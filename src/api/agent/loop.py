"""Цикл диалога: вопрос → ответ по отчёту.

Живёт здесь, а не в MCP-сервере: MCP отдаёт возможности, а оркестрацию ведёт клиент.
В протоколе нет метода «запусти агента», и это не ограничение, а граница ответственности.

Путей два, и различает их **только транспорт**. `run_stream` отдаёт события
по мере работы, `run` — один готовый ответ. Агент под ними один и тот же:
те же инструменты, тот же контекст, те же правила. Что в потоке приходит
событиями `chart` и `sources`, здесь возвращается полями ответа — иначе
программный клиент получил бы внешние сведения без ссылок, а это запрещено
промптом.

Так было не всегда, и разошлись они молча. У `run` была своя сборка контекста
(`build_messages` из первого коммита) и ни одного инструмента. Коммит 006 добавил
в общий `SYSTEM_PROMPT` раздел «Про инструменты» и снял границу «искать вне отчёта
не умеешь» — но инструменты выдал только потоку. `run` стал сообщать модели, что
умеет показывать графики и искать снаружи, не имея ни того, ни другого. Тесты
это пропустили: они проверяли только роли сообщений.

Память — в рамках одной сессии. Кейсодатель: «память нужна именно в рамках одной
сессии», между сессиями оценка не переносится.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, ToolMessage

from api.agent import events, graph, prompt
from core.charts import build_charts
from core.llm import environment
from core.report import Report

PROVIDER_DOWN = "Сервис разбора сейчас недоступен. Отчёт выше остаётся полным."
EMPTY_ANSWER = "Модель не смогла сформулировать ответ. Попробуйте переспросить короче."

# Сколько пар «вопрос-ответ» держим. Ограничение не про память, а про токены:
# у провайдера лимит считает вход, и растущая история съела бы минутную квоту.
HISTORY_TURNS = 6


@dataclass
class Session:
    """Состояние одного диалога. Живёт в памяти процесса, наружу не переживает."""

    session_id: str
    history: list[dict] = field(default_factory=list)
    focus_inn: str | None = None  # о каком контрагенте сейчас речь

    def focus(self, inn: str) -> None:
        """Переключает контрагента, сбрасывая разговор.

        Ответы о предыдущей компании в новом контексте вводят в заблуждение:
        пользователь читает их как относящиеся к текущей.
        """
        if self.focus_inn != inn:
            self.history.clear()
            self.focus_inn = inn

    def remember(self, question: str, answer: str) -> None:
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": answer})
        del self.history[: max(0, len(self.history) - HISTORY_TURNS * 2)]


@dataclass(frozen=True)
class Answer:
    """Ответ диалога: текст, обоснование и всё, что добыли инструменты.

    `charts` и `sources` — то же, что в потоке уходит событиями `chart`
    и `sources`. Без них непотоковый клиент не смог бы ни нарисовать
    запрошенный график, ни показать ссылку на внешний источник, хотя промпт
    требует ссылку всегда.
    """

    text: str
    sections: tuple[str, ...] = ()
    charts: tuple[str, ...] = ()
    sources: tuple[dict, ...] = ()


_SESSIONS: dict[str, Session] = {}


def session(session_id: str) -> Session:
    """Сессия по идентификатору, создавая при первом обращении."""
    if session_id not in _SESSIONS:
        _SESSIONS[session_id] = Session(session_id=session_id)
    return _SESSIONS[session_id]


def _grounding(report: Report, text: str) -> tuple[str, ...]:
    """Разделы, названные в ответе — по имени раздела или по заголовку его фактора.

    Не угадываем «на что мог опираться»: отмечаем только то, что модель назвала сама.
    Придуманное обоснование хуже отсутствующего — оно выглядит как проверка,
    которой не было.

    Заголовки факторов учитываются потому, что модель говорит «Блокировки счетов
    налоговой», а не «раздел Реестры»: по одним названиям разделов обоснование
    оставалось пустым почти всегда.
    """
    lowered = text.lower()
    found = []
    for section in report.sections:
        named = section.title.lower() in lowered or any(
            f.heading.lower() in lowered for f in section.factors
        )
        if named:
            found.append(section.key)
    return tuple(found)


def _trace(report: Report) -> dict:
    """Настройки вызова агента: предел шагов и метки для записи в LangSmith.

    Метки обязательны. Без `inn` и окружения записи неразличимы — непонятно,
    о какой компании речь и пришёл ли вызов с сервера или с ноутбука. У непотокового
    пути они были, пока он ходил через `LLMClient.ask`, и потерялись при переезде
    на агента; у потокового их не было никогда. Здесь они общие для обоих.
    """
    return {
        "recursion_limit": graph.MAX_STEPS * 2,
        "run_name": "counterparty-chat",
        "metadata": {"environment": environment(), "inn": report.inn},
    }


def _harvest(messages: list) -> tuple[str, tuple[str, ...], tuple[dict, ...]]:
    """Текст ответа и добытое инструментами из готовой переписки агента.

    Разбор тот же, что в `events.Translator`, но по завершённой переписке,
    а не по кускам потока: там события рождаются по мере работы, здесь всё
    известно сразу. Итог инструмента с признаком ошибки пропускаем — неудавшийся
    вызов не должен выглядеть как добытые данные.
    """
    text, charts, sources = "", [], []
    for message in messages:
        if isinstance(message, ToolMessage):
            if getattr(message, "status", "success") == "error":
                continue
            payload = getattr(message, "artifact", None)
            if not isinstance(payload, dict):
                continue
            if "chart" in payload:
                charts.append(payload["chart"]["chart"])
            if "sources" in payload:
                sources.extend(payload["sources"])
        elif isinstance(message, AIMessage):
            # Ответом считаем последнюю реплику модели: до неё идут те, что
            # только заказывали инструменты, и текста в них нет.
            text = message.text or text
    return text.strip(), tuple(charts), tuple(sources)


async def run(
    state: Session,
    report: Report,
    record: dict,
    question: str,
    tools: list | None = None,
) -> Answer:
    """Прогоняет шаг диалога и возвращает готовый ответ целиком.

    Тот же агент, что в потоке, — отличается только доставка. Асинхронный по той
    же причине, что и `run_stream`: инструменты ходят по сети, а синхронный вызов
    занимал бы поток из пула Starlette всё время ответа.
    """
    state.focus(report.inn)
    charts = {c.key: c for c in build_charts(record)}
    agent = graph.build(
        tools or [], prompt.system_prompt(report, [c.title for c in charts.values()], question)
    )
    result = await agent.ainvoke(
        {"messages": prompt.conversation(question, state.history)},
        context=graph.Context(record=record, report=report),
        config=_trace(report),
    )
    text, показанные, найденные = _harvest(result["messages"])
    if not text:
        # У gpt-oss рассуждение приходит отдельным полем и способно съесть весь
        # бюджет, оставив content пустым. Пустой ответ выдавать за содержательный
        # нельзя — это неотличимо от «мне нечего сказать».
        raise RuntimeError("Модель вернула пустой ответ")
    state.remember(question, text)
    return Answer(
        text=text,
        sections=_grounding(report, text),
        charts=показанные,
        sources=найденные,
    )


async def run_stream(
    state: Session,
    report: Report,
    record: dict,
    question: str,
    tools: list | None = None,
) -> AsyncIterator[events.Event]:
    """Прогоняет шаг диалога, отдавая события по мере работы агента.

    Асинхронный намеренно. Синхронный генератор Starlette крутит в пуле потоков,
    и каждый поток занят всё время ответа: на длинных потоках пул кончается
    и блокирует весь сервис, включая обычные ручки. Одновременных пользователей
    при этом было бы столько, сколько потоков в пуле.

    Отличается от `run` не только транспортом: здесь у модели есть инструменты,
    и запись о контрагенте целиком уезжает в контекст выполнения, откуда её
    читают они. В промпт запись не попадает — 31 000 токенов на типовой компании
    при лимите провайдера 8 000 в минуту.

    Непотоковый `run` рядом — для клиентов, которые событий не понимают. Агент
    у них общий, поэтому расходиться в возможностях им больше нечем.
    """
    state.focus(report.inn)
    charts = {c.key: c for c in build_charts(record)}
    titles = [c.title for c in charts.values()]
    agent = graph.build(tools or [], prompt.system_prompt(report, titles, question))
    translator = events.Translator(charts)

    said: list[str] = []
    try:
        stream = agent.astream(
            {"messages": prompt.conversation(question, state.history)},
            context=graph.Context(record=record, report=report),
            stream_mode="messages",
            config=_trace(report),
        )
        async for chunk, _meta in stream:
            for event in translator.feed(chunk):
                if event.name == "token":
                    said.append(event.data["text"])
                yield event
    except Exception:  # noqa: BLE001 — наружу уходит одно понятное событие
        # Ошибка приходит событием, а не обрывом потока: уже показанный текст
        # остаётся у пользователя, и он видит причину, а не молчание.
        yield events.Event("error", {"detail": PROVIDER_DOWN})
    else:
        if not "".join(said).strip():
            # У gpt-oss рассуждение тратит токены из того же лимита и способно
            # съесть весь бюджет, оставив ответ пустым. Пустой ответ после
            # показанного вызова инструмента выглядит как поломка, а не как
            # «мне нечего сказать».
            yield events.Event("error", {"detail": EMPTY_ANSWER})

    text = "".join(said).strip()
    if text:
        state.remember(question, text)
    yield events.Event("done", {"sections": list(_grounding(report, text))})

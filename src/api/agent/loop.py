"""Цикл диалога: вопрос → ответ по отчёту.

Живёт здесь, а не в MCP-сервере: MCP отдаёт возможности, а оркестрацию ведёт клиент.
В протоколе нет метода «запусти агента», и это не ограничение, а граница ответственности.

Инструментов у модели нет намеренно. Отчёт помещается в контекст целиком — самая
тяжёлая компания даёт около 740 токенов, — поэтому дотягиваться не за чем.
А невызванный инструмент это прямой путь к выдумыванию, и «не выдумывает» стоит
первым в критериях приёмки кейса.

Память — в рамках одной сессии. Кейсодатель: «память нужна именно в рамках одной
сессии», между сессиями оценка не переносится.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from api.agent import events, graph, prompt
from api.agent.prompt import build_messages
from core.charts import build_charts
from core.llm import LLMClient
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
    """Ответ диалога и разделы, на которые он опирается."""

    text: str
    sections: tuple[str, ...] = ()


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


def run(state: Session, report: Report, question: str, client: LLMClient | None = None) -> Answer:
    """Прогоняет один шаг диалога и возвращает ответ пользователю."""
    state.focus(report.inn)
    messages = build_messages(report, question, state.history)
    answer = (client or LLMClient()).ask(messages, max_tokens=700, inn=report.inn)
    text = answer.content.strip()
    if not text:
        # У gpt-oss рассуждение приходит отдельным полем и способно съесть весь
        # бюджет, оставив content пустым. Пустой ответ выдавать за содержательный
        # нельзя — это неотличимо от «мне нечего сказать».
        raise RuntimeError("Модель вернула пустой ответ")
    state.remember(question, text)
    return Answer(text=text, sections=_grounding(report, text))


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

    Непотоковый `run` остаётся: его читают MCP-сервер и программные клиенты,
    поток они не понимают.
    """
    state.focus(report.inn)
    charts = {c.key: c for c in build_charts(record)}
    titles = [c.title for c in charts.values()]
    agent = graph.build(tools or [], prompt.system_prompt(report, titles))
    translator = events.Translator(charts)

    said: list[str] = []
    try:
        stream = agent.astream(
            {"messages": prompt.conversation(question, state.history)},
            context=graph.Context(record=record, report=report),
            stream_mode="messages",
            config={"recursion_limit": graph.MAX_STEPS * 2},
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

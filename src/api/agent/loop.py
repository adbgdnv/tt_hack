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

import asyncio
import re
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field, replace

from langchain_core.messages import AIMessage, ToolMessage

from api.agent import events, graph, prompt
from core import deal as deals
from core import verify
from core.charts import build_charts
from core.deal import Deal
from core.llm import PRIMARY, LLMClient, Route, chain, environment
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
    deal: Deal = field(default_factory=Deal)  # что за сделку человек проверяет

    def focus(self, inn: str) -> None:
        """Переключает контрагента, сбрасывая разговор.

        Ответы о предыдущей компании в новом контексте вводят в заблуждение:
        пользователь читает их как относящиеся к текущей.

        Условия сделки при этом остаются: они про задачу пользователя, а не про
        компанию. Закупщик, который смотрит трёх поставщиков под один аванс,
        описывал бы их заново на каждой карточке.
        """
        if self.focus_inn != inn:
            self.history.clear()
            self.focus_inn = inn

    def situation(self, question: str, stated: Deal | None = None) -> Deal:
        """Условия сделки после этой реплики: форма, потом сама реплика.

        Порядок именно такой. Форма — то, что человек выставил раньше, реплика —
        то, что он говорит сейчас: «а если отсрочка?» должно переигрывать
        выставленный аванс, иначе разговор и сохранённый контекст расходятся.
        """
        if stated is not None:
            self.deal = deals.merge(self.deal, stated)
        self.deal = deals.from_text(question, self.deal)
        return self.deal

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
    lookups: tuple[dict, ...] = ()
    check: verify.Verification = field(default_factory=verify.Verification)
    # Условия сделки, с которыми отвечали. Уходят клиенту, потому что часть
    # из них разобрана из реплики: человек должен видеть, что именно у нас
    # сохранилось, и мочь это поправить.
    deal: Deal = field(default_factory=Deal)


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


def _trace(report: Report, route: Route | None = None) -> dict:
    """Настройки вызова агента: предел шагов и метки для записи в LangSmith.

    Метки обязательны. Без `inn` и окружения записи неразличимы — непонятно,
    о какой компании речь и пришёл ли вызов с сервера или с ноутбука. У непотокового
    пути они были, пока он ходил через `LLMClient.ask`, и потерялись при переезде
    на агента; у потокового их не было никогда. Здесь они общие для обоих.
    """
    return {
        "recursion_limit": graph.MAX_STEPS * 2,
        "run_name": "counterparty-chat",
        "metadata": {
            "environment": environment(),
            "inn": report.inn,
            "provider": route.provider if route else "",
            "model": route.model if route else "",
        },
    }


def _harvest(
    messages: list,
) -> tuple[str, tuple[str, ...], tuple[dict, ...], tuple[dict, ...]]:
    """Текст ответа и добытое инструментами из готовой переписки агента.

    Разбор тот же, что в `events.Translator`, но по завершённой переписке,
    а не по кускам потока: там события рождаются по мере работы, здесь всё
    известно сразу. Итог инструмента с признаком ошибки пропускаем — неудавшийся
    вызов не должен выглядеть как добытые данные.
    """
    text, charts, sources, lookups = "", [], [], []
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
            if "lookup" in payload:
                lookups.append(payload["lookup"])
        elif isinstance(message, AIMessage):
            # Ответом считаем последнюю реплику модели: до неё идут те, что
            # только заказывали инструменты, и текста в них нет.
            text = message.text or text
    return text.strip(), tuple(charts), tuple(sources), tuple(lookups)


# Вторая ступень проверки. Зовётся только когда сверка числами не сошлась:
# на подтверждённом ответе она стоила бы вызова модели впустую.
ВТОРАЯ_СТУПЕНЬ = """Ниже отчёт о компании и числа из ответа ассистента, которых
автоматическая сверка в отчёте не нашла. Сверка сравнивает величины и промахивается
на пересчётах, долях и суммах, которые ассистент сложил сам.

Назови через запятую номера тех чисел, которые отчёт всё-таки подтверждает —
прямо или очевидным пересчётом. Если ни одного, ответь «нет». Ничего кроме
номеров не пиши.

ОТЧЁТ:
{report}

ЧИСЛА:
{claims}"""


async def _second_opinion(
    report: Report, checked: verify.Verification, route: Route
) -> verify.Verification:
    """Спрашивает модель про числа, которых сверка не нашла.

    Отдельный дешёвый вызов, а не второй агент: у него нет ни инструментов,
    ни истории — только отчёт и список чисел. Отказ второй ступени не отменяет
    первую: остаётся результат сверки, честно помеченный как непроверенный
    моделью.
    """
    спорные = [(номер, c) for номер, c in enumerate(checked.claims, 1) if not c.found]
    перечень = "\n".join(f"{номер}) «{c.number}» — {c.context}" for номер, c in спорные)
    вопрос = ВТОРАЯ_СТУПЕНЬ.format(report=prompt.render_report(report), claims=перечень)
    try:
        ответ = await asyncio.to_thread(
            LLMClient(provider=route.provider, model=route.model).ask,
            [{"role": "user", "content": вопрос}],
            max_tokens=300,
            inn=report.inn,
        )
    except Exception:  # noqa: BLE001 — сеть; первая ступень уже дала результат
        return checked
    подтверждённые = {int(n) for n in re.findall(r"\d+", ответ.content)}
    claims = list(checked.claims)
    for номер, _ in спорные:
        if номер in подтверждённые:
            claims[номер - 1] = replace(claims[номер - 1], found=True)
    return verify.Verification(
        claims=tuple(claims),
        unverified=sum(1 for c in claims if not c.found),
        checked=True,
    )


async def _verified(
    report: Report, text: str, route: Route, extras: tuple[str, ...] = ()
) -> verify.Verification:
    """Проверка ответа лестницей: сначала кодом, моделью — только если не сошлось.

    Ступень вторая стоит вызова модели, поэтому не зовётся никогда, пока первая
    сходится. На проверенном наборе вопросов сходится она в большинстве случаев.
    """
    итог = verify.check(text, report, extras)
    if итог.unverified == 0:
        return итог
    return await _second_opinion(report, итог, route)



def _text_of(messages: list) -> str:
    """Текст ответа из переписки — чтобы отличить молчание от ответа, не разбирая
    всё остальное."""
    return _harvest(messages)[0]


def _shown(lookups: tuple[dict, ...], sources: tuple[dict, ...]) -> tuple[str, ...]:
    """Всё, что пользователь увидел рядом с ответом, кроме самого отчёта.

    Проверка сверяет ответ с этим наравне с отчётом: взятое по теме и выдержка
    из внешнего источника лежат у пользователя на экране, значит числа из них —
    такое же основание, как числа отчёта.
    """
    взятое = tuple(тема.get("text", "") for тема in lookups)
    находки = tuple(f"{ссылка.get('title', '')} {ссылка.get('snippet', '')}" for ссылка in sources)
    return взятое + находки


def _routes() -> tuple[Route, ...]:
    """Пути по порядку. Пустой — «как настроено»: так тест с подставным агентом
    работает там, где настоящего ключа нет вовсе."""
    return chain() or (Route(PRIMARY),)


async def run(
    state: Session,
    report: Report,
    record: dict,
    question: str,
    tools: list | None = None,
    deal: Deal | None = None,
) -> Answer:
    """Прогоняет шаг диалога и возвращает готовый ответ целиком.

    Тот же агент, что в потоке, — отличается только доставка. Асинхронный по той
    же причине, что и `run_stream`: инструменты ходят по сети, а синхронный вызов
    занимал бы поток из пула Starlette всё время ответа.

    Отказ основного провайдера переводит вызов на запасного. Пользователь приходит
    за разбором, а не за отчётом о нашей инфраструктуре: ошибка провайдера должна
    доходить до него только тогда, когда не осталось ни одного.
    """
    state.focus(report.inn)
    сделка = state.situation(question, deal)
    charts = {c.key: c for c in build_charts(record)}
    системный = prompt.system_prompt(
        report, [c.title for c in charts.values()], question, сделка
    )

    пути = _routes()
    последняя = None
    for номер, путь in enumerate(пути):
        agent = graph.build(tools or [], системный, provider=путь.provider, model=путь.model)
        try:
            result = await agent.ainvoke(
                {"messages": prompt.conversation(question, state.history)},
                context=graph.Context(record=record, report=report),
                config=_trace(report, путь),
            )
        except Exception as error:  # noqa: BLE001 — решение о запасном пути принимаем здесь
            последняя = error
            if номер + 1 < len(пути):
                continue
            raise
        # Молчание — такой же отказ, как ошибка: рассуждение способно съесть весь
        # бюджет ответа, и у следующей модели на это свой шанс. Замерено на живом
        # прогоне: один вопрос из десяти вернулся пустым и повторился нормально.
        if _text_of(result["messages"]) or номер + 1 == len(пути):
            break
    else:  # pragma: no cover — цикл всегда либо возвращает, либо поднимает
        raise RuntimeError("Не настроен ни один провайдер модели") from последняя

    text, показанные, найденные, взятое = _harvest(result["messages"])
    if not text:
        # Рассуждение приходит отдельным полем и способно съесть весь бюджет,
        # оставив content пустым. Пустой ответ выдавать за содержательный нельзя —
        # это неотличимо от «мне нечего сказать».
        raise RuntimeError("Модель вернула пустой ответ")
    state.remember(question, text)
    return Answer(
        text=text,
        sections=_grounding(report, text),
        charts=показанные,
        sources=найденные,
        lookups=взятое,
        check=await _verified(report, text, путь, _shown(взятое, найденные)),
        deal=сделка,
    )


async def run_stream(
    state: Session,
    report: Report,
    record: dict,
    question: str,
    tools: list | None = None,
    deal: Deal | None = None,
) -> AsyncIterator[events.Event]:
    """Прогоняет шаг диалога, отдавая события по мере работы агента.

    Асинхронный намеренно. Синхронный генератор Starlette крутит в пуле потоков,
    и каждый поток занят всё время ответа: на длинных потоках пул кончается
    и блокирует весь сервис, включая обычные ручки. Одновременных пользователей
    при этом было бы столько, сколько потоков в пуле.

    Отличается от `run` не только транспортом: здесь у модели есть инструменты,
    и запись о контрагенте целиком уезжает в контекст выполнения, откуда её
    читают они. В промпт запись не попадает — модель должна видеть ровно то,
    что видит пользователь.

    Непотоковый `run` рядом — для клиентов, которые событий не понимают. Агент
    у них общий, поэтому расходиться в возможностях им больше нечем.
    """
    state.focus(report.inn)
    # Условия сделки — первым событием, до единого токена ответа. Часть из них
    # разобрана из самой реплики, и человек должен видеть, что у нас сохранилось,
    # раньше, чем прочтёт ответ, построенный на этом.
    сделка = state.situation(question, deal)
    yield events.Event("deal", asdict(сделка))
    charts = {c.key: c for c in build_charts(record)}
    titles = [c.title for c in charts.values()]
    системный = prompt.system_prompt(report, titles, question, сделка)

    пути = _routes()
    said: list[str] = []
    # Всё, что уехало пользователю кроме текста: проверка сверяет ответ и с этим.
    показанное: list[dict] = []
    внешнее: list[dict] = []
    отказ = ""
    путь = пути[0]
    for номер, путь in enumerate(пути):
        agent = graph.build(tools or [], системный, provider=путь.provider, model=путь.model)
        translator = events.Translator(charts)
        сказано = len(said)
        try:
            stream = agent.astream(
                {"messages": prompt.conversation(question, state.history)},
                context=graph.Context(record=record, report=report),
                stream_mode="messages",
                config=_trace(report, путь),
            )
            async for chunk, _meta in stream:
                for event in translator.feed(chunk):
                    if event.name == "token":
                        said.append(event.data["text"])
                    elif event.name == "lookup":
                        показанное.append(event.data)
                    elif event.name == "sources":
                        внешнее.extend(event.data["items"])
                    yield event
        except Exception:  # noqa: BLE001 — наружу уходит одно понятное событие
            # Запасной провайдер имеет смысл, только пока пользователь ничего
            # не увидел: показанный текст переиграть нельзя, и второй ответ
            # поверх первого читался бы как две разные оценки одной компании.
            if len(said) == сказано and номер + 1 < len(пути):
                continue
            # Ошибка приходит событием, а не обрывом потока: уже показанный текст
            # остаётся у пользователя, и он видит причину, а не молчание.
            отказ = PROVIDER_DOWN
        else:
            # Молчание — такой же отказ, как ошибка. Замерено: один вопрос
            # из десяти вернулся пустым и на повторе ответил нормально.
            if not "".join(said).strip() and номер + 1 < len(пути):
                continue
        break

    text = "".join(said).strip()
    if not отказ and not text:
        # Рассуждение тратит токены из бюджета ответа и способно съесть его
        # целиком. Пустой ответ после показанного вызова инструмента выглядит
        # как поломка, а не как «мне нечего сказать».
        отказ = EMPTY_ANSWER
    if отказ:
        yield events.Event("error", {"detail": отказ})

    if text:
        state.remember(question, text)
        # Проверка после ответа, а не до: ответ уже прочитан, а отметка о том,
        # чем он подтверждён, догоняет его через секунду. Задерживать ради неё
        # первое слово значило бы платить за проверку задержкой всего ответа.
        yield _check_event(
            await _verified(report, text, путь, _shown(tuple(показанное), tuple(внешнее)))
        )
    yield events.Event("done", {"sections": list(_grounding(report, text))})


def _check_event(итог: verify.Verification) -> events.Event:
    """Итог проверки в событие. Неподтверждённое показывается целиком: удалить
    его значит спрятать сомнение, а пользователю нужны и утверждение, и сомнение."""
    return events.Event(
        "check",
        {
            "total": len(итог.claims),
            "unverified": [
                {"number": c.number, "context": c.context} for c in итог.claims if not c.found
            ],
            "checked": итог.checked,
        },
    )

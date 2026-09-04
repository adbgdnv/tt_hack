"""Диалог о контрагенте.

Модель подменяется: проверяется поведение цикла, а не качество ответов. Качество
проверяется вручную по quickstart на живом провайдере — автоматически его
не поймать, а вот сборку контекста и сброс истории поймать можно.
"""

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from api.agent import loop
from api.agent.prompt import SYSTEM_PROMPT, render_report, system_prompt
from core.report import build


class ПодставнойАгент:
    """Отвечает заготовкой и запоминает, что ему передали.

    Подменяет граф целиком, а не модель: после того как непотоковый путь переехал
    на того же агента, что и поток, точка подмены у обоих одна — `graph.build`.
    """

    def __init__(self, text="Ответ по отчёту", tool_messages=()):
        self.text = text
        self.tool_messages = list(tool_messages)
        self.messages = None

    async def ainvoke(self, state, **_):
        self.messages = state["messages"]
        return {"messages": [*self.tool_messages, AIMessage(content=self.text)]}


@pytest.fixture
def агент(monkeypatch):
    """Ставит подставного агента и отдаёт функцию запуска одного шага."""

    def поставить(text="Ответ по отчёту", tool_messages=()):
        подставной = ПодставнойАгент(text, tool_messages)
        monkeypatch.setattr(loop.graph, "build", lambda *_, **__: подставной)
        return подставной

    return поставить


def запись(inn="7704310756", name='ООО "ТЕСТ"', **overrides) -> dict:
    record = {
        "baseInfo": {
            "inn": inn,
            "shortName": name,
            "riskLevel": "LOW",
            "registrationInfo": {"yearsFromRegistration": 9},
        },
        "status": {"status": "CURRENT"},
        "zskRiskLevel": "GREEN",
        "reputationalRisks": {"negative": [], "positive": []},
    }
    record.update(overrides)
    return record


@pytest.fixture(autouse=True)
def чистые_сессии():
    loop._SESSIONS.clear()
    yield
    loop._SESSIONS.clear()


# ─────────────────────────── контекст ───────────────────────────


def test_отчёт_уходит_в_контекст_целиком():
    """Модель должна видеть ровно то, что видит пользователь."""
    report = build(запись())
    системная = system_prompt(report, [])
    assert SYSTEM_PROMPT in системная
    assert report.name in системная
    for section in report.sections:
        assert section.title in системная


async def test_оба_канала_собирают_агента_одинаково(monkeypatch):
    """Поток и обычная ручка обязаны строить одного и того же агента.

    Держит починку расхождения, из-за которого правка промпта доезжала до одного
    канала из двух: у `run` была своя сборка контекста и ни одного инструмента,
    а коммит 006 добавил в общий `SYSTEM_PROMPT` правила про инструменты. Обычная
    ручка стала обещать то, чего у неё не было, и тесты это пропустили — они
    проверяли только роли сообщений.

    Сравниваем то, что каждый канал передал в `graph.build`: набор инструментов
    и системную часть.
    """
    записанное = []

    def перехват(tools, system):
        записанное.append((tools, system))
        return ПодставнойАгент()

    monkeypatch.setattr(loop.graph, "build", перехват)
    инструменты = ["инструмент"]
    отчёт, record = build(запись()), запись()

    await loop.run(loop.Session(session_id="a"), отчёт, record, "Вопрос", инструменты)
    поток = loop.run_stream(loop.Session(session_id="b"), отчёт, record, "Вопрос", инструменты)
    [_ async for _ in поток]

    assert len(записанное) == 2
    assert записанное[0] == записанное[1]


async def test_вызов_помечается_для_трассировки(monkeypatch):
    """Без ИНН и окружения записи в LangSmith неразличимы: непонятно, о какой
    компании речь и откуда пришёл вызов.

    Метки были у непотокового пути, пока он ходил через `LLMClient.ask`, и
    потерялись при переезде на агента — тесты этого не заметили, потому что
    проверяли `ask`, а не цикл.
    """
    записанное = {}

    class Запоминающий(ПодставнойАгент):
        async def ainvoke(self, state, **kwargs):
            записанное.update(kwargs.get("config") or {})
            return await super().ainvoke(state, **kwargs)

    monkeypatch.setattr(loop.graph, "build", lambda *_, **__: Запоминающий())
    отчёт = build(запись(inn="7704310756"))
    await loop.run(loop.session("s1"), отчёт, запись(), "Вопрос", [])

    assert записанное["run_name"] == "counterparty-chat"
    assert записанное["metadata"]["inn"] == "7704310756"
    assert записанное["metadata"]["environment"] in {"local", "server"}
    # Предел шагов не должен потеряться вместе с добавлением меток
    assert записанное["recursion_limit"] == loop.graph.MAX_STEPS * 2


async def test_добытое_инструментами_возвращается_полями(агент):
    """В потоке график и ссылки уходят событиями. Здесь событий нет, и без полей
    клиент получил бы внешние сведения без ссылок — промпт этого не допускает."""
    итоги = [
        ToolMessage(content="показан", tool_call_id="1", artifact={"chart": {"chart": "balance"}}),
        ToolMessage(
            content="найдено",
            tool_call_id="2",
            artifact={"sources": [{"title": "Т", "url": "https://x", "snippet": ""}]},
        ),
    ]
    агент(tool_messages=итоги)
    ответ = await loop.run(loop.session("s1"), build(запись()), запись(), "Вопрос", [])
    assert ответ.charts == ("balance",)
    assert ответ.sources[0]["url"] == "https://x"


async def test_неудавшийся_вызов_не_считается_добытым(агент):
    """Инструмент, вернувший ошибку, не должен выглядеть как показанный график."""
    сбой = ToolMessage(
        content="не вышло",
        tool_call_id="1",
        status="error",
        artifact={"chart": {"chart": "balance"}},
    )
    агент(tool_messages=[сбой])
    ответ = await loop.run(loop.session("s1"), build(запись()), запись(), "Вопрос", [])
    assert ответ.charts == ()


def test_отсутствие_оценки_проговаривается_словами():
    """«Оценить невозможно» не должно читаться моделью как низкий риск."""
    record = запись()
    record["baseInfo"]["riskLevel"] = "UNKNOWN"
    текст = render_report(build(record))
    assert "оценка отсутствует" in текст
    assert "это не низкий риск" in текст


def test_у_предпринимателя_разделы_помечены_неприменимыми():
    текст = render_report(build(запись(name="ИП Иванов И.И.")))
    assert "не применимо к этой форме собственности" in текст


# ─────────────────────────── сессия ───────────────────────────


async def test_история_накапливается(агент):
    агент()
    state, report = loop.session("s1"), build(запись())
    await loop.run(state, report, запись(), "Первый вопрос", [])
    await loop.run(state, report, запись(), "Второй вопрос", [])
    assert len(state.history) == 4
    assert state.history[0]["content"] == "Первый вопрос"


async def test_смена_контрагента_сбрасывает_разговор(агент):
    """Ответы о предыдущей компании в новом контексте вводят в заблуждение."""
    агент()
    state = loop.session("s1")
    первая, вторая = запись(inn="1111111111"), запись(inn="2222222222")
    await loop.run(state, build(первая), первая, "Вопрос про первую", [])
    assert state.history
    await loop.run(state, build(вторая), вторая, "Вопрос про вторую", [])
    assert len(state.history) == 2
    assert state.focus_inn == "2222222222"


async def test_история_ограничена_по_длине(агент):
    """Растущая история съела бы минутную квоту провайдера."""
    агент()
    state, report = loop.session("s1"), build(запись())
    for i in range(loop.HISTORY_TURNS + 4):
        await loop.run(state, report, запись(), f"Вопрос {i}", [])
    assert len(state.history) <= loop.HISTORY_TURNS * 2


# ─────────────────────────── отказ и сбой ───────────────────────────


async def test_пустой_ответ_модели_это_ошибка_а_не_ответ(агент):
    """У gpt-oss рассуждение приходит отдельным полем и способно съесть бюджет,
    оставив content пустым. Выдавать пустоту за ответ нельзя."""
    агент(text="")
    with pytest.raises(RuntimeError):
        await loop.run(loop.session("s1"), build(запись()), запись(), "Вопрос", [])


async def test_обоснование_отмечает_только_названные_разделы(агент):
    """Придуманное обоснование хуже отсутствующего: выглядит как проверка,
    которой не было."""
    агент(text="По разделу Суды данных нет.")
    ответ = await loop.run(loop.session("s1"), build(запись()), запись(), "Что по судам?", [])
    assert "courts" in ответ.sections
    assert "finances" not in ответ.sections


def test_промпт_перечисляет_настоящие_разделы():
    """Список возможностей в промпте должен совпадать с разделами отчёта.

    Иначе ассистент обещает то, чего нет: переименовали раздел — и на вопрос
    «что ты умеешь» он называет несуществующий. Обещание, которого продукт
    не выполняет, хуже отсутствующего.
    """
    from core.report import SECTION_TITLES

    пропущены = [
        название
        for название in SECTION_TITLES.values()
        # в промпте они перечислены в именительном падеже и без заглавной
        if название.split()[0].lower()[:6] not in SYSTEM_PROMPT.lower()
    ]
    assert not пропущены, f"в промпте не названы разделы: {пропущены}"


def test_промпт_очерчивает_границы():
    """Без явного «не умею» модель отвечает как обычная языковая модель —
    обещает переводы и разговор на любые темы. Проверено на живом провайдере."""
    for граница in ["не умеешь", "переводить", "отраслевыми нормами"]:
        assert граница in SYSTEM_PROMPT.lower(), f"из промпта пропала граница: {граница}"


def test_промпт_подчиняет_внешние_источники_отчёту():
    """Поиск снаружи появился, и он же — главный способ сломать «не выдумывает».
    Кейсодатель задал иерархию: «доверяем прежде всего данным, которые есть у нас».

    Раньше здесь стояла граница «искать вне отчёта не умеешь». Она снята вместе
    с появлением инструмента поиска — на её место встают эти правила.
    """
    низкий = SYSTEM_PROMPT.lower()

    assert "отчёта не хватает" in низкий  # когда вообще можно искать
    assert "отдельным слоем" in низкий  # найденное не смешивается с отчётом
    assert "не подтверждено" in низкий  # и помечается
    assert "верь отчёту" in низкий  # при расхождении

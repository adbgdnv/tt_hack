"""Разбор нескольких контрагентов сразу.

Модель подменяется: проверяется собранный контекст и поток событий, а не
качество ответа. Спека — `specs/014-pool-chat/spec.md`.
"""

from types import SimpleNamespace

import pytest
from langgraph.runtime import Runtime

from api.agent import graph, loop, prompt, tools
from core import compare
from core.report import build

ЧИСТАЯ = {
    "baseInfo": {
        "inn": "7700000001",
        "shortName": 'ООО "ЧИСТАЯ"',
        "riskLevel": "LOW",
        "registrationInfo": {"yearsFromRegistration": 12},
    },
    "status": {"status": "CURRENT"},
    "zskRiskLevel": "GREEN",
    "reputationalRisks": {"negative": [], "positive": []},
}

ТЯЖЁЛАЯ = {
    "baseInfo": {
        "inn": "7700000002",
        "shortName": 'ООО "ТЯЖЁЛАЯ"',
        "riskLevel": "HIGH",
        "registrationInfo": {"yearsFromRegistration": 0},
    },
    "status": {"status": "CURRENT"},
    "zskRiskLevel": "RED",
    "reputationalRisks": {
        "negative": [{"code": "massAddress", "name": "Массовый адрес"}],
        "positive": [],
    },
}

ПУЛ = [ЧИСТАЯ, ТЯЖЁЛАЯ]


def кусок(текст):
    return SimpleNamespace(content=текст, tool_call_chunks=[])


class ПодставнойАгент:
    """Отдаёт заготовленные куски и запоминает, с чем его собрали."""

    def __init__(self, куски=()):
        self.куски = куски

    def astream(self, *_, **__):
        async def поток():
            for к in self.куски:
                yield к, {}

        return поток()


async def прогнать(monkeypatch, вопрос="кому из них можно отгружать?", записи=ПУЛ):
    """Прогон разбора пула с подменённой моделью. Возвращает события и промпт."""
    собранное: dict = {}

    def сборка(_tools, системный, provider="", model="", **_):
        собранное["prompt"] = системный
        return ПодставнойАгент([кусок("Разберу обеих.")])

    monkeypatch.setattr(loop.graph, "build", сборка)
    поток = loop.run_pool_stream(loop.Session(session_id="т"), записи, вопрос)
    return [с async for с in поток], собранное


# ─────────────────────────── Контекст пула ───────────────────────────


async def test_в_контексте_вывод_сравнения_а_не_свой_порядок(monkeypatch):
    _, собранное = await прогнать(monkeypatch)

    системный = собранное["prompt"]
    assert "ВЫВОД СРАВНЕНИЯ:" in системный
    # Обе компании названы: разбор пула, который упомянул одну, — не разбор пула.
    assert 'ООО "ЧИСТАЯ"' in системный
    assert 'ООО "ТЯЖЁЛАЯ"' in системный


async def test_балла_в_контексте_нет(monkeypatch):
    """Кейсодатель: «Ранжирование в виде какого-то скора не требуется».

    Балл в контексте модель бы процитировала, и он оказался бы в ответе.
    """
    _, собранное = await прогнать(monkeypatch)

    вывод = собранное["prompt"].split("ВЫВОД СРАВНЕНИЯ:")[1].split("ОТЧЁТЫ")[0]
    assert "балл" not in вывод.lower()
    assert "score" not in вывод.lower()


async def test_порядок_в_контексте_тот_же_что_на_экране(monkeypatch):
    _, собранное = await прогнать(monkeypatch)

    вердикты = compare.compare(ПУЛ)
    системный = собранное["prompt"]
    места = [системный.index(f"ИНН {в.inn}") for в in вердикты]
    assert места == sorted(места), "порядок в промпте разошёлся с порядком на экране"


async def test_условия_сделки_действуют_на_весь_пул(monkeypatch):
    _, собранное = await прогнать(
        monkeypatch, вопрос="мы поставщик, отсрочка 60 дней — кому отгружать?"
    )

    assert "60" in собранное["prompt"]


async def test_свой_системный_промпт_а_не_промпт_одной_компании(monkeypatch):
    """Роль разная: в отчёте разбирают одну компанию, в пуле — выбирают между.

    Общими остаются принципы, а не роль и границы.
    """
    _, собранное = await прогнать(monkeypatch)

    assert собранное["prompt"].startswith(prompt.POOL_SYSTEM_PROMPT[:40])
    assert собранное["prompt"] != prompt.SYSTEM_PROMPT


# ─────────────────────────── Поток ───────────────────────────


async def test_поток_отдаёт_те_же_события(monkeypatch):
    события, _ = await прогнать(monkeypatch)

    имена = [с.name for с in события]
    assert имена[0] == "deal", "условия сделки — до первого слова ответа"
    assert "token" in имена
    assert имена[-1] == "done"


async def test_пул_из_одной_компании_разбирается(monkeypatch):
    """Одна компания в пуле — это разбор, а не «сравнивать не с чем»."""
    события, собранное = await прогнать(monkeypatch, записи=[ТЯЖЁЛАЯ])

    assert [с.name for с in события][-1] == "done"
    assert 'ООО "ТЯЖЁЛАЯ"' in собранное["prompt"]


async def test_смена_состава_пула_сбрасывает_переписку(monkeypatch):
    """Ответ про двоих не должен продолжаться как ответ про одну."""
    monkeypatch.setattr(
        loop.graph, "build", lambda *_, **__: ПодставнойАгент([кусок("Разберу.")])
    )
    состояние = loop.Session(session_id="т")

    async for _ in loop.run_pool_stream(состояние, ПУЛ, "кому отгружать?"):
        pass
    assert состояние.history, "ответ про пул должен попасть в переписку"

    async for _ in loop.run_pool_stream(состояние, [ЧИСТАЯ], "а ей?"):
        pass
    # Две реплики: вопрос и ответ этого прогона. Предыдущий пул забыт.
    assert len(состояние.history) == 2


async def test_тот_же_состав_переписку_не_сбрасывает(monkeypatch):
    """Иначе разговор о пуле начинался бы заново на каждом вопросе."""
    monkeypatch.setattr(
        loop.graph, "build", lambda *_, **__: ПодставнойАгент([кусок("Разберу.")])
    )
    состояние = loop.Session(session_id="т")

    async for _ in loop.run_pool_stream(состояние, ПУЛ, "кому отгружать?"):
        pass
    async for _ in loop.run_pool_stream(состояние, ПУЛ, "а если аванс?"):
        pass

    assert len(состояние.history) == 4


# ─────────────────────────── Инструменты ───────────────────────────


def контекст(записи=ПУЛ) -> graph.Context:
    отчёты = {з["baseInfo"]["inn"]: build(з) for з in записи}
    return graph.Context(
        records={з["baseInfo"]["inn"]: з for з in записи}, reports=отчёты
    )


@pytest.fixture
def в_пуле(monkeypatch):
    """Подменяет окружение выполнения: инструменты читают пул из него."""

    def подставить(записи=ПУЛ):
        среда = Runtime(context=контекст(записи))
        monkeypatch.setattr(tools, "get_runtime", lambda _: среда)
        return среда

    return подставить


def test_графика_в_пуле_нет_и_он_об_этом_говорит():
    """Интерфейс рисует график из загруженного отчёта, а на сравнении их нет."""
    имена = [т.name for т in tools.build_pool(ПУЛ)]
    assert "show_chart" not in имена
    assert "look_up" in имена


def test_инн_вне_пула_перечисляет_пул(в_пуле):
    в_пуле()

    ответ = tools.look_up.invoke({"topic": "налоги", "inn": "9999999999"})

    assert 'ООО "ЧИСТАЯ"' in ответ and 'ООО "ТЯЖЁЛАЯ"' in ответ
    assert "9999999999" in ответ


def test_без_инн_в_пуле_из_нескольких_тоже_перечисляет(в_пуле):
    """Промолчать нельзя: модель взяла бы данные наугад и приписала не той."""
    в_пуле()

    ответ = tools.look_up.invoke({"topic": "налоги"})

    assert "Назови ИНН компании" in ответ


def test_в_блоке_вызова_видно_у_какой_компании_взято(в_пуле):
    в_пуле()

    _, выхлоп = tools.look_up.func(topic="налоги", inn="7700000002")

    assert выхлоп["lookup"]["company"] == 'ООО "ТЯЖЁЛАЯ"'


def test_в_разборе_одной_компании_имени_не_приходит(в_пуле):
    """Там оно повторяет заголовок экрана и в ленте только шумит."""
    в_пуле([ЧИСТАЯ])

    _, выхлоп = tools.look_up.func(topic="налоги")

    assert "company" not in выхлоп["lookup"]

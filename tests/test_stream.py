"""Поток ответа.

Модель подменяется: проверяется поведение потока, а не качество ответа.
Контракт — `specs/006-chat-agent-tools/contracts/stream.md`.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import ToolMessage

from api.agent import events, loop
from api.main import app
from core.repo import load
from core.report import build

# Приложение читает подготовленный набор при старте — без него оно не поднимается
# намеренно: пустой набор выглядел бы как «у всех компаний ничего нет». В репозиторий
# набор не коммитится, поэтому тесты ручки пропускаются там, где его нет.
try:
    _ЕСТЬ_НАБОР = bool(load().counterparties)
except RuntimeError:
    _ЕСТЬ_НАБОР = False

нужен_набор = pytest.mark.skipif(not _ЕСТЬ_НАБОР, reason="набор не собран")

ОПОРНАЯ = "5032257375"

# Своя запись, а не из набора: набор в репозиторий не коммитится, и тест,
# требующий его, в CI не запустился бы.
ЗАПИСЬ = {
    "baseInfo": {
        "inn": ОПОРНАЯ,
        "shortName": 'ООО "МАКСМАРКЕТ"',
        "riskLevel": "LOW",
        "registrationInfo": {"yearsFromRegistration": 9},
    },
    "status": {"status": "CURRENT"},
    "zskRiskLevel": "GREEN",
    "reputationalRisks": {"negative": [], "positive": []},
}


def кусок(текст):
    return SimpleNamespace(content=текст, tool_call_chunks=[])


class ПодставнойАгент:
    """Отдаёт заготовленные куски. Ничего не ждёт и никуда не ходит."""

    def __init__(self, куски=(), ошибка=None):
        self.куски, self.ошибка = куски, ошибка

    def astream(self, *_, **__):
        async def поток():
            # Куски идут до отказа: так проверяется разница между «упал сразу»
            # и «упал посреди ответа» — во втором случае запасной путь брать уже
            # нельзя, пользователь текст уже прочитал.
            for к in self.куски:
                yield к, {}
            if self.ошибка:
                raise self.ошибка

        return поток()


async def прогнать(monkeypatch, агент, сессия=None):
    monkeypatch.setattr(loop.graph, "build", lambda *_, **__: агент)
    запись = ЗАПИСЬ
    отчёт = build(запись)
    состояние = сессия or loop.Session(session_id="т")
    поток = loop.run_stream(состояние, отчёт, запись, "Сколько производств?")
    return [с async for с in поток], состояние


async def test_текст_приходит_событиями(monkeypatch):
    события, _ = await прогнать(monkeypatch, ПодставнойАгент([кусок("54 актив"), кусок("ных")]))

    # `deal` первым: условия сделки уходят клиенту до первого слова ответа.
    assert [с.name for с in события] == ["deal", "token", "token", "check", "done"]


async def test_проверка_идёт_после_текста_а_не_до(monkeypatch):
    """Ответ уже прочитан к моменту, когда приходит отметка о том, чем он
    подтверждён. Задерживать ради проверки первое слово значило бы платить
    за неё задержкой всего ответа."""
    события, _ = await прогнать(monkeypatch, ПодставнойАгент([кусок("Компании 9 лет.")]))

    имена = [с.name for с in события]
    assert имена.index("check") > имена.index("token")
    проверка = события[имена.index("check")].data
    assert проверка["total"] == 1
    # Девять лет есть в отчёте — обращаться к модели было не за чем
    assert проверка["unverified"] == []
    assert проверка["checked"] is False


async def test_выдуманное_число_помечается(monkeypatch):
    """«Не выдумывает» — критерий приёмки кейса, и до сих пор он держался
    на одних формулировках промпта."""
    агент = ПодставнойАгент([кусок("Исков на 999 999 999 ₽.")])

    события, _ = await прогнать(monkeypatch, агент)

    проверка = next(с.data for с in события if с.name == "check")
    assert [c["number"] for c in проверка["unverified"]] == ["999 999 999"]


async def test_последнее_событие_всегда_done(monkeypatch):
    """Клиент по нему понимает, что ответ закончен, и снимает индикатор."""
    события, _ = await прогнать(monkeypatch, ПодставнойАгент([кусок("ответ")]))

    assert события[-1].name == "done"


async def test_отказ_модели_приходит_событием_а_не_обрывом(monkeypatch):
    """Заголовки ответа уже ушли к моменту отказа, кодом ответа сообщить нельзя.
    Уже показанный текст должен остаться на экране."""
    агент = ПодставнойАгент(ошибка=RuntimeError("провайдер лёг"))

    события, _ = await прогнать(monkeypatch, агент)

    assert [с.name for с in события] == ["deal", "error", "done"]
    assert "недоступен" in события[1].data["detail"]


async def test_отказ_первого_пути_переводит_на_запасной(monkeypatch):
    """Пользователь приходит за разбором, а не за отчётом о нашей инфраструктуре.
    Отказ модели должен доходить до него только тогда, когда путей не осталось."""
    from core.llm import Route

    monkeypatch.setattr(
        loop, "_routes", lambda: (Route("openrouter", "первая"), Route("openrouter", "вторая"))
    )
    построено = []

    def сборка(_tools, _system, provider="", model=""):
        построено.append(model)
        if len(построено) == 1:
            return ПодставнойАгент(ошибка=RuntimeError("модель легла"))
        return ПодставнойАгент([кусок("Ответ по отчёту.")])

    monkeypatch.setattr(loop.graph, "build", сборка)
    поток = loop.run_stream(loop.Session(session_id="т"), build(ЗАПИСЬ), ЗАПИСЬ, "Вопрос")
    события = [с async for с in поток]

    assert построено == ["первая", "вторая"]
    assert "error" not in [с.name for с in события]
    assert "".join(с.data["text"] for с in события if с.name == "token") == "Ответ по отчёту."


async def test_после_показанного_текста_запасной_путь_не_берётся(monkeypatch):
    """Показанный текст переиграть нельзя: второй ответ поверх первого читался бы
    как две разные оценки одной компании."""
    from core.llm import Route

    monkeypatch.setattr(
        loop, "_routes", lambda: (Route("openrouter", "а"), Route("openrouter", "б"))
    )
    построено = []

    def сборка(_tools, _system, provider="", model=""):
        построено.append(model)
        return ПодставнойАгент([кусок("Начал отвечать")], ошибка=RuntimeError("оборвалось"))

    monkeypatch.setattr(loop.graph, "build", сборка)
    поток = loop.run_stream(loop.Session(session_id="т"), build(ЗАПИСЬ), ЗАПИСЬ, "Вопрос")
    события = [с async for с in поток]

    assert построено == ["а"]
    assert [с.name for с in события if с.name == "error"] == ["error"]


async def test_молчание_первой_модели_переводит_на_следующую(monkeypatch):
    """Молчание — такой же отказ, как ошибка: рассуждение способно съесть весь
    бюджет ответа. Замерено на живом прогоне: один вопрос из десяти вернулся
    пустым и на повторе ответил нормально."""
    from core.llm import Route

    monkeypatch.setattr(
        loop, "_routes", lambda: (Route("openrouter", "а"), Route("openrouter", "б"))
    )
    построено = []

    def сборка(_tools, _system, provider="", model=""):
        построено.append(model)
        куски = [кусок("")] if len(построено) == 1 else [кусок("Ответ.")]
        return ПодставнойАгент(куски)

    monkeypatch.setattr(loop.graph, "build", сборка)
    поток = loop.run_stream(loop.Session(session_id="т"), build(ЗАПИСЬ), ЗАПИСЬ, "Вопрос")
    события = [с async for с in поток]

    assert построено == ["а", "б"]
    assert "error" not in [с.name for с in события]


async def test_пустой_ответ_это_ошибка_а_не_ответ(monkeypatch):
    """Рассуждение тратит токены из бюджета ответа и способно съесть его целиком.
    Проверено на живом вызове: при 500 токенах ответа `deepseek v4 flash` вернул
    пустую строку. Пустой ответ после показанного вызова инструмента выглядит
    как поломка, а не как «мне нечего сказать»."""
    события, _ = await прогнать(monkeypatch, ПодставнойАгент([кусок("")]))

    assert [с.name for с in события] == ["deal", "error", "done"]


async def test_ответ_запоминается_в_истории(monkeypatch):
    сессия = loop.Session(session_id="т")

    _, состояние = await прогнать(monkeypatch, ПодставнойАгент([кусок("54 штуки")]), сессия)

    assert состояние.history[-1] == {"role": "assistant", "content": "54 штуки"}


async def test_неудачный_ответ_в_историю_не_попадает(monkeypatch):
    """Иначе следующий вопрос уедет в модель вместе с пустотой."""
    сессия = loop.Session(session_id="т")

    await прогнать(monkeypatch, ПодставнойАгент(ошибка=RuntimeError("лёг")), сессия)

    assert сессия.history == []


async def test_вызов_инструмента_доходит_до_событий(monkeypatch):
    """Порядок из контракта: tool_start → chart → tool_end."""
    вызов = SimpleNamespace(
        content="",
        tool_call_chunks=[{"name": "show_chart", "args": '{"kind": "balance"}', "id": "1"}],
    )
    итог = ToolMessage(
        content="показан",
        tool_call_id="1",
        name="show_chart",
        artifact={"chart": {"chart": "balance", "inn": ОПОРНАЯ}},
    )

    события, _ = await прогнать(monkeypatch, ПодставнойАгент([вызов, итог, кусок("готово")]))

    assert [с.name for с in события] == [
        "deal",
        "tool_start",
        "chart",
        "tool_end",
        "token",
        "check",
        "done",
    ]


@нужен_набор
def test_ручка_отдаёт_поток(monkeypatch):
    monkeypatch.setattr("api.main.repo.by_inn", lambda inn: ЗАПИСЬ if inn == ОПОРНАЯ else None)

    async def подстава(*_, **__):
        yield events.Event("token", {"text": "привет"})
        yield events.Event("done", {"sections": []})

    monkeypatch.setattr(loop, "run_stream", подстава)

    with TestClient(app) as client:
        ответ = client.post(
            "/chat/stream", json={"message": "вопрос", "inn": ОПОРНАЯ, "session_id": "т"}
        )

    assert ответ.status_code == 200
    assert ответ.headers["content-type"].startswith("text/event-stream")
    # Подсказка для nginx: без неё поток копится в буфере и приходит целиком
    assert ответ.headers["x-accel-buffering"] == "no"
    assert "event: token" in ответ.text
    assert ответ.text.rstrip().endswith('data: {"sections": []}')


@нужен_набор
def test_неизвестный_инн_это_отказ_а_не_пустой_поток(monkeypatch):
    """Пустой поток неотличим от «у компании всё чисто»."""
    monkeypatch.setattr("api.main.repo.by_inn", lambda inn: ЗАПИСЬ if inn == ОПОРНАЯ else None)
    with TestClient(app) as client:
        ответ = client.post(
            "/chat/stream", json={"message": "вопрос", "inn": "0000000000", "session_id": "т"}
        )

    assert ответ.status_code == 404


@нужен_набор
def test_обычная_ручка_отдаёт_добытое_инструментами(monkeypatch):
    """`/chat` работает тем же агентом, что и поток, поэтому график и ссылки
    должны доезжать и до неё — иначе непотоковый клиент получит внешние сведения
    без ссылок, чего промпт не допускает.

    Ручка была без единого теста, и переезд на агента ловить было нечем.
    """
    monkeypatch.setattr("api.main.repo.by_inn", lambda inn: ЗАПИСЬ if inn == ОПОРНАЯ else None)

    async def подстава(*_, **__):
        return loop.Answer(
            text="Ответ",
            sections=("courts",),
            charts=("balance",),
            sources=({"title": "Т", "url": "https://x", "snippet": ""},),
        )

    monkeypatch.setattr(loop, "run", подстава)

    with TestClient(app) as client:
        ответ = client.post("/chat", json={"message": "вопрос", "inn": ОПОРНАЯ, "session_id": "т"})

    assert ответ.status_code == 200
    assert ответ.json() == {
        "answer": "Ответ",
        "sections": ["courts"],
        "charts": ["balance"],
        "sources": [{"title": "Т", "url": "https://x", "snippet": ""}],
        # То же, что в потоке приходит событиями `lookup` и `check`: без первого
        # клиент не увидит данные, на которые опирается ответ, без второго —
        # не отличит подтверждённое отчётом от неподтверждённого.
        "lookups": [],
        "check": {"total": 0, "unverified": [], "checked": False},
        # Условия сделки после хода: часть могла быть разобрана из самой реплики,
        # и клиент показывает пользователю, что у нас сохранилось.
        "deal": {"side": None, "scheme": None, "sum": None, "days": None, "goal": None},
    }


@нужен_набор
def test_обычная_ручка_отвечает_502_на_сбой_провайдера(monkeypatch):
    """Сбой сервиса нельзя выдавать за содержательный ответ о компании."""
    monkeypatch.setattr("api.main.repo.by_inn", lambda inn: ЗАПИСЬ if inn == ОПОРНАЯ else None)

    async def падает(*_, **__):
        raise RuntimeError("провайдер лёг")

    monkeypatch.setattr(loop, "run", падает)

    with TestClient(app) as client:
        ответ = client.post("/chat", json={"message": "вопрос", "inn": ОПОРНАЯ, "session_id": "т"})

    assert ответ.status_code == 502


async def test_событие_deal_несёт_разобранные_условия(monkeypatch):
    """Часть условий разбирается из самой реплики, и человек должен увидеть,
    что у нас сохранилось, раньше, чем прочтёт построенный на этом ответ."""
    monkeypatch.setattr(loop.graph, "build", lambda *_, **__: ПодставнойАгент([кусок("да")]))
    сессия = loop.Session(session_id="т")

    поток = loop.run_stream(
        сессия, build(ЗАПИСЬ), ЗАПИСЬ, "готов дать отсрочку 60 дней на 3 млн", []
    )
    события = [с async for с in поток]

    assert события[0].name == "deal"
    assert события[0].data["scheme"] == "deferral"
    assert события[0].data["days"] == 60
    assert события[0].data["sum"] == 3_000_000


def test_условия_из_запроса_доезжают_до_цикла(monkeypatch):
    """Форма над полем ввода — второй источник условий, наравне с репликой."""
    monkeypatch.setattr("api.main.repo.by_inn", lambda inn: ЗАПИСЬ if inn == ОПОРНАЯ else None)
    переданное = {}

    def подстава(состояние, отчёт, запись, вопрос, инструменты=None, сделка=None):
        переданное["сделка"] = сделка

        async def пусто():
            yield events.Event("done", {"sections": []})

        return пусто()

    monkeypatch.setattr(loop, "run_stream", подстава)

    with TestClient(app) as client:
        client.post(
            "/chat/stream",
            json={
                "message": "вопрос",
                "inn": ОПОРНАЯ,
                "session_id": "т",
                "deal": {"side": "supplier", "scheme": "prepay", "sum": 3000000, "days": 45},
            },
        )

    assert переданное["сделка"].side == "supplier"
    assert переданное["сделка"].scheme == "prepay"


def test_чужой_ключ_условий_отбрасывается(monkeypatch):
    """Значение не из словаря — ошибка клиента, а не сведение о сделке:
    в промпт оно уходить не должно."""
    monkeypatch.setattr("api.main.repo.by_inn", lambda inn: ЗАПИСЬ if inn == ОПОРНАЯ else None)
    переданное = {}

    def подстава(состояние, отчёт, запись, вопрос, инструменты=None, сделка=None):
        переданное["сделка"] = сделка

        async def пусто():
            yield events.Event("done", {"sections": []})

        return пусто()

    monkeypatch.setattr(loop, "run_stream", подстава)

    with TestClient(app) as client:
        client.post(
            "/chat/stream",
            json={"message": "вопрос", "inn": ОПОРНАЯ, "deal": {"side": "кто-то ещё"}},
        )

    assert переданное["сделка"].side is None

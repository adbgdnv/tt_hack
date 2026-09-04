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
from core import repo
from core.report import build

ОПОРНАЯ = "5032257375"


def кусок(текст):
    return SimpleNamespace(content=текст, tool_call_chunks=[])


class ПодставнойАгент:
    """Отдаёт заготовленные куски. Ничего не ждёт и никуда не ходит."""

    def __init__(self, куски=(), ошибка=None):
        self.куски, self.ошибка = куски, ошибка

    def astream(self, *_, **__):
        async def поток():
            if self.ошибка:
                raise self.ошибка
            for к in self.куски:
                yield к, {}

        return поток()


@pytest.fixture
def запись():
    return repo.by_inn(ОПОРНАЯ)


async def прогнать(monkeypatch, агент, сессия=None):
    monkeypatch.setattr(loop.graph, "build", lambda *_, **__: агент)
    запись = repo.by_inn(ОПОРНАЯ)
    отчёт = build(запись)
    состояние = сессия or loop.Session(session_id="т")
    поток = loop.run_stream(состояние, отчёт, запись, "Сколько производств?")
    return [с async for с in поток], состояние


async def test_текст_приходит_событиями(monkeypatch):
    события, _ = await прогнать(monkeypatch, ПодставнойАгент([кусок("54 актив"), кусок("ных")]))

    assert [с.name for с in события] == ["token", "token", "done"]


async def test_последнее_событие_всегда_done(monkeypatch):
    """Клиент по нему понимает, что ответ закончен, и снимает индикатор."""
    события, _ = await прогнать(monkeypatch, ПодставнойАгент([кусок("ответ")]))

    assert события[-1].name == "done"


async def test_отказ_модели_приходит_событием_а_не_обрывом(monkeypatch):
    """Заголовки ответа уже ушли к моменту отказа, кодом ответа сообщить нельзя.
    Уже показанный текст должен остаться на экране."""
    агент = ПодставнойАгент(ошибка=RuntimeError("провайдер лёг"))

    события, _ = await прогнать(monkeypatch, агент)

    assert [с.name for с in события] == ["error", "done"]
    assert "недоступен" in события[0].data["detail"]


async def test_пустой_ответ_это_ошибка_а_не_ответ(monkeypatch):
    """У gpt-oss рассуждение тратит токены из того же лимита и способно съесть
    весь бюджет. Пустой ответ после показанного вызова инструмента выглядит
    как поломка, а не как «мне нечего сказать»."""
    события, _ = await прогнать(monkeypatch, ПодставнойАгент([кусок("")]))

    assert [с.name for с in события] == ["error", "done"]


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

    assert [с.name for с in события] == ["tool_start", "chart", "tool_end", "token", "done"]


def test_ручка_отдаёт_поток(monkeypatch):
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


def test_неизвестный_инн_это_отказ_а_не_пустой_поток():
    """Пустой поток неотличим от «у компании всё чисто»."""
    with TestClient(app) as client:
        ответ = client.post(
            "/chat/stream", json={"message": "вопрос", "inn": "0000000000", "session_id": "т"}
        )

    assert ответ.status_code == 404

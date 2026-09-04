"""Трассировка вызовов модели.

Главное свойство здесь — не «работает», а «не ломает». Наблюдение за системой
не должно становиться её частью: диалог уже переживает недоступность провайдера
модели, и внешняя служба не может стать новым способом всё уронить.

Саму отправку записей не проверяем — это чужой код, и проверять его значит
проверять LangChain. Проверяем своё: что запись получает метаданные, по которым
её можно найти, и что настройки клиента не сделают отказ дороже.
"""

import os
from types import SimpleNamespace

import pytest

from core.llm import Answer, LLMClient, _environment


@pytest.fixture
def клиент(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "тестовый-ключ")
    return LLMClient()


class ЗаписанныйВызов:
    """Подставная модель: запоминает, с чем её позвали, и отвечает заготовкой."""

    def __init__(self, ответ=None, ошибка=None):
        self.ответ, self.ошибка = ответ, ошибка
        self.вызовы = []

    def invoke(self, messages, config=None, **_):
        self.вызовы.append((messages, config))
        if self.ошибка:
            raise self.ошибка
        return self.ответ


def заготовка(текст="Ответ по отчёту.", вход=1453, выход=51):
    return SimpleNamespace(
        text=текст,
        usage_metadata={"input_tokens": вход, "output_tokens": выход},
        response_metadata={"model_name": "openai/gpt-oss-20b"},
    )


def test_без_переменной_трассировка_выключена(monkeypatch):
    """Основной режим в тестах и CI: никуда не обращаемся, условий в коде не нужно."""
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    from langsmith import utils

    assert utils.tracing_is_enabled() is False


def test_тесты_не_создают_записей():
    """Прогон не должен мусорить в проекте и тратить квоту.

    Сторож не декоративный: он поймал, как `LANGSMITH_TRACING=true` из личного
    `.env` разработчика включал отправку записей на каждом прогоне. Выключением
    занимается conftest.
    """
    assert os.environ.get("LANGSMITH_TRACING") != "true"


def test_ответ_разбирается_с_токенами(клиент, monkeypatch):
    """Счётчики нужны не для красоты: по ним видно, съело ли бюджет рассуждение
    gpt-oss, из-за которого content приходит пустым."""
    модель = ЗаписанныйВызов(ответ=заготовка())
    monkeypatch.setattr(клиент, "_chat", lambda *_: модель)

    ответ = клиент.ask([{"role": "user", "content": "вопрос"}])

    assert ответ == Answer(
        content="Ответ по отчёту.",
        prompt_tokens=1453,
        completion_tokens=51,
        model="openai/gpt-oss-20b",
    )


def test_инн_и_окружение_уходят_в_запись(клиент, monkeypatch):
    """Без метаданных записи неразличимы: непонятно, о какой компании речь
    и пришёл ли вызов с сервера или с ноутбука."""
    модель = ЗаписанныйВызов(ответ=заготовка())
    monkeypatch.setattr(клиент, "_chat", lambda *_: модель)

    клиент.ask([{"role": "user", "content": "вопрос"}], inn="5032257375")

    _, config = модель.вызовы[0]
    assert config["metadata"] == {"environment": "local", "inn": "5032257375"}
    assert config["run_name"] == "counterparty-chat"


def test_упавшая_модель_не_вызывается_дважды(клиент, monkeypatch):
    """Отказ уходит наверх с первого раза.

    У клиента OpenAI повтор включён по умолчанию, и на лежащем провайдере
    пользователь ждал бы кратно дольше — молча, потому что повторяет библиотека.
    Решение о повторе принимает вызывающий, поэтому `max_retries=0`.
    """
    модель = ЗаписанныйВызов(ошибка=RuntimeError("провайдер лёг"))
    monkeypatch.setattr(клиент, "_chat", lambda *_: модель)

    with pytest.raises(RuntimeError):
        клиент.ask([{"role": "user", "content": "вопрос"}])

    assert len(модель.вызовы) == 1


def test_повторы_отключены_у_настоящего_клиента(клиент):
    """Предыдущий тест проверяет подставную модель — этот следит, что настройка
    не потерялась в настоящей."""
    assert клиент._chat(max_tokens=100, temperature=0.2).max_retries == 0


def test_окружение_различается(monkeypatch):
    """На сервере и локально записи должны быть отличимы одна от другой."""
    monkeypatch.delenv("API_ROOT_PATH", raising=False)
    assert _environment() == "local"
    monkeypatch.setenv("API_ROOT_PATH", "/api")
    assert _environment() == "server"

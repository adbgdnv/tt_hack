"""Выбор провайдера и запасной путь.

Отказ провайдера не должен доходить до пользователя ошибкой: он приходит
за разбором, а не за отчётом о нашей инфраструктуре. Живой провайдер здесь
не дёргается — проверяется только выбор пути.
"""

from __future__ import annotations

import pytest

from core import llm


@pytest.fixture(autouse=True)
def чистое_окружение(monkeypatch):
    for имя in ("LLM_PROVIDER", "LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY"):
        monkeypatch.setenv(имя, "")
        monkeypatch.delenv(имя, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "")


def test_без_ключей_путей_нет(monkeypatch):
    """Пустая цепочка — честный ответ. Попытка сходить к ненастроенному
    провайдеру стоила бы времени и всё равно кончилась бы ошибкой."""
    assert llm.chain() == ()


def test_обе_модели_openrouter_идут_раньше_groq(monkeypatch):
    """Отказ модели и отказ провайдера — разные события. Первое лечится сменой
    модели у того же провайдера, и это дешевле. Groq стоит последним намеренно:
    он слабее, и подгонять под него продукт больше не нужно."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-тест")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-тест")

    assert llm.chain() == (
        llm.Route("openrouter", "deepseek/deepseek-v4-flash"),
        llm.Route("openrouter", "z-ai/glm-5.3-flash"),
        llm.Route("groq"),
    )


def test_ненастроенный_провайдер_выпадает(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-тест")

    assert [r.provider for r in llm.chain()] == ["openrouter", "openrouter"]


def test_настройка_переставляет_порядок(monkeypatch):
    """Переключение основного провайдера не должно требовать правки кода."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-тест")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-тест")
    monkeypatch.setenv("LLM_PROVIDER", "groq")

    assert llm.chain()[0].provider == "groq"


def test_общий_ключ_принадлежит_названному_провайдеру(monkeypatch):
    """Так было до появления второго провайдера, и старая настройка обязана
    работать. Отдавать общий ключ любому провайдеру нельзя — ключ Groq ушёл бы
    в OpenRouter."""
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_API_KEY", "gsk-тест")

    assert llm.key_for("groq") == "gsk-тест"
    assert llm.key_for("openrouter") == ""


def test_без_ключа_клиент_говорит_какую_переменную_задать(monkeypatch):
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        llm.LLMClient(provider="openrouter")


def test_глубина_рассуждения_задаётся_только_там_где_её_понимают(monkeypatch):
    """У gpt-oss рассуждение тратится из бюджета ответа и требует ограничения.
    У моделей OpenRouter такого параметра нет, и посылать его туда нельзя."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-тест")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-тест")

    assert llm.LLMClient(provider="groq").reasoning == "low"
    assert llm.LLMClient(provider="openrouter").reasoning is None


def test_запасная_модель_не_подменяется_настройкой(monkeypatch):
    """`LLM_MODEL` переопределяет модель основного пути. Применить его
    к запасному значит подсунуть провайдеру чужую модель."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-тест")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-тест")
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_MODEL", "своя/модель")

    assert llm.LLMClient(provider="groq").model == "своя/модель"
    assert llm.LLMClient(provider="openrouter").model == "deepseek/deepseek-v4-flash"

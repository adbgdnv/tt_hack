"""Трассировка вызовов модели.

Главное свойство здесь — не «работает», а «не ломает». Наблюдение за системой
не должно становиться её частью: диалог уже переживает недоступность провайдера
модели, и внешняя служба не может стать новым способом всё уронить.
"""

import os
from types import SimpleNamespace

import pytest

from core import llm
from core.llm import Answer, LLMClient, _environment


@pytest.fixture
def клиент(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "тестовый-ключ")
    return LLMClient()


@pytest.fixture
def трассировка_включена(monkeypatch):
    """Включаем подменой, а не переменной окружения.

    Контекст трассировки библиотека захватывает один раз на процесс: первый же
    вызов `tracing_is_enabled()` фиксирует состояние, и позднее изменение переменной
    уже не действует. На сервере это не мешает — окружение задано до старта, — но
    переключить на лету нельзя, и тест, полагающийся на setenv, зависел бы
    от порядка прогона.
    """
    monkeypatch.setattr("core.llm.langsmith_utils.tracing_is_enabled", lambda: True)
    # Настоящий декоратор создаёт запись и отправляет её по сети. В тестах это
    # и лишний поход наружу, и мусор в проекте — подменяем сквозным.
    monkeypatch.setattr("core.llm.traceable", lambda **_: (lambda fn: fn))


def test_без_переменной_трассировка_выключена(monkeypatch):
    """Основной режим в тестах и CI: никуда не обращаемся, условий в коде не нужно."""
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    from langsmith import utils

    assert utils.tracing_is_enabled() is False


def test_вызов_проходит_при_выключенной_трассировке(клиент, monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    вызовов = []

    def подмена(messages, max_tokens, temperature):
        вызовов.append(messages)
        return Answer(content="ответ")

    monkeypatch.setattr(клиент, "_call", подмена)
    assert клиент.ask([{"role": "user", "content": "вопрос"}]).content == "ответ"
    assert len(вызовов) == 1


def test_сбой_настройки_трассировки_не_роняет_вызов(клиент, monkeypatch, трассировка_включена):
    """Настройка записи упала — вызов всё равно уходит, пользователь получает ответ."""
    def падающая_настройка(**_):
        raise RuntimeError("сломалось")

    monkeypatch.setattr("core.llm.traceable", падающая_настройка)
    monkeypatch.setattr(клиент, "_call", lambda *_: Answer(content="ответ"))
    assert клиент.ask([{"role": "user", "content": "вопрос"}]).content == "ответ"


def test_упавшая_модель_не_вызывается_дважды(клиент, monkeypatch, трассировка_включена):
    """Оборачивать сам вызов в try нельзя: упавшую модель это превратило бы
    в повторный запрос, а пользователь получил бы поведение, которого не просил."""
    попытки = []

    def падающий(*_):
        попытки.append(1)
        raise RuntimeError("провайдер недоступен")

    monkeypatch.setattr(клиент, "_call", падающий)
    with pytest.raises(RuntimeError):
        клиент.ask([{"role": "user", "content": "вопрос"}])
    assert len(попытки) == 1, "модель вызвана повторно — трассировка проглотила ошибку"


def test_окружение_различается(monkeypatch):
    """Записи с ноутбука и с сервера должны быть различимы без чтения содержимого."""
    monkeypatch.delenv("API_ROOT_PATH", raising=False)
    assert _environment() == "local"
    monkeypatch.setenv("API_ROOT_PATH", "/api")
    assert _environment() == "server"


def test_инн_передаётся_в_запись(клиент, monkeypatch, трассировка_включена):
    """Иначе вызов не связать с отчётом, о котором шла речь."""
    записано = {}

    def подмена_traceable(**kwargs):
        записано.update(kwargs.get("metadata") or {})
        return lambda fn: fn

    monkeypatch.setattr("core.llm.traceable", подмена_traceable)
    monkeypatch.setattr(клиент, "_call", lambda *_: Answer(content="ответ"))
    клиент.ask([{"role": "user", "content": "в"}], inn="5032257375")
    assert записано["inn"] == "5032257375"


def test_тесты_не_создают_записей():
    """Прогон не должен мусорить в проекте и тратить квоту."""
    assert os.environ.get("LANGSMITH_TRACING") != "true"


def test_счётчик_токенов_уходит_в_запись(monkeypatch):
    """Токены надо переложить руками — сами они в запись не попадают.

    Наблюдатель ищет `usage_metadata` в корне результата, а результат у нас —
    объект `Answer`, и счётчики лежат на уровень глубже. Без перекладывания записи
    приходят с нулями: проверено на живом ключе, было `0 (вход 0, выход 0)`.
    """
    дерево = SimpleNamespace(metadata={})
    monkeypatch.setattr("core.llm.get_current_run_tree", lambda: дерево)

    llm._report_usage({"prompt_tokens": 1453, "completion_tokens": 51})

    assert дерево.metadata["usage_metadata"] == {
        "input_tokens": 1453,
        "output_tokens": 51,
        "total_tokens": 1504,
    }


def test_вне_трассировки_счётчик_никуда_не_пишется(monkeypatch):
    """Дерева вызовов нет — значит и складывать некуда. Падать при этом нельзя:
    основной режим работы продукта именно такой."""
    monkeypatch.setattr("core.llm.get_current_run_tree", lambda: None)

    llm._report_usage({"prompt_tokens": 10, "completion_tokens": 5})  # не падает

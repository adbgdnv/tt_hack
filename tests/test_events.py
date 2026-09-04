"""Перевод потока агента в события контракта.

Проверяется на заготовках кусков, без обращения к модели: нас интересует разбор,
а не качество ответа. Контракт — `specs/006-chat-agent-tools/contracts/stream.md`.
"""

import json
from types import SimpleNamespace

from langchain_core.messages import ToolMessage

from api.agent import events
from core.charts import ChartSpec, Series

ГРАФИКИ = {
    "arbitration_years": ChartSpec(
        key="arbitration_years",
        title="Суммы исков по годам",
        form="lines",
        labels=("2023", "2024"),
        series=(Series(name="Как ответчик", unit="₽", values=(0, 2589790444)),),
        source="arbitrationByStatus",
    )
}


def кусок_текста(текст):
    return SimpleNamespace(content=текст, tool_call_chunks=[])


def кусок_вызова(имя, аргументы, идентификатор="1"):
    вызов = {"name": имя, "args": аргументы, "id": идентификатор}
    return SimpleNamespace(content="", tool_call_chunks=[вызов])


def итог(имя="show_chart", ошибка=False, добавка=None):
    """Настоящий ToolMessage, а не подделка: перевод опознаёт итог по типу."""
    return ToolMessage(
        content="готово",
        tool_call_id="1",
        name=имя,
        status="error" if ошибка else "success",
        artifact=добавка,
    )


def перевести(куски):
    """Перевод помнит состояние между кусками, поэтому один экземпляр на прогон."""
    перевод = events.Translator(ГРАФИКИ)
    return [с for кусок in куски for с in перевод.feed(кусок)]


def test_текст_становится_токенами():
    события = перевести([кусок_текста("54 актив"), кусок_текста("ных")])
    assert [(с.name, с.data["text"]) for с in события] == [
        ("token", "54 актив"),
        ("token", "ных"),
    ]


def test_вызов_инструмента_объявляется_по_человечески():
    """Пользователь читает ленту, а не отладочный вывод: имя функции с аргументами
    показывать нельзя. Название графика берётся то же, что на дашборде."""
    события = перевести([кусок_вызова("show_chart", '{"kind": "arbitration_years"}')])
    assert события[0].name == "tool_start"
    assert события[0].data["title"] == "Строю график «Суммы исков по годам»"


def test_аргументы_приходят_кусками_и_могут_быть_неполными():
    """Имя инструмента приходит в первом куске, аргументы дособираются в следующих.
    На момент объявления вызова разобрать их может не получиться — это не повод
    падать, обходимся общей фразой."""
    события = перевести([кусок_вызова("show_chart", '{"kind": "arbitr')])
    assert события[0].data["title"] == "Строю график"


def test_один_вызов_объявляется_один_раз():
    """Последующие куски того же вызова несут только аргументы — второе
    объявление в ленте выглядело бы как два вызова вместо одного."""
    события = перевести(
        [
            кусок_вызова("show_chart", '{"kind":', "abc"),
            кусок_вызова("show_chart", '"balance"}', "abc"),
        ]
    )
    assert sum(1 for с in события if с.name == "tool_start") == 1


def test_порядок_событий_вызова():
    """Контракт: tool_start → chart → tool_end."""
    события = перевести(
        [
            кусок_вызова("show_chart", '{"kind": "arbitration_years"}'),
            итог(добавка={"chart": {"chart": "arbitration_years", "inn": "5032257375"}}),
        ]
    )
    assert [с.name for с in события] == ["tool_start", "chart", "tool_end"]
    assert события[1].data == {"chart": "arbitration_years", "inn": "5032257375"}


def test_событие_графика_несёт_только_ключ():
    """Данные графика интерфейс берёт из уже загруженного отчёта. Так числа
    в чате физически не могут разойтись с дашбордом."""
    события = перевести([итог(добавка={"chart": {"chart": "balance", "inn": "1"}})])
    график = next(с for с in события if с.name == "chart")
    assert set(график.data) == {"chart", "inn"}


def test_ошибка_инструмента_не_проглатывается():
    """Инструмент, который тихо ничего не сделал, неотличим от сработавшего,
    и следующий за ним текст модели читается как подтверждённый."""
    события = перевести([итог(ошибка=True)])
    assert события[-1].name == "tool_end"
    assert события[-1].data["ok"] is False


def test_неудачный_вызов_не_рисует_график():
    события = перевести([итог(ошибка=True, добавка={"chart": {"chart": "balance", "inn": "1"}})])
    assert [с.name for с in события] == ["tool_end"]


def test_событие_кодируется_по_формату_sse():
    закодировано = events.Event("token", {"text": "привет"}).encode()
    assert закодировано.startswith("event: token\ndata: ")
    assert закодировано.endswith("\n\n")
    assert json.loads(закодировано.split("data: ")[1])["text"] == "привет"

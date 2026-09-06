"""MCP-сервер.

Проверяется, что объявлено и что отвечает, а не как считает ядро: у ядра
свои тесты. Спека — `specs/015-mcp-server/spec.md`.

Инструменты зовутся напрямую: `mcp.tool()` регистрирует функцию и возвращает
её же. Поднимать транспорт в каждом тесте значило бы проверять библиотеку.
"""

import json

import pytest

from core import compare as compare_core
from core import repo
from mcp_server import server

# Сервер читает подготовленный набор. В репозиторий набор не коммитится,
# поэтому там, где его нет, тесты пропускаются — как и у ручек.
try:
    _ЕСТЬ_НАБОР = bool(repo.load().counterparties)
except RuntimeError:
    _ЕСТЬ_НАБОР = False

нужен_набор = pytest.mark.skipif(not _ЕСТЬ_НАБОР, reason="набор не собран")

МАКСМАРКЕТ = "5032257375"
ТЕХПРОМ = "9714079997"
АЛЬЯНС = "7704310756"
# У этой компании два раздела без данных — на ней проверяется, что «проверять
# было нечем» не выдаётся за «проверили и чисто».
БЕЗ_ДАННЫХ = "9727128465"


# ─────────────────────────── Объявления ───────────────────────────


def test_ни_один_инструмент_не_отвечает_отказом():
    """Пустой инструмент хуже отсутствующего: клиент видит его и зовёт."""
    for инструмент in server.mcp._tool_manager.list_tools():
        функция = getattr(server, инструмент.name)
        источник = функция.__code__.co_consts
        assert NotImplementedError not in источник, f"{инструмент.name} — заглушка"


def test_объявлены_все_инструменты_контракта():
    имена = {и.name for и in server.mcp._tool_manager.list_tools()}
    assert имена == {
        "search_counterparty",
        "get_counterparty_report",
        "assess_risk",
        "find_contradictions",
        "compare_counterparties",
        "get_financials",
        "look_up",
        "verify_claims",
    }


def test_описание_тем_перечисляет_темы():
    """Описание доходит до модели в любом клиенте: наш промпт туда не едет."""
    описание = server.mcp._tool_manager.get_tool("look_up").description
    assert "финансы" in описание and "налоги" in описание


def test_в_сервере_нет_импортов_приложения():
    """Принцип II конституции: удали src/api — сервер работает."""
    исходник = server.__file__
    with open(исходник, encoding="utf-8") as f:
        текст = f.read()
    assert "from api" not in текст and "import api" not in текст


# ─────────────────────────── Разбор рисков ───────────────────────────


@нужен_набор
def test_разбор_рисков_называет_противоречия():
    итог = server.assess_risk(МАКСМАРКЕТ)

    заголовки = [п["title"] for п in итог["contradictions"]]
    assert заголовки, "у опорного примера противоречия есть"
    # У каждого — значения, на которых оно построено: без них модель
    # пересказывает вывод, а проверить его нечем.
    assert all(п["evidence"] for п in итог["contradictions"])


@нужен_набор
def test_в_разборе_рисков_нет_балла():
    """Кейсодатель: ранжирование в виде скора не требуется."""
    итог = server.assess_risk(МАКСМАРКЕТ)

    assert "score" not in итог
    assert not any("score" in str(к).lower() for к in итог)


@нужен_набор
def test_раздел_без_данных_попадает_в_пробелы_а_не_в_чистые():
    """«Проверили и чисто» и «проверять было нечем» — разные вещи.

    Замерено: компания проходит 14 проверок из 14 при двух разделах без
    данных и читается как безупречная.
    """
    итог = server.assess_risk(БЕЗ_ДАННЫХ)

    пустые = [р["title"] for р in итог["sections"] if р["state"] == "empty"]
    assert пустые, "тест опирается на компанию с пустыми разделами"
    assert итог["gaps"] == пустые


@нужен_набор
def test_неизвестная_оценка_помечена_а_не_подменена():
    """`known=False` — «оценить невозможно», а не низкий риск."""
    итог = server.assess_risk(МАКСМАРКЕТ)

    for оценка in (итог["bank_risk"], итог["zsk_risk"]):
        assert set(оценка) == {"source", "value", "known"}


@нужен_набор
def test_противоречия_отдельным_инструментом_те_же():
    """Два имени одного вопроса разошлись бы в первый же день."""
    assert (
        server.find_contradictions(МАКСМАРКЕТ)["contradictions"]
        == server.assess_risk(МАКСМАРКЕТ)["contradictions"]
    )


# ─────────────────────────── Сравнение ───────────────────────────


@нужен_набор
def test_порядок_сравнения_тот_же_что_на_экране():
    итог = server.compare_counterparties([ТЕХПРОМ, МАКСМАРКЕТ, АЛЬЯНС])

    ожидаемый = [в.inn for в in compare_core.compare([repo.by_inn(и) for и in
                                                      (ТЕХПРОМ, МАКСМАРКЕТ, АЛЬЯНС)])]
    assert [в["inn"] for в in итог["verdicts"]] == ожидаемый


@нужен_набор
def test_в_сравнении_нет_балла():
    итог = server.compare_counterparties([ТЕХПРОМ, МАКСМАРКЕТ])

    for вердикт in итог["verdicts"]:
        assert "score" not in вердикт
        assert not isinstance(вердикт["level"], int | float)


@нужен_набор
def test_ненайденные_названы_а_не_выброшены():
    итог = server.compare_counterparties([МАКСМАРКЕТ, "0000000000"])

    assert итог["not_found"] == ["0000000000"]
    assert len(итог["verdicts"]) == 1


def test_перебор_пула_отклоняется_числом():
    итог = server.compare_counterparties([str(и) * 10 for и in range(9)])

    assert итог["error"] == "too_many"
    assert str(compare_core.ПРЕДЕЛ_ПУЛА) in итог["detail"]


def test_предел_пула_берётся_из_ядра_а_не_вписан(monkeypatch):
    """Иначе он разъедется с вебом при первой же правке: там он из ядра."""
    monkeypatch.setattr(compare_core, "ПРЕДЕЛ_ПУЛА", 2)

    итог = server.compare_counterparties([МАКСМАРКЕТ, ТЕХПРОМ, АЛЬЯНС])

    assert итог["error"] == "too_many"
    assert "2" in итог["detail"]


# ─────────────────────────── Темы и финансы ───────────────────────────


@нужен_набор
def test_тема_отдаёт_данные():
    итог = server.look_up(МАКСМАРКЕТ, "налоги")

    assert "text" in итог and итог["text"]


@нужен_набор
def test_неизвестная_тема_перечисляет_доступные():
    """Пустота заполняется правдоподобным, поэтому пустоты быть не должно."""
    итог = server.look_up(МАКСМАРКЕТ, "погода")

    assert "text" not in итог
    assert "финансы" in итог["topics"]


@нужен_набор
def test_финансы_различают_нет_отчётности_и_ноль():
    итог = server.get_financials(МАКСМАРКЕТ)

    assert итог["reports_filed"] is True
    assert "is_entrepreneur" in итог


@нужен_набор
def test_у_ип_отчётности_не_бывает():
    """50 из 200 — ИП. Про них ответ «у ИП такого не бывает», а не «данных нет»."""
    # ИП опознаётся по названию: отдельного поля в выгрузке нет — то же
    # правило, что в `report._is_entrepreneur`.
    ип = next(
        (
            з
            for з in repo.all()
            if str((з.get("baseInfo") or {}).get("shortName") or "").startswith("ИП")
        ),
        None,
    )
    if ип is None:
        pytest.skip("в наборе нет ИП")

    итог = server.get_financials(ип["baseInfo"]["inn"])

    assert итог["is_entrepreneur"] is True


# ─────────────────────────── Проверка чисел ───────────────────────────


@нужен_набор
def test_настоящее_подтверждается_выдуманное_нет():
    итог = server.verify_claims("выручка 116 257 852 000 ₽, а судов 900", [МАКСМАРКЕТ])

    assert итог["total"] == 2
    # Строкой, а не числом: показываем ровно то, что написала модель.
    assert [c["number"] for c in итог["unverified"]] == ["900"]


@нужен_набор
def test_числа_сверяются_со_всеми_названными_отчётами():
    """С одним отчётом настоящее число второй компании стало бы «выдуманным»."""
    итог = server.verify_claims("выручка 116 257 852 000 ₽", [ТЕХПРОМ, МАКСМАРКЕТ])

    assert итог["unverified"] == []


@нужен_набор
def test_ответ_без_чисел_не_подтверждён_а_не_проверен():
    итог = server.verify_claims("компания выглядит неплохо", [МАКСМАРКЕТ])

    assert итог["total"] == 0
    assert итог["confirmed"] == 0


# ─────────────────────────── Ненайденное ───────────────────────────


@нужен_набор
@pytest.mark.parametrize(
    "вызов",
    [
        lambda: server.assess_risk("0000000000"),
        lambda: server.find_contradictions("0000000000"),
        lambda: server.get_counterparty_report("0000000000"),
        lambda: server.get_financials("0000000000"),
        lambda: server.look_up("0000000000", "налоги"),
        lambda: server.verify_claims("текст", ["0000000000"]),
    ],
)
def test_ненайденное_это_ответ_а_не_исключение(вызов):
    """Исключение доходит до клиента как поломка и обрывает разговор."""
    assert вызов()["error"] == "not_found"


# ─────────────────────────── Ресурс ───────────────────────────


@нужен_набор
def test_ресурс_отдаёт_отчёт_разбираемым():
    """Клиент подкладывает его в контекст сам — значит это должен быть JSON,
    а не пересказ."""
    данные = json.loads(server.counterparty_resource(МАКСМАРКЕТ))

    assert данные["инн"] == МАКСМАРКЕТ


@нужен_набор
def test_ресурс_на_ненайденном_не_падает():
    данные = json.loads(server.counterparty_resource("0000000000"))

    assert данные["error"] == "not_found"

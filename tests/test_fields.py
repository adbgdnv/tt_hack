"""Словарь полей.

Проверяется не содержимое описаний — они дословно из спецификации кейсодателя, —
а то, что словарь покрывает всё, что продукт показывает, и что происхождение
каждой формулировки видно.
"""

import re

import pytest

from core import fields


def test_словарь_собран():
    словарь = fields.load()

    assert словарь["meta"]["полей"] == 114
    assert словарь["meta"]["из_спецификации"] == 103
    assert словарь["meta"]["своих"] == 11
    # поле без описания — это поле, про которое мы ничего не можем сказать
    assert словарь["meta"]["без_описания"] == 0


def test_у_каждой_статьи_есть_происхождение():
    """Пользователь и мы должны различать, где формулировка кейсодателя,
    а где наша: за первую отвечает он, за вторую мы."""
    for путь, статья in fields.load()["fields"].items():
        assert статья["origin"] in {"spec", "own"}, путь
        assert статья["label"], путь


def test_подпись_собирается_словами():
    подпись = fields.describe([
        "finReports[].assets.currentAssets.stocks",
        "finReports[].assets.currentAssets.receivables",
        "finReports[].assets.currentAssets.bankroll",
    ])

    assert подпись == "Запасы, Дебиторская задолженность, Денежные средства"
    assert "[]" not in подпись


def test_повторы_в_подписи_схлопываются():
    """Два поля с одной подписью не должны давать «Выручка, Выручка»."""
    assert fields.describe(["finReports[].common.proceeds"] * 2) == "Выручка"


def test_неизвестный_путь_возвращается_как_есть():
    """Подставить выдуманное название хуже, чем показать путь: по пути хотя бы
    видно, что описания нет."""
    assert fields.label("выдуманный.путь") == "выдуманный.путь"


def test_расхождения_спецификации_с_данными_зафиксированы():
    """Молча разрешить расхождение в пользу одной из сторон значит лишить
    следующего читателя способа о нём узнать."""
    расхождения = fields.conflicts()

    assert "status.reasonName" in расхождения
    assert "Причина закрытия" in расхождения["status.reasonName"]
    assert "foundersInfo.cofounders[].active" in расхождения


def test_заполненность_известна_по_каждому_полю():
    """Чтобы не построить правило на поле, заполненном у трёх компаний,
    не заметив этого."""
    assert fields.filled("status.reasonName") == 6
    assert fields.filled("baseInfo.inn") == 200


def test_подписи_графиков_не_содержат_путей():
    """Требование FR-013. До этой фичи под графиком стояло
    `finReports[].assets.currentAssets.{stocks,receivables,bankroll}`."""
    from core.charts import build_charts
    from core.repo import load

    try:
        записи = load().counterparties
    except Exception:  # noqa: BLE001
        pytest.skip("набор не собран")

    проверено = 0
    for запись in записи:
        for график in build_charts(запись):
            проверено += 1
            assert not re.search(r"\[\]|\{|[a-zA-Z]\.[a-zA-Z]", график.source), график.source
    assert проверено > 500


def test_словарь_читается_один_раз():
    """Файл в рантайме не меняется, а читать его на каждый отчёт значит
    разбирать JSON на каждый показ страницы."""
    fields.load.cache_clear()
    первый = fields.load()
    assert fields.load() is первый

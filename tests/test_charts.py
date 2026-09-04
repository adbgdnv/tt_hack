"""Описания графиков: когда они создаются и когда нет.

Правила достаточности данных проверяются прогоном по всем двумстам компаниям:
график из одной точки выглядит как обычный график, а пустая рамка — как поломка
вёрстки. Глазами такое ловится случайно.
"""

import pytest

from core.charts import Series, build_charts, series_chart, snapshot_chart
from core.repo import load

# ─────────────────────────── правила достаточности ───────────────────────────


def test_ряд_из_одной_точки_графиком_не_становится():
    """Одна точка создаёт впечатление динамики, которой нет."""
    assert series_chart(
        key="revenue_assets",
        title="Выручка",
        labels=["2025"],
        series=[Series(name="Выручка", unit="₽", values=[100])],
        source="finReports",
    ) is None


def test_ряд_из_двух_точек_график_даёт():
    chart = series_chart(
        key="revenue_assets",
        title="Выручка",
        labels=["2024", "2025"],
        series=[Series(name="Выручка", unit="₽", values=[100, 200])],
        source="finReports",
    )
    assert chart is not None
    assert chart.form == "lines"
    assert len(chart.labels) == len(chart.series[0].values)


def test_ряд_без_значений_графиком_не_становится():
    assert series_chart(
        key="revenue_assets",
        title="Выручка",
        labels=["2024", "2025"],
        series=[Series(name="Выручка", unit="₽", values=[None, None])],
        source="finReports",
    ) is None


def test_срез_без_второй_величины_графиком_не_становится():
    assert snapshot_chart(
        key="balance",
        title="Баланс",
        pairs=[("Капитал", 100), ("Обязательства", None)],
        unit="₽",
        source="finReports",
    ) is None


def test_срез_с_нулём_график_даёт():
    """«В этой роли не судилась» и «данных о роли нет» — разные утверждения."""
    chart = snapshot_chart(
        key="plaintiff_defendant",
        title="Роль в судах",
        pairs=[("Как истец", 0), ("Как ответчик", 5_000_000)],
        unit="₽",
        source="arbitrationByStatus",
    )
    assert chart is not None
    assert chart.series[0].values == (0, 5_000_000)


def test_описание_несёт_основание():
    """Пользователь должен уметь проверить цифру."""
    chart = snapshot_chart(
        key="proceedings",
        title="Производства",
        pairs=[("Активные", 3), ("Завершённые", 7)],
        unit="",
        source="executionProceedings",
    )
    assert chart.source


# ─────────────────────────── инварианты на настоящем наборе ───────────────────────────

try:
    _RECORDS = load().counterparties
except RuntimeError:
    _RECORDS = ()

нужен_набор = pytest.mark.skipif(not _RECORDS, reason="набор не собран")


@нужен_набор
def test_ни_одного_графика_из_одной_точки_на_всех_компаниях():
    for record in _RECORDS:
        for chart in build_charts(record):
            assert len(chart.labels) >= 2, f"{chart.key}: одна точка"
            for s in chart.series:
                assert len(s.values) == len(chart.labels)


@нужен_набор
def test_ни_одного_описания_без_значений():
    for record in _RECORDS:
        for chart in build_charts(record):
            assert any(v is not None for s in chart.series for v in s.values), chart.key


@нужен_набор
def test_покрытие_совпадает_с_замерами():
    """Цифры из спеки должны сходиться с реальностью, иначе отбор графиков
    строился на неверных данных."""
    from collections import Counter

    счёт = Counter(c.key for r in _RECORDS for c in build_charts(r))
    с_графиком = sum(1 for r in _RECORDS if build_charts(r))
    assert счёт["plaintiff_defendant"] == 160
    assert счёт["balance"] == 134
    assert счёт["revenue_assets"] == 121
    assert счёт["proceedings"] == 96
    assert счёт["arbitration_years"] == 61
    assert с_графиком == 178, f"хотя бы один график у {с_графиком} компаний, ожидалось 178"


@нужен_набор
def test_у_предпринимателей_нет_финансовых_графиков():
    for record in _RECORDS:
        имя = str((record.get("baseInfo") or {}).get("shortName", ""))
        if имя.startswith("ИП"):
            ключи = {c.key for c in build_charts(record)}
            assert "revenue_assets" not in ключи
            assert "balance" not in ключи


@нужен_набор
def test_числа_на_графике_совпадают_с_фактами_раздела():
    """Иначе экран противоречит сам себе: в списке одна выручка, на графике другая."""
    from core.report import build

    сверено = 0
    for record in _RECORDS:
        for section in build(record).sections:
            факты = {f.label: f.value for f in section.facts}
            for chart in section.charts:
                if chart.key != "revenue_assets" or "Выручка" not in факты:
                    continue
                последняя = chart.series[0].values[-1]
                assert последняя == факты["Выручка"], (
                    f"{record['baseInfo']['inn']}: на графике {последняя}, "
                    f"в фактах {факты['Выручка']}"
                )
                сверено += 1
    assert сверено > 50, f"сверено всего {сверено} компаний — проверка почти ничего не поймала"


@нужен_набор
def test_годы_идут_по_возрастанию():
    """В выгрузке отчёты лежат от свежего к старому — на графике так читать нельзя."""
    for record in _RECORDS:
        for chart in build_charts(record):
            if chart.form != "lines":
                continue
            годы = [int(label) for label in chart.labels]
            assert годы == sorted(годы), f"{chart.key}: {годы}"


@нужен_набор
def test_ноль_отличается_от_отсутствия_в_ролях():
    """Компания без исков в роли истца получает столбец нулевой высоты,
    а не отсутствие столбца."""
    нулевые = 0
    for record in _RECORDS:
        for chart in build_charts(record):
            if chart.key == "plaintiff_defendant":
                assert len(chart.series[0].values) == 2
                нулевые += any(v == 0 for v in chart.series[0].values)
    assert нулевые > 0, "ни одной компании с нулём в роли — проверка бессмысленна"

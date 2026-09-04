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
            # Подпись факта несёт год («Выручка за 2025»), поэтому ищем по началу.
            выручка = next(
                (f.value for f in section.facts if f.label.startswith("Выручка")), None
            )
            прибыль = next(
                (f.value for f in section.facts if f.label.startswith("Прибыль")), None
            )
            for chart in section.charts:
                ожидание = {"revenue_assets": выручка, "profit_years": прибыль}.get(chart.key)
                if ожидание is None:
                    continue
                последняя = chart.series[0].values[-1]
                assert последняя == ожидание, (
                    f"{record['baseInfo']['inn']} / {chart.key}: "
                    f"на графике {последняя}, в фактах {ожидание}"
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


# ─────────────────────────── новые виды ───────────────────────────


def запись_с_отчётностью(**assets_liabilities) -> dict:
    """Юрлицо с двумя годами отчётности — основа для финансовых графиков."""
    return {
        "baseInfo": {"inn": "7704310756", "shortName": 'ООО "ТЕСТ"'},
        "finReports": [
            {"common": {"year": 2025, "proceeds": 200, "profit": -50}, **assets_liabilities},
            {"common": {"year": 2024, "proceeds": 100, "profit": 10}},
        ],
    }


def test_прибыль_рисуется_отдельным_графиком_и_уходит_в_минус():
    """Из 179 значений прибыли 23 отрицательные. Убыток — обычное значение,
    а не сбой, и он обязан попасть на график."""
    spec = next(c for c in build_charts(запись_с_отчётностью()) if c.key == "profit_years")

    assert spec.series[0].values == (10.0, -50.0)


def test_состав_оборотных_активов_пропускает_неназванное():
    """Отсутствующая часть — не ноль: «запасов нет» и «про запасы не сказано»
    разные утверждения, и второе мы сказать не можем."""
    запись = запись_с_отчётностью(assets={"currentAssets": {"receivables": 700, "bankroll": 300}})

    spec = next(c for c in build_charts(запись) if c.key == "asset_mix")

    assert spec.labels == ("Дебиторка", "Деньги")  # «Запасы» не выдуманы нулём
    assert spec.series[0].values == (700.0, 300.0)


def test_одна_часть_состава_не_график():
    """Одно число — это число, а не состав."""
    запись = запись_с_отчётностью(assets={"currentAssets": {"bankroll": 300}})

    assert not [c for c in build_charts(запись) if c.key == "asset_mix"]


def test_состав_из_одних_нулей_не_рисуется():
    запись = запись_с_отчётностью(assets={"currentAssets": {"stocks": 0, "bankroll": 0}})

    assert not [c for c in build_charts(запись) if c.key == "asset_mix"]


def test_исход_дел_складывает_роли():
    """Вопрос «сколько дел ещё не закончено» одинаков для истца и ответчика."""
    запись = {
        "baseInfo": {"inn": "1", "shortName": 'ООО "ТЕСТ"'},
        "arbitrationByStatus": {
            "plaintiffArbitration": {"plaintiffArbitrationFinished": {"pfCount": 3}},
            "defandantArbitration": {
                "defandantArbitrationFinished": {"dfCount": 2},
                "defandantArbitrationPending": {"dpCount": 4},
            },
        },
    }

    spec = next(c for c in build_charts(запись) if c.key == "case_outcome")

    assert dict(zip(spec.labels, spec.series[0].values, strict=True)) == {
        "Завершено": 5.0,  # 3 как истец + 2 как ответчик
        "Рассматривается": 4.0,
        "Обжалуется": 0.0,
    }


def test_производства_считаются_по_годам_возбуждения():
    """Дюжина производств пятилетней давности и дюжина за последний год —
    разные компании, а счётчик «активных» их не различает."""
    запись = {
        "baseInfo": {"inn": "1", "shortName": 'ООО "ТЕСТ"'},
        "executionProceedings": [
            {"date": "2024-11-10T21:00:00.000Z", "active": False},
            {"date": "2024-02-01T00:00:00.000Z", "active": False},
            {"date": "2026-01-15T00:00:00.000Z", "active": True},
        ],
    }

    spec = next(c for c in build_charts(запись) if c.key == "proceedings_years")

    assert spec.labels == ("2024", "2026")
    assert spec.series[0].values == (2, 1)


def test_длинная_история_производств_усечена_и_названа():
    """Пятнадцать лет не помещаются в карточку, но выдавать восемь лет
    за всю историю нельзя — усечение названо в источнике."""
    from core.charts import PROCEEDINGS_YEARS

    запись = {
        "baseInfo": {"inn": "1", "shortName": 'ООО "ТЕСТ"'},
        "executionProceedings": [{"date": f"{2010 + i}-01-01T00:00:00.000Z"} for i in range(12)],
    }

    spec = next(c for c in build_charts(запись) if c.key == "proceedings_years")

    assert len(spec.labels) == PROCEEDINGS_YEARS
    assert spec.labels[-1] == "2021"
    assert "из 12" in spec.source


def test_перечень_видов_для_модели_совпадает_с_построителями():
    """Модель выбирает вид по этому перечню. Разойдись он с построителями —
    она будет просить график, которого нет, или не узнает о существующем.
    Одно расхождение уже было: в перечне «Выручка и активы», на экране
    «Выручка и активы по годам»."""
    from api.agent.tools import CHART_KINDS
    from core.charts import BUILDERS

    перечисленные = {}
    for строка in CHART_KINDS.strip().splitlines():
        ключ, название = строка.lstrip("- ").split(" — ")
        перечисленные[ключ.strip()] = название.strip("«»")

    assert set(перечисленные) == {b.__name__ for b in BUILDERS}


@нужен_набор
def test_названия_видов_дословно_совпадают_с_заголовками():
    """Ответ модели «показал „Выручку и активы“» и подпись под картинкой
    «Выручка и активы по годам» — расхождение, которое пользователь читает
    как ошибку. Ровно оно и было до этой проверки."""
    from api.agent.tools import CHART_KINDS

    перечисленные = {}
    for строка in CHART_KINDS.strip().splitlines():
        ключ, название = строка.lstrip("- ").split(" — ")
        перечисленные[ключ.strip()] = название.strip("«»")

    настоящие = {c.key: c.title for record in _RECORDS for c in build_charts(record)}

    assert настоящие
    for ключ, заголовок in настоящие.items():
        assert перечисленные[ключ] == заголовок, (
            f"{ключ}: в перечне «{перечисленные[ключ]}», на экране «{заголовок}»"
        )

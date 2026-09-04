"""Описания графиков отчёта.

Кейсодатель упомянул графики трижды и назвал их отсутствие болью текущего продукта:
«там, по сути, нет графиков».

Описание говорит, **что** показать, и ничего не говорит о том, **чем** рисовать:
ни цветов, ни размеров, ни библиотеки. Отрисовка целиком забота интерфейса.

Собирается здесь, а не на клиенте, по той же причине, что и отчёт: модель в диалоге
получает те же ряды, что нарисованы на экране. Иначе ответ на вопрос «что с выручкой»
разойдётся с графиком рядом, а проверяемость — заявленная ценность продукта.

Правило достаточности данных — доменное знание наравне с «что важнее»: две точки это
ряд, одна — число. График из одной точки создаёт впечатление динамики, которой нет.
"""

from __future__ import annotations

from dataclasses import dataclass

Number = float | int | None


@dataclass(frozen=True)
class Series:
    """Одна серия значений. Значения соответствуют подписям оси один к одному."""

    name: str
    unit: str
    values: tuple[Number, ...]


@dataclass(frozen=True)
class ChartSpec:
    """Описание графика. Отрисовку не задаёт."""

    key: str
    title: str
    form: str  # "lines" — ряд по годам, "bars" — сравнение величин
    labels: tuple[str, ...]
    series: tuple[Series, ...]
    source: str  # из каких полей отчёта построено


MIN_POINTS = 2


def series_chart(
    key: str, title: str, labels: list[str], series: list[Series], source: str
) -> ChartSpec | None:
    """Ряд по годам. Меньше двух точек — не график.

    Возвращает None, а не пустое описание: пустая рамка выглядит как поломка
    и подрывает доверие ко всему отчёту.
    """
    if len(labels) < MIN_POINTS:
        return None
    непустые = [s for s in series if any(v is not None for v in s.values)]
    if not непустые:
        return None
    return ChartSpec(
        key=key,
        title=title,
        form="lines",
        labels=tuple(labels),
        series=tuple(Series(s.name, s.unit, tuple(s.values)) for s in непустые),
        source=source,
    )


def snapshot_chart(
    key: str, title: str, pairs: list[tuple[str, Number]], unit: str, source: str
) -> ChartSpec | None:
    """Сравнение величин на один момент. Нужны все величины.

    Ноль — это значение, а не отсутствие: «в этой роли не судилась» и «данных о роли
    нет» разные утверждения, и второе мы сказать не можем.
    """
    if any(value is None for _, value in pairs):
        return None
    return ChartSpec(
        key=key,
        title=title,
        form="bars",
        labels=tuple(label for label, _ in pairs),
        series=(Series(name=title, unit=unit, values=tuple(v for _, v in pairs)),),
        source=source,
    )


# ─────────────────────────── извлечение величин ───────────────────────────


def _num(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(str(value).replace(" ", ""))
    except (TypeError, ValueError):
        return None


def _is_entrepreneur(record: dict) -> bool:
    return str((record.get("baseInfo") or {}).get("shortName") or "").startswith("ИП")


def _fin_years(record: dict) -> list[dict]:
    """Годовые отчёты по возрастанию года. В выгрузке они идут от свежего к старому."""
    reports = [f for f in (record.get("finReports") or []) if (f.get("common") or {}).get("year")]
    return sorted(reports, key=lambda f: f["common"]["year"])


# ─────────────────────────── пять графиков ───────────────────────────


def revenue_assets(record: dict) -> ChartSpec | None:
    """Выручка и активы по годам. Данные есть у 121 компании из 200.

    Прибыль второй линией не берётся: она заполнена у 68 компаний против 121
    с выручкой, и линия оборвалась бы у половины — график выглядел бы сломанным
    там, где он просто неполон.
    """
    if _is_entrepreneur(record):
        return None
    years = _fin_years(record)
    with_revenue = [f for f in years if (f.get("common") or {}).get("proceeds") is not None]
    if len(with_revenue) < MIN_POINTS:
        return None
    return series_chart(
        key="revenue_assets",
        title="Выручка и активы по годам",
        labels=[str(f["common"]["year"]) for f in with_revenue],
        series=[
            Series("Выручка", "₽", tuple(_num(f["common"].get("proceeds")) for f in with_revenue)),
            Series(
                "Активы",
                "₽",
                tuple(_num((f.get("assets") or {}).get("totalAssets")) for f in with_revenue),
            ),
        ],
        source="finReports[].common.proceeds, finReports[].assets.totalAssets",
    )


def balance(record: dict) -> ChartSpec | None:
    """Чем обеспечены активы: собственным капиталом или обязательствами.

    Накопительный столбец недоступен — компонент дизайн-системы не выставляет `stackId`.
    Два столбца рядом читаются точнее: длины человек сравнивает лучше, чем доли.
    """
    if _is_entrepreneur(record):
        return None
    years = _fin_years(record)
    if not years:
        return None
    liabilities = years[-1].get("liabilities") or {}
    capitals = _num(liabilities.get("capitals"))
    total = _num(liabilities.get("totalLiabilities"))
    if capitals is None or total is None:
        return None
    return snapshot_chart(
        key="balance",
        title="Чем обеспечены активы",
        pairs=[("Собственный капитал", capitals), ("Обязательства", max(total - capitals, 0))],
        unit="₽",
        source="finReports[].liabilities.capitals, .totalLiabilities",
    )


def plaintiff_defendant(record: dict) -> ChartSpec | None:
    """Суммы в роли истца и ответчика. Лучшее покрытие — 160 компаний из 200.

    Роль меняет смысл цифры на противоположный: сама взыскивает или к ней предъявляют.
    """
    arb = record.get("arbitrationByStatus") or {}
    plaintiff, defendant = arb.get("plaintiffArbitration"), arb.get("defandantArbitration")
    if plaintiff is None and defendant is None:
        return None

    def сумма(block: dict | None, keys: tuple[str, ...]) -> float:
        """Складывает суммы по всем статусам роли: закрытые, обжалованные, открытые."""
        total = 0.0
        for name in keys:
            part = (block or {}).get(name) or {}
            for value in part.values():
                total += _num(value) or 0
        return total

    as_plaintiff = сумма(
        plaintiff,
        (
            "plaintiffArbitrationFinished",
            "plaintiffArbitrationAppealed",
            "plaintiffArbitrationPending",
        ),
    )
    as_defendant = сумма(
        defendant,
        (
            "defandantArbitrationFinished",
            "defandantArbitrationAppealed",
            "defandantArbitrationPending",
        ),
    )
    return snapshot_chart(
        key="plaintiff_defendant",
        title="В какой роли судится",
        pairs=[("Как истец", as_plaintiff), ("Как ответчик", as_defendant)],
        unit="₽",
        source="arbitrationByStatus.plaintiffArbitration, .defandantArbitration",
    )


def arbitration_years(record: dict) -> ChartSpec | None:
    """Судебная нагрузка по годам. Данные есть у 61 компании из 200."""
    cases = sorted(
        (c for c in (record.get("arbitrationCases") or []) if c.get("year")),
        key=lambda c: c["year"],
    )
    if len(cases) < MIN_POINTS:
        return None
    return series_chart(
        key="arbitration_years",
        title="Суммы исков по годам",
        labels=[str(c["year"]) for c in cases],
        series=[
            Series("Как истец", "₽", tuple(_num(c.get("plaintiffAmount")) or 0 for c in cases)),
            Series("Как ответчик", "₽", tuple(_num(c.get("defendantAmount")) or 0 for c in cases)),
        ],
        source="arbitrationCases[].plaintiffAmount, .defendantAmount",
    )


def proceedings(record: dict) -> ChartSpec | None:
    """Исполнительные производства: активные против завершённых.

    Поштучно не рисуются: у одной компании их 1744 — в описание уходят агрегаты.
    """
    items = record.get("executionProceedings") or []
    if not items:
        return None
    active = sum(1 for p in items if p.get("active") is True)
    return snapshot_chart(
        key="proceedings",
        title="Исполнительные производства",
        pairs=[("Активные", active), ("Завершённые", len(items) - active)],
        unit="",
        source="executionProceedings[].active",
    )


BUILDERS = (revenue_assets, balance, plaintiff_defendant, arbitration_years, proceedings)


def build_charts(record: dict) -> tuple[ChartSpec, ...]:
    """Все описания графиков, которые данные позволяют построить."""
    return tuple(chart for build in BUILDERS if (chart := build(record)) is not None)

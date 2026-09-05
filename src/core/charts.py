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

from core.fields import describe

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
    # Подпись источника словами, а не путём внутри данных. Раньше здесь стояло
    # `finReports[].assets.currentAssets.{stocks,receivables,bankroll}` — путь
    # JSON, показанный пользователю. Слова берутся из словаря полей, чтобы
    # у одного поля было одно название по всему продукту.
    source: str


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
    # Смысл у столбчатого графика несут подписи, а не название серии: повторять
    # в нём заголовок значит писать одно и то же дважды.
    return ChartSpec(
        key=key,
        title=title,
        form="bars",
        labels=tuple(label for label, _ in pairs),
        series=(
            Series(
                name="Сумма" if unit == "₽" else "Количество",
                unit=unit,
                values=tuple(v for _, v in pairs),
            ),
        ),
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
        source=describe(["finReports[].common.proceeds", "finReports[].assets.totalAssets"]),
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
        source=describe([
            "finReports[].liabilities.capitals",
            "finReports[].liabilities.totalLiabilities",
        ]),
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
        source="Суммы исков по арбитражным делам, в разбивке по роли компании",
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
        source=describe([
            "arbitrationCases[].plaintiffAmount",
            "arbitrationCases[].defendantAmount",
        ]),
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
        source=describe(["executionProceedings[].active"]),
    )


def profit_years(record: dict) -> ChartSpec | None:
    """Прибыль по годам. Данные есть у 68 компаний из 200.

    Отдельным графиком, а не второй линией к выручке: прибыль заполнена реже,
    и линия обрывалась бы у половины компаний — график выглядел бы сломанным
    там, где он просто неполон. Убыток здесь обычное значение: из 179 значений
    прибыли 23 отрицательные, и ось обязана уходить ниже нуля.
    """
    if _is_entrepreneur(record):
        return None
    years = [f for f in _fin_years(record) if (f.get("common") or {}).get("profit") is not None]
    if len(years) < MIN_POINTS:
        return None
    return series_chart(
        key="profit_years",
        title="Прибыль по годам",
        labels=[str(f["common"]["year"]) for f in years],
        series=[Series("Прибыль", "₽", tuple(_num(f["common"].get("profit")) for f in years))],
        source=describe(["finReports[].common.profit"]),
    )


def _parts(node: dict | None, fields: list[tuple[str, str]]) -> list[tuple[str, Number]]:
    """Состав величины: берём только те части, которые в отчёте есть.

    Отсутствующая часть — не ноль. «Запасов нет» и «про запасы не сказано» это
    разные утверждения, и второе мы сказать не можем, поэтому пропущенное поле
    просто не попадает на график, а не рисуется нулевым столбцом.
    """
    pairs: list[tuple[str, Number]] = []
    for key, label in fields:
        value = _num((node or {}).get(key))
        if value is not None:
            pairs.append((label, value))
    # Одна часть — это число, а не состав; всё по нулям — нечего показывать.
    if len(pairs) < MIN_POINTS or not any(value for _, value in pairs):
        return []
    return pairs


def asset_mix(record: dict) -> ChartSpec | None:
    """Из чего состоят оборотные активы. 127 компаний из 200 — лучшее покрытие
    среди финансовых графиков.

    Состав, а не итог: «оборотные против внеоборотных» заполнено лишь у 49 компаний
    и вдобавок говорит меньше. Для решения о поставщике важно, где лежат деньги —
    в запасах на складе, в долгах покупателей или на счету: расплатиться завтра
    можно только последним.
    """
    if _is_entrepreneur(record):
        return None
    years = _fin_years(record)
    if not years:
        return None
    pairs = _parts(
        (years[-1].get("assets") or {}).get("currentAssets"),
        [("stocks", "Запасы"), ("receivables", "Дебиторка"), ("bankroll", "Деньги")],
    )
    if not pairs:
        return None
    return snapshot_chart(
        key="asset_mix",
        title="Из чего состоят оборотные активы",
        pairs=pairs,
        unit="₽",
        source=describe(["finReports[].assets.currentAssets.stocks",
                         "finReports[].assets.currentAssets.receivables",
                         "finReports[].assets.currentAssets.bankroll"]),
    )


def liability_mix(record: dict) -> ChartSpec | None:
    """Из чего состоят краткосрочные обязательства. 51 компания из 200.

    Долг поставщикам и долг банку гасят по-разному: первый обычно можно
    передоговорить, второй нет.
    """
    if _is_entrepreneur(record):
        return None
    years = _fin_years(record)
    if not years:
        return None
    pairs = _parts(
        (years[-1].get("liabilities") or {}).get("shortTermLiabilities"),
        [("accountsPayable", "Кредиторка"), ("borrowedFunds", "Заёмные средства")],
    )
    if not pairs:
        return None
    return snapshot_chart(
        key="liability_mix",
        title="Из чего состоят краткосрочные обязательства",
        pairs=pairs,
        unit="₽",
        source=describe(["finReports[].liabilities.shortTermLiabilities.accountsPayable",
                         "finReports[].liabilities.shortTermLiabilities.borrowedFunds"]),
    )


# Счётчики дел по статусам. Роль в этом графике не различается намеренно:
# вопрос «сколько дел ещё не закончено» одинаков для истца и ответчика,
# а роль показывает соседний график.
# `defandant` — опечатка в схеме источника, не наша; префиксы счётчиков
# (pf/pp/pa и df/dp/da) там же заданы по первым буквам роли и статуса.
_CASE_STATUS = (
    (
        "Завершено",
        ("plaintiffArbitrationFinished", "pfCount"),
        ("defandantArbitrationFinished", "dfCount"),
    ),
    (
        "Рассматривается",
        ("plaintiffArbitrationPending", "ppCount"),
        ("defandantArbitrationPending", "dpCount"),
    ),
    (
        "Обжалуется",
        ("plaintiffArbitrationAppealed", "paCount"),
        ("defandantArbitrationAppealed", "daCount"),
    ),
)


def case_outcome(record: dict) -> ChartSpec | None:
    """Чем закончились дела. 65 компаний из 200.

    Незакрытое дело и закрытое — разные новости: первое ещё может обернуться
    взысканием, второе уже нет. Общий счётчик дел этого не различает.
    """
    arb = record.get("arbitrationByStatus") or {}
    pairs: list[tuple[str, Number]] = []
    for label, (истец, ключ_истца), (ответчик, ключ_ответчика) in _CASE_STATUS:
        сумма = 0.0
        for роль, статус, ключ in (
            ("plaintiffArbitration", истец, ключ_истца),
            ("defandantArbitration", ответчик, ключ_ответчика),
        ):
            блок = ((arb.get(роль) or {}).get(статус)) or {}
            сумма += _num(блок.get(ключ)) or 0
        pairs.append((label, сумма))

    # Один непустой статус — это число, а не сравнение: «все восемь дел
    # завершены» карточка и так говорит счётчиком.
    if sum(1 for _, value in pairs if value) < MIN_POINTS:
        return None
    return snapshot_chart(
        key="case_outcome",
        title="Чем закончились дела",
        pairs=pairs,
        unit="",
        source="Счётчики арбитражных дел по статусу рассмотрения",
    )


# Сколько последних лет показываем. Пятнадцать лет подряд не помещаются в карточку
# шириной 430 пикселей, а вопрос, ради которого на график смотрят, — «беда свежая
# или старая» — закрывается последними годами. Усечение названо в источнике,
# чтобы не выдавать восемь лет за всю историю.
PROCEEDINGS_YEARS = 8


def proceedings_years(record: dict) -> ChartSpec | None:
    """Когда возбуждались производства. 67 компаний из 200.

    Дюжина производств пятилетней давности и дюжина за последний год — разные
    компании. Счётчик «активных и завершённых» их не различает.
    """
    by_year: dict[str, int] = {}
    for item in record.get("executionProceedings") or []:
        year = str(item.get("date") or "")[:4]
        if year.isdigit():
            by_year[year] = by_year.get(year, 0) + 1
    if len(by_year) < MIN_POINTS:
        return None

    years = sorted(by_year)[-PROCEEDINGS_YEARS:]
    усечено = len(by_year) > len(years)
    return series_chart(
        key="proceedings_years",
        title="Когда возбуждались производства",
        labels=years,
        series=[Series("Производств", "", tuple(by_year[y] for y in years))],
        source=describe(["executionProceedings[].date"])
        + (f" — показаны последние {PROCEEDINGS_YEARS} лет из {len(by_year)}" if усечено else ""),
    )


BUILDERS = (
    # Порядок определяет, какой график попадёт на карточку раздела: первый
    # построенный. Внутри раздела сначала динамика, потом состав на сегодня —
    # «что происходит» важнее, чем «как устроено».
    revenue_assets,
    profit_years,
    balance,
    asset_mix,
    liability_mix,
    plaintiff_defendant,
    case_outcome,
    arbitration_years,
    proceedings,
    proceedings_years,
)


def build_charts(record: dict) -> tuple[ChartSpec, ...]:
    """Все описания графиков, которые данные позволяют построить."""
    return tuple(chart for build in BUILDERS if (chart := build(record)) is not None)

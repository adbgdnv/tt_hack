"""Сборка представления отчёта о контрагенте.

Чистая функция от записи: ни сети, ни модели. Отчёт обязан открываться при упавшем
провайдере — иначе продукт держится на доступности внешнего сервиса.

Одно представление идёт и на экран, и в диалог, и в MCP. Если показать модели больше,
чем видит пользователь, её ответ разойдётся с экраном и проверить его будет нельзя,
а проверяемость — заявленная ценность продукта.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from core.charts import ChartSpec, build_charts
from core.factors import frequency, heading, weight
from core.triggers import Trigger
from core.triggers import build as build_triggers

# ─────────────────────────── разделы ───────────────────────────

SECTION_TITLES: dict[str, str] = {
    "registration": "Регистрация и реквизиты",
    "courts": "Суды",
    "enforcement": "Исполнительные производства",
    "finances": "Финансы",
    "registries": "Реестры",
    "activity": "Виды деятельности",
    "management": "Руководство",
    "related": "Связанные организации",
}

# Раздел фактора берётся из поля `chapter` данных, а не выводится из кода.
CHAPTER_TO_SECTION: dict[str, str] = {
    "arbitr": "courts",
    "execproc": "enforcement",
    "finance": "finances",
    "reestrs": "registries",
    "okved": "activity",
    "manager": "management",
    "relatedComp": "related",
    "license": "registration",
    "site": "registration",
    "filials": "registration",
}

# Нераспознанный раздел не отбрасывается: фактор виден, а сам факт расхождения
# схемы фиксируется. В данных уже есть один такой — у фактора в `chapter`
# лежит его собственный код.
FALLBACK_SECTION = "registries"

# График принадлежит разделу и наследует его порядок: раздел с сигналом стоит выше,
# и его график виден раньше. Отдельного правила приоритета графиков не нужно.
# Почему в разделе, где график бывает, его сейчас нет. Молчание читается как поломка:
# пользователь видит числа и не понимает, почему рядом нет картинки.
CHARTS_MISSING_NOTE: dict[str, str] = {
    "finances": "Для графика нужна отчётность минимум за два года — здесь её меньше",
    "courts": "Для графика нужны суммы по ролям или дела минимум за два года",
    "enforcement": "Графика нет: производств в отчёте не значится",
}

CHARTS_NOT_APPLICABLE_NOTE = "У ИП бухгалтерской отчётности не бывает — графика нет"

CHART_SECTIONS: dict[str, str] = {
    "revenue_assets": "finances",
    "profit_years": "finances",
    "balance": "finances",
    "asset_mix": "finances",
    "liability_mix": "finances",
    "plaintiff_defendant": "courts",
    "case_outcome": "courts",
    "arbitration_years": "courts",
    "proceedings": "enforcement",
    "proceedings_years": "enforcement",
}

# У предпринимателей этих сведений не бывает по устройству формы: проверено,
# что у всех пятидесяти отсутствуют и отчётность, и учредители.
NOT_APPLICABLE_FOR_ENTREPRENEUR = ("finances", "management")


class State(Enum):
    """Четыре разных «пусто» — смешивать их значит выдавать «мы не знаем»
    за «всё чисто»."""

    SIGNAL = "signal"
    FILLED = "filled"
    EMPTY = "empty"
    NOT_APPLICABLE = "not_applicable"


STATE_NOTES: dict[State, str] = {
    State.SIGNAL: "Есть на что обратить внимание",
    State.FILLED: "Данные есть, ничего не сработало",
    State.EMPTY: "Данных нет — оценить по этому критерию невозможно",
    State.NOT_APPLICABLE: "У ИП такого не бывает",
}

_ORDER = {State.SIGNAL: 0, State.FILLED: 1, State.EMPTY: 2, State.NOT_APPLICABLE: 3}


# ─────────────────────────── структуры ───────────────────────────


@dataclass(frozen=True)
class Factor:
    code: str
    heading: str
    explanation: str
    weight: int


@dataclass(frozen=True)
class Fact:
    """Число или строка раздела — то, что пользователь может сверить с источником.

    `kind` отделяет деньги от прочего: форматирование сумм — забота интерфейса,
    у него для этого есть компонент дизайн-системы, а собственная реализация
    расходится с ней в мелочах.
    """

    label: str
    value: object
    kind: str = "text"
    # Изменение к предыдущему году долей: 0.16 это +16%. None означает
    # «сравнивать не с чем», а не «не изменилось».
    #
    # Число без сравнения решения не меняет: «выручка 116 млрд» одинаково
    # выглядит у растущей компании и у падающей вдвое.
    delta: float | None = None
    delta_note: str = ""  # «к 2024» — с чем именно сравнили


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    state: State
    note: str
    factors: tuple[Factor, ...] = ()
    facts: tuple[Fact, ...] = ()
    charts: tuple[ChartSpec, ...] = ()
    # Почему графика нет. Пусто, когда график есть или когда его тут и не бывает.
    charts_note: str = ""
    # Сколько проверок по разделу провёл источник и сколько из них компания прошла.
    #
    # Без этой пары «проверено, чисто» неотличимо от «мы не смотрели», и раздел
    # молча съезжает в «данных нет». Так и было: реестры проверены у всех 200
    # компаний — от 4 до 9 проверок на каждую, — а 157 из них показывали
    # «Недостаточно данных». Источник прямо пишет «Не найден в реестре
    # организаций проходящих процедуру банкротства»; выдавать это за незнание
    # значит пугать пользователя там, где данные его успокаивают.
    checks_passed: int = 0
    checks_total: int = 0
    # Названия пройденных проверок — для детального вида. На карточке их место
    # занимает счётчик: двадцать три подтверждения списком это ровно тот шум,
    # против которого продукт и сделан.
    passed_checks: tuple[str, ...] = ()


@dataclass(frozen=True)
class Assessment:
    """Оценка риска. `known=False` означает «оценить невозможно» —
    это не низкий риск и не высокий."""

    source: str
    value: str
    known: bool


@dataclass(frozen=True)
class Report:
    inn: str
    name: str
    is_entrepreneur: bool
    status: str
    registered: str | None
    years: object
    bank_risk: Assessment
    zsk_risk: Assessment
    sections: tuple[Section, ...]
    unknown_chapters: tuple[str, ...] = ()
    signals: int = 0
    unknowns: int = 0
    # Противоречия между блоками — то, чего не видно ни в одном разделе
    # по отдельности. Считаются здесь же, чтобы модель и экран видели одно
    # и то же: расхождение между ними проверить было бы нечем.
    triggers: tuple[Trigger, ...] = ()


# ─────────────────────────── оценки риска ───────────────────────────

_BANK_RISK = {"LOW": "Низкий", "MEDIUM": "Средний", "HIGH": "Высокий"}
_ZSK_RISK = {"GREEN": "Зелёный", "YELLOW": "Жёлтый", "RED": "Красный"}
_NO_ASSESSMENT = "Оценить невозможно"


def _assessment(raw: object, mapping: dict[str, str], source: str) -> Assessment:
    value = mapping.get(str(raw or "").strip().upper())
    if value is None:
        return Assessment(source=source, value=_NO_ASSESSMENT, known=False)
    return Assessment(source=source, value=value, known=True)


# ─────────────────────────── факты разделов ───────────────────────────


def _num(value: object) -> float:
    try:
        return float(str(value).replace(" ", ""))
    except (TypeError, ValueError):
        return 0.0


# Коэффициенты источника. Показываем как есть, без толкования: три числа даны,
# пороги — нет. Раскрасить их в «норма / есть риски», как делают открытые
# сервисы, значит придумать границу за источник, а отвечаем мы только за то,
# что в нём сказано. Год в подписи обязателен: у 9 компаний из 47 он не
# совпадает с годом отчётности, и без него читался бы как год выручки.
_COEFFICIENTS = (
    ("sustainability", "Финансовая устойчивость"),
    ("solvency", "Платёжеспособность"),
    ("profitability", "Рентабельность"),
)


def _maybe_num(value: object) -> float | None:
    """Число или None. В отличие от `_num`, отсутствие не превращается в ноль:
    ноль выручки и отсутствие отчётности — разные утверждения."""
    if value is None:
        return None
    try:
        return float(str(value).replace(" ", ""))
    except (TypeError, ValueError):
        return None


def _delta(now: float, before: float | None) -> float | None:
    """Изменение долей от прошлого года.

    От нуля и от убытка не считаем: «прибыль выросла на 300%» при убытке
    в прошлом году — арифметически верно и по смыслу бессмысленно, а деление
    на ноль просто невозможно. В таких случаях честнее не показать ничего.
    """
    if before is None or before <= 0:
        return None
    return (now - before) / before


def _coefficient_facts(record: dict) -> list[Fact]:
    coefficient = record.get("coefficient") or {}
    year = coefficient.get("year")
    facts = []
    for key, label in _COEFFICIENTS:
        value = _maybe_num(coefficient.get(key))
        if value is not None:
            facts.append(Fact(f"{label}, {year}" if year else label, value, "ratio"))
    return facts


def _finance_facts(record: dict) -> tuple[Fact, ...]:
    """Выручка и прибыль последнего года — с изменением к предыдущему."""
    years = sorted(
        (f for f in (record.get("finReports") or []) if (f.get("common") or {}).get("year")),
        key=lambda f: f["common"]["year"],
    )
    if not years:
        return ()
    last, previous = years[-1], (years[-2] if len(years) > 1 else None)
    facts = []
    for field, label in (("proceeds", "Выручка"), ("profit", "Прибыль")):
        value = _maybe_num((last.get("common") or {}).get(field))
        if value is None:
            continue
        before = _maybe_num(((previous or {}).get("common") or {}).get(field))
        change = _delta(value, before)
        facts.append(
            Fact(
                f"{label} за {last['common']['year']}",
                round(value),
                "money",
                delta=change,
                delta_note=f"к {previous['common']['year']}" if change is not None else "",
            )
        )
    return tuple(facts + _coefficient_facts(record))


def _section_facts(record: dict, key: str) -> tuple[Fact, ...]:
    """Числа раздела — то, что пользователь может сверить с исходником."""
    base = record.get("baseInfo") or {}
    if key == "registration":
        reg = base.get("registrationInfo") or {}
        facts = [Fact("Статус", (record.get("status") or {}).get("status") or "—")]
        if reg.get("yearsFromRegistration") is not None:
            facts.append(Fact("Лет с регистрации", reg["yearsFromRegistration"], "count"))
        if base.get("address"):
            facts.append(Fact("Адрес", str(base["address"])))
        return tuple(facts)
    if key == "courts":
        arb = record.get("arbitrationByStatus") or {}
        facts = []
        if arb.get("commonCount") is not None:
            facts.append(Fact("Всего дел", int(_num(arb["commonCount"])), "count"))
        if arb.get("commonAmount") is not None:
            facts.append(Fact("Сумма по делам", round(_num(arb["commonAmount"])), "money"))
        return tuple(facts)
    if key == "enforcement":
        proceedings = record.get("executionProceedings") or []
        active = [p for p in proceedings if p.get("active") is True]
        if not proceedings:
            return ()
        return (
            Fact("Всего производств", len(proceedings), "count"),
            Fact("Из них активных", len(active), "count"),
            Fact("Сумма активных", round(sum(_num(p.get("amount")) for p in active)), "money"),
        )
    if key == "finances":
        return _finance_facts(record)
    if key == "activity":
        main = (record.get("kindsOfActivityInfo") or {}).get("mainKindOfActivity") or {}
        return (Fact("Основной вид", str(main.get("description") or "—")),) if main else ()
    if key == "management":
        person = (record.get("foundersInfo") or {}).get("authPerson") or {}
        if not person:
            return ()
        return (
            Fact("Руководитель", str(person.get("name") or "—")),
            Fact("Должность", str(person.get("positionName") or "—")),
        )
    if key == "related":
        related = record.get("relatedCompanies") or []
        return (Fact("Связанных организаций", len(related), "count"),) if related else ()
    return ()


# ─────────────────────────── сборка ───────────────────────────


def _is_entrepreneur(record: dict) -> bool:
    return str((record.get("baseInfo") or {}).get("shortName") or "").startswith("ИП")


def _collect_factors(record: dict) -> tuple[dict[str, list[Factor]], tuple[str, ...]]:
    """Раскладывает негативные факторы по разделам, возвращая и нераспознанные разделы."""
    by_section: dict[str, list[Factor]] = {key: [] for key in SECTION_TITLES}
    unknown: list[str] = []
    negative = (record.get("reputationalRisks") or {}).get("negative") or []
    for raw in negative:
        code = str(raw.get("code") or "")
        chapter = str(raw.get("chapter") or "")
        section = CHAPTER_TO_SECTION.get(chapter)
        if section is None:
            section = FALLBACK_SECTION
            if chapter and chapter not in unknown:
                unknown.append(chapter)
        by_section[section].append(
            Factor(
                code=code,
                heading=heading(code),
                # Объяснение из источника, дословно: своя редактура исказила бы смысл.
                explanation=str(raw.get("name") or "").strip(),
                weight=weight(code),
            )
        )
    for factors in by_section.values():
        # Тяжесть, затем редкость, затем алфавит. Средний ключ появился потому,
        # что без него ничья решалась буквой заголовка — у 29 компаний из 117,
        # и «Массовый адрес» обгонял «Убыток по отчётности» из-за «М». Реже
        # значит больше сообщает об этой компании, а не о базе.
        factors.sort(key=lambda f: (-f.weight, frequency(f.code), f.heading))
    return by_section, tuple(unknown)


# Название проверки от объяснения, зачем её знать, источник отделяет запятой,
# точкой или тире: «Не найден в реестре организаций должников ФНС, что может
# свидетельствовать об отсутствии задолженности...». Нужна первая часть.
_CLAUSE = re.compile(r"[,.]\s|\s[-–—]\s")


def _check_label(name: str) -> str:
    """Название пройденной проверки — первая фраза подтверждения, дословно.

    Своя редактура здесь исказила бы смысл: «не найден в реестре» и «в реестре
    не значится» юридически не одно и то же, а отвечаем мы только за то, что
    сказал источник.
    """
    return _CLAUSE.split(name.strip(), 1)[0].strip(" .,-–—")


def _collect_checks(record: dict) -> dict[str, list[str]]:
    """Какие проверки раздел прошёл — по позитивным подтверждениям источника.

    На карточке от этого списка остаётся одно число: позитивных факторов 3 122
    на 200 компаний против 217 негативных, и выписать их значит утопить сигнал
    в подтверждениях того, что ничего не случилось. Но иметь их надо: без них
    «проверено, чисто» неотличимо от «мы не смотрели».
    """
    passed: dict[str, list[str]] = {key: [] for key in SECTION_TITLES}
    positive = (record.get("reputationalRisks") or {}).get("positive") or []
    for raw in positive:
        chapter = str(raw.get("chapter") or "")
        label = _check_label(str(raw.get("name") or ""))
        if label:
            passed[CHAPTER_TO_SECTION.get(chapter, FALLBACK_SECTION)].append(label)
    return passed


def _state(
    key: str, factors: list[Factor], facts: tuple[Fact, ...], checks: int, entrepreneur: bool
) -> State:
    if entrepreneur and key in NOT_APPLICABLE_FOR_ENTREPRENEUR:
        return State.NOT_APPLICABLE
    if factors:
        return State.SIGNAL
    # Пройденная проверка — такие же данные, как факт. Раздел без собственных
    # чисел, но с подтверждениями источника, знает о компании достаточно.
    return State.FILLED if facts or checks else State.EMPTY


def _charts_note(key: str, state: State, charts: list[ChartSpec]) -> str:
    """Объяснение отсутствия графика — только там, где график вообще бывает."""
    if charts or key not in CHARTS_MISSING_NOTE:
        return ""
    if state is State.NOT_APPLICABLE:
        return CHARTS_NOT_APPLICABLE_NOTE
    return CHARTS_MISSING_NOTE[key]


def build(record: dict) -> Report:
    """Собирает представление отчёта из записи контрагента."""
    base = record.get("baseInfo") or {}
    entrepreneur = _is_entrepreneur(record)
    by_section, unknown = _collect_factors(record)
    passed = _collect_checks(record)

    by_chart_section: dict[str, list[ChartSpec]] = {key: [] for key in SECTION_TITLES}
    for chart in build_charts(record):
        by_chart_section[CHART_SECTIONS[chart.key]].append(chart)

    sections = []
    for key, title in SECTION_TITLES.items():
        factors = by_section[key]
        facts = _section_facts(record, key)
        state = _state(key, factors, facts, len(passed[key]), entrepreneur)
        # Неприменимый раздел не проверялся: у ИП отчётности не бывает, и «0 из 0»
        # там честнее любого счётчика.
        applicable = state is not State.NOT_APPLICABLE
        passed_checks = tuple(passed[key]) if applicable else ()
        checks_passed = len(passed_checks)
        # Сработавший фактор — это тоже проведённая проверка, просто непройденная.
        # Поэтому знаменатель считает и их: «5 из 9» у компании с четырьмя
        # сигналами в реестрах сообщает больше, чем одни только четыре сигнала.
        checks_total = checks_passed + (len(factors) if applicable else 0)
        sections.append(
            Section(
                key=key,
                title=title,
                state=state,
                note=STATE_NOTES[state],
                factors=tuple(factors),
                facts=facts if state is not State.NOT_APPLICABLE else (),
                # Неприменимый раздел графиков не содержит по определению:
                # данных для них не бывает.
                charts=(
                    tuple(by_chart_section[key]) if state is not State.NOT_APPLICABLE else ()
                ),
                charts_note=_charts_note(key, state, by_chart_section[key]),
                checks_passed=checks_passed,
                checks_total=checks_total,
                passed_checks=passed_checks,
            )
        )

    # Порядок: сигнал → заполнено → пусто → неприменимо. Внутри сигналов —
    # по суммарной тяжести, чтобы банкротство стояло выше «много кодов ОКВЭД».
    sections.sort(key=lambda s: (_ORDER[s.state], -sum(f.weight for f in s.factors)))

    reg = base.get("registrationInfo") or {}
    return Report(
        inn=str(base.get("inn") or ""),
        name=str(base.get("shortName") or ""),
        is_entrepreneur=entrepreneur,
        status=str((record.get("status") or {}).get("status") or ""),
        registered=reg.get("registrationDate"),
        years=reg.get("yearsFromRegistration"),
        bank_risk=_assessment(base.get("riskLevel"), _BANK_RISK, "Скоринг банка"),
        zsk_risk=_assessment(record.get("zskRiskLevel"), _ZSK_RISK, "Платформа ЗСК Банка России"),
        sections=tuple(sections),
        unknown_chapters=unknown,
        signals=sum(1 for s in sections if s.state is State.SIGNAL),
        unknowns=sum(1 for s in sections if s.state is State.EMPTY),
        triggers=build_triggers(record),
    )

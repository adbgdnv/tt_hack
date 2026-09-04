"""Сборка представления отчёта о контрагенте.

Чистая функция от записи: ни сети, ни модели. Отчёт обязан открываться при упавшем
провайдере — иначе продукт держится на доступности внешнего сервиса.

Одно представление идёт и на экран, и в диалог, и в MCP. Если показать модели больше,
чем видит пользователь, её ответ разойдётся с экраном и проверить его будет нельзя,
а проверяемость — заявленная ценность продукта.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.charts import ChartSpec, build_charts
from core.factors import heading, weight

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
CHART_SECTIONS: dict[str, str] = {
    "revenue_assets": "finances",
    "balance": "finances",
    "plaintiff_defendant": "courts",
    "arbitration_years": "courts",
    "proceedings": "enforcement",
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


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    state: State
    note: str
    factors: tuple[Factor, ...] = ()
    facts: tuple[Fact, ...] = ()
    charts: tuple[ChartSpec, ...] = ()


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
        reports = record.get("finReports") or []
        if not reports:
            return ()
        common = reports[0].get("common") or {}
        facts = []
        if common.get("year") is not None:
            facts.append(Fact("Последний год", str(common["year"])))
        if common.get("proceeds") is not None:
            facts.append(Fact("Выручка", round(_num(common["proceeds"])), "money"))
        return tuple(facts)
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
        factors.sort(key=lambda f: (-f.weight, f.heading))
    return by_section, tuple(unknown)


def _state(key: str, factors: list[Factor], facts: tuple[Fact, ...], entrepreneur: bool) -> State:
    if entrepreneur and key in NOT_APPLICABLE_FOR_ENTREPRENEUR:
        return State.NOT_APPLICABLE
    if factors:
        return State.SIGNAL
    return State.FILLED if facts else State.EMPTY


def build(record: dict) -> Report:
    """Собирает представление отчёта из записи контрагента."""
    base = record.get("baseInfo") or {}
    entrepreneur = _is_entrepreneur(record)
    by_section, unknown = _collect_factors(record)

    by_chart_section: dict[str, list[ChartSpec]] = {key: [] for key in SECTION_TITLES}
    for chart in build_charts(record):
        by_chart_section[CHART_SECTIONS[chart.key]].append(chart)

    sections = []
    for key, title in SECTION_TITLES.items():
        factors = by_section[key]
        facts = _section_facts(record, key)
        state = _state(key, factors, facts, entrepreneur)
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
    )

"""Противоречия между блоками отчёта.

Триггер — не пересказ риск-кода. Пятнадцать негативных кодов источник даёт
готовыми, и они уже показаны разделами; дублировать их значит выдумывать
критерии за источник. Триггер — то, чего не видно **ни в одном поле
по отдельности**: светофоры зелёные, а компания в банкротстве; выручка есть,
а год у неё позапрошлый; уставный капитал 10 000 ₽ при исках на миллионы.

Кандидат становится правилом, только пройдя четыре проверки:

1. это противоречие между блоками, а не одно поле;
2. отчёт не говорит этого сам — ни кодом источника, ни графиком;
3. срабатывает не чаще чем у трети набора, иначе описывает рынок, а не компанию;
4. складывается из названных полей, иначе непроверяем.

Замеры по каждому правилу и список отвергнутых кандидатов —
`specs/009-risk-triggers/research.md`. Частоты закреплены тестами: если правило
поедет, тест назовёт новое число, а не промолчит.

Формулировки обращают внимание и не выносят вердикт — принцип IV конституции.
"""

from __future__ import annotations

from dataclasses import dataclass

# Порог уставного капитала, ниже которого он перестаёт что-либо обеспечивать.
# 10 000 ₽ — законный минимум для ООО, и в наборе таких большинство.
МИНИМАЛЬНЫЙ_КАПИТАЛ = 10_000

# Сколько лет молчания в отчётности считаем сигналом. Два года: отчётность
# сдаётся ежегодно, и пропуск одного года ещё может быть сроком сдачи.
ЛЕТ_МОЛЧАНИЯ = 2

# Год, относительно которого считаем свежесть. Набор — один срез на дату,
# и брать текущую дату машины значит получать разные результаты в разные дни.
ГОД_НАБОРА = 2026


@dataclass(frozen=True)
class Trigger:
    """Сработавшее противоречие.

    `evidence` хранит уже готовые к показу значения, а не сырые числа:
    правило форматирования сумм живёт в отчёте, и второе его место разошлось бы
    с первым.

    `fields` пользователю не показывается никогда — это то, чем триггер
    проверяется, и вход в словарь полей.
    """

    key: str
    title: str
    explanation: str
    section: str
    weight: int
    evidence: tuple[str, ...] = ()
    fields: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


# ─────────────────────────── чтение записи ───────────────────────────


def _num(value: object) -> float:
    if isinstance(value, dict):  # {"$numberLong": "..."} — обёртка крупных сумм
        value = value.get("$numberLong", 0)
    try:
        return float(str(value).replace(" ", "") or 0)
    except (TypeError, ValueError):
        return 0.0


def _years(record: dict) -> list[dict]:
    """Годовые отчёты по возрастанию. В выгрузке они лежат от свежего к старому."""
    return sorted(
        (f for f in (record.get("finReports") or []) if (f.get("common") or {}).get("year")),
        key=lambda f: f["common"]["year"],
    )


def _sum_by_role(record: dict, role: str) -> float:
    """Суммы по всем статусам одной роли: завершённые, обжалуемые, открытые.

    `defandant` — опечатка в схеме источника, не наша.
    """
    блок = (record.get("arbitrationByStatus") or {}).get(role) or {}
    return sum(
        _num(значение)
        for часть in блок.values()
        if isinstance(часть, dict)
        for ключ, значение in часть.items()
        if ключ.endswith("Amount")
    )


def _is_entrepreneur(record: dict) -> bool:
    return str((record.get("baseInfo") or {}).get("shortName") or "").startswith("ИП")


def _money(value: float) -> str:
    """Сумма для показа. Формат тот же, что у отчёта: разряды и порядок словами."""
    целое = f"{round(value):,}".replace(",", " ")
    if abs(value) >= 1e9:
        return f"{целое} ₽ ({value / 1e9:.2f} млрд)"
    if abs(value) >= 1e6:
        return f"{целое} ₽ ({value / 1e6:.1f} млн)"
    return f"{целое} ₽"


# ─────────────────────────── правила ───────────────────────────
#
# Каждое возвращает Trigger или None. Порядок объявления не важен — порядок
# показа задаёт `weight`.


def status_note(record: dict) -> Trigger | None:
    """Статус «действующая» с припиской, которая меняет смысл.

    Все 200 компаний набора числятся действующими, и отчёт честно пишет
    «Действующее». У шести при этом заполнено `status.reasonName`, и там —
    «признано несостоятельным (банкротом)» или «решение о предстоящем
    исключении». Поле не показывалось нигде: на экране у банкрота стояло
    «Статус: Действующее».
    """
    приписка = str((record.get("status") or {}).get("reasonName") or "").strip()
    if not приписка:
        return None
    return Trigger(
        key="status_note",
        title="Статус с оговоркой",
        explanation="Компания числится действующей, но у статуса есть приписка",
        section="registration",
        weight=5,
        evidence=(приписка,),
        fields=("status.status", "status.reasonName"),
        tags=("надёжность",),
    )


def lights_silent(record: dict) -> Trigger | None:
    """Оба светофора зелёные при тяжёлых открытых данных.

    Опорное противоречие кейса. Светофоры считаются по банковским
    транзакционным данным и судов не учитывают — это устройство, а не ошибка.
    Но отчёт показывает зелёные светофоры и красные разделы рядом и нигде
    не говорит, что одно другому противоречит.
    """
    base = record.get("baseInfo") or {}
    if base.get("riskLevel") != "LOW" or record.get("zskRiskLevel") != "GREEN":
        return None

    ответчику = _sum_by_role(record, "defandantArbitration")
    активных = sum(1 for p in (record.get("executionProceedings") or []) if p.get("active"))
    коды = {f.get("code") for f in ((record.get("reputationalRisks") or {}).get("negative") or [])}

    основания = []
    if ответчику > 100e6:
        основания.append(f"предъявлено как ответчику {_money(ответчику)}")
    if активных >= 10:
        основания.append(f"действующих исполнительных производств {активных}")
    if "liquidationStatus" in коды:
        основания.append("значится в реестре проходящих процедуру банкротства")
    if not основания:
        return None

    return Trigger(
        key="lights_silent",
        title="Обе оценки зелёные, а открытые данные тяжёлые",
        explanation=(
            "Скоринг банка и платформа ЗСК считаются по банковским операциям "
            "и судов не учитывают — по открытым данным картина другая"
        ),
        section="courts",
        weight=5,
        evidence=tuple(основания),
        fields=(
            "baseInfo.riskLevel",
            "zskRiskLevel",
            "arbitrationByStatus.defandantArbitration",
            "executionProceedings[].active",
        ),
        tags=("надёжность", "суды"),
    )


def receiver_in_charge(record: dict) -> Trigger | None:
    """Во главе управляющий, а не директор.

    Отчёт печатает «Должность: КОНКУРСНЫЙ УПРАВЛЯЮЩИЙ» и ставит рядом зелёный
    бейдж «значимых сигналов нет»: раздел «Руководство» смотрит на негативные
    коды, а должности среди них нет.
    """
    person = ((record.get("foundersInfo") or {}).get("authPerson")) or {}
    должность = str(person.get("positionName") or "").upper()
    if not any(w in должность for w in ("КОНКУРСН", "ЛИКВИДАТ", "ВНЕШНИЙ УПРАВЛ")):
        return None
    return Trigger(
        key="receiver_in_charge",
        title="Компанией управляет не директор",
        explanation="Полномочия руководителя переданы управляющему — сделки идут через него",
        section="management",
        weight=5,
        evidence=(str(person.get("positionName") or "").strip(),),
        fields=("foundersInfo.authPerson.positionName",),
        tags=("управление", "надёжность"),
    )


def claims_over_revenue(record: dict) -> Trigger | None:
    """Предъявлено больше, чем компания зарабатывает за год.

    Ни один раздел не ставит иски рядом с выручкой: суды и финансы живут
    в разных карточках.
    """
    годы = _years(record)
    if not годы:
        return None
    выручка = _num((годы[-1].get("common") or {}).get("proceeds"))
    ответчику = _sum_by_role(record, "defandantArbitration")
    if выручка <= 0 or ответчику <= выручка:
        return None
    return Trigger(
        key="claims_over_revenue",
        title="Исков больше, чем годовой выручки",
        explanation="Требования к компании превышают всё, что она заработала за год",
        section="courts",
        weight=4,
        evidence=(
            f"предъявлено {_money(ответчику)}",
            f"выручка за {годы[-1]['common']['year']} — {_money(выручка)}",
        ),
        fields=("arbitrationByStatus.defandantArbitration", "finReports[].common.proceeds"),
        tags=("суды", "финансы"),
    )


def negative_capital(record: dict) -> Trigger | None:
    """Собственный капитал ушёл в минус: накопленный убыток съел его целиком."""
    годы = _years(record)
    if not годы:
        return None
    капитал = _num((годы[-1].get("liabilities") or {}).get("capitals"))
    if капитал >= 0:
        return None
    return Trigger(
        key="negative_capital",
        title="Собственный капитал отрицательный",
        explanation="Накопленные убытки превысили капитал — компания живёт на заёмные средства",
        section="finances",
        weight=4,
        evidence=(f"капитал за {годы[-1]['common']['year']} — {_money(капитал)}",),
        fields=("finReports[].liabilities.capitals",),
        tags=("финансы",),
    )


def receivables_over_revenue(record: dict) -> Trigger | None:
    """Покупатели должны больше, чем компания зарабатывает за год.

    Считается от выручки, а не от остатка на счету: сравнение с деньгами даёт
    62 компании из 200, то есть описывает расчёты в экономике, а не компанию.
    """
    годы = _years(record)
    if not годы:
        return None
    оборотные = ((годы[-1].get("assets") or {}).get("currentAssets")) or {}
    дебиторка = _num(оборотные.get("receivables"))
    выручка = _num((годы[-1].get("common") or {}).get("proceeds"))
    if выручка <= 0 or дебиторка <= выручка:
        return None
    return Trigger(
        key="receivables_over_revenue",
        title="Долги покупателей больше годовой выручки",
        explanation="Деньги за отгруженное не собраны дольше года — их может не хватить на расчёты",
        section="finances",
        weight=3,
        evidence=(
            f"дебиторская задолженность {_money(дебиторка)}",
            f"выручка за {годы[-1]['common']['year']} — {_money(выручка)}",
        ),
        fields=(
            "finReports[].assets.currentAssets.receivables",
            "finReports[].common.proceeds",
        ),
        tags=("финансы",),
    )


def stale_reporting(record: dict) -> Trigger | None:
    """Отчётность есть, но позапрошлогодняя.

    Карточка пишет «Выручка за 2023» и не сообщает, что 2023 — это два года
    назад: год стоит подписью, а не выводом.
    """
    годы = _years(record)
    if not годы:
        return None
    последний = годы[-1]["common"]["year"]
    прошло = ГОД_НАБОРА - int(последний)
    if прошло < ЛЕТ_МОЛЧАНИЯ:
        return None
    return Trigger(
        key="stale_reporting",
        title="Свежей отчётности нет",
        explanation=f"Последняя сданная отчётность за {последний} год, с тех пор прошло {прошло}",
        section="finances",
        weight=3,
        evidence=(f"последний отчётный год — {последний}",),
        fields=("finReports[].common.year",),
        tags=("финансы", "данные"),
    )


def no_reporting(record: dict) -> Trigger | None:
    """Отчётности нет вовсе, и это юридическое лицо.

    У ИП её не бывает по устройству формы — там это не сигнал, а норма,
    и раздел честно пишет «не применимо». У юрлица отсутствие — уже вопрос.
    """
    if _is_entrepreneur(record) or record.get("finReports"):
        return None
    return Trigger(
        key="no_reporting",
        title="Бухгалтерской отчётности нет",
        explanation="Юридическое лицо сдаёт отчётность ежегодно — здесь её нет ни за один год",
        section="finances",
        weight=3,
        evidence=("ни одного отчётного года в данных",),
        fields=("finReports",),
        tags=("финансы", "данные"),
    )


def thin_capital(record: dict) -> Trigger | None:
    """Уставный капитал минимальный при крупных исках.

    Уставный капитал — то, чем участники отвечают по обязательствам. Ничто
    в отчёте не ставит 10 000 ₽ рядом с миллионными требованиями.
    """
    капитал = _num((record.get("foundersInfo") or {}).get("shareCapital"))
    ответчику = _sum_by_role(record, "defandantArbitration")
    if not (0 < капитал <= МИНИМАЛЬНЫЙ_КАПИТАЛ) or ответчику <= 10e6:
        return None
    return Trigger(
        key="thin_capital",
        title="Уставный капитал минимальный при крупных исках",
        explanation="Ответственность участников ограничена суммой, несопоставимой с требованиями",
        section="management",
        weight=3,
        evidence=(f"уставный капитал {_money(капитал)}", f"предъявлено {_money(ответчику)}"),
        fields=("foundersInfo.shareCapital", "arbitrationByStatus.defandantArbitration"),
        tags=("управление", "суды"),
    )


RULES = (
    status_note,
    lights_silent,
    receiver_in_charge,
    claims_over_revenue,
    negative_capital,
    receivables_over_revenue,
    stale_reporting,
    no_reporting,
    thin_capital,
)


def build(record: dict) -> tuple[Trigger, ...]:
    """Все сработавшие противоречия, по убыванию значимости.

    Пустой результат — это ответ, а не отсутствие ответа: у 147 компаний
    из 200 не срабатывает ни одно правило, и интерфейс говорит об этом словами.
    """
    сработали = [t for правило in RULES if (t := правило(record)) is not None]
    сработали.sort(key=lambda t: (-t.weight, t.key))
    return tuple(сработали)


# ─────────────────────────── порядок по вопросу ───────────────────────────
#
# Вопрос пользователя меняет порядок, но не состав. Скрывать сработавшее
# противоречие потому, что спросили про другое, опасно: спросивший про выручку
# не должен пропустить банкротство.
#
# Намерения взяты из `docs/roles_situations.md` — там они отобраны и подтверждены
# кейсодателем, а не придуманы под этот модуль.
#
# Разбирается правилами, а не моделью: вызов на каждый вопрос стоил бы задержки
# и токенов ради упорядочивания списка из пяти строк.


@dataclass(frozen=True)
class Intent:
    key: str
    tags: tuple[str, ...]
    patterns: tuple[str, ...]


INTENTS = (
    Intent(
        key="deferral",  # «согласовать отсрочку 60 дней на 3 млн»
        tags=("финансы", "взыскания"),
        patterns=("отсроч", "рассроч", "постоплат", "товарн", "кредит", "заплат", "расплат"),
    ),
    Intent(
        key="prepayment",  # «менеджер принёс договор, аванс 40%»
        tags=("надёжность", "управление", "финансы"),
        patterns=("аванс", "предоплат", "переве", "деньги вперёд", "залог"),
    ),
    Intent(
        key="lights_doubt",  # «светофор зелёный, но контрагент смущает»
        tags=("надёжность", "суды"),
        patterns=("светофор", "оценк", "зелён", "скоринг", "зск", "риск"),
    ),
    Intent(
        key="delivery",  # «не отдать аванс тому, кто не поставит»
        tags=("суды", "управление"),
        patterns=("постав", "отгруз", "исполн", "сорв", "подряд", "работ"),
    ),
)

GENERAL = Intent(key="general", tags=(), patterns=())


def intent_of(question: str) -> Intent:
    """Намерение вопроса. Неузнанный вопрос даёт `general` — порядок остаётся
    по значимости, как без вопроса."""
    текст = (question or "").lower()
    for намерение in INTENTS:
        if any(слово in текст for слово in намерение.patterns):
            return намерение
    return GENERAL


def order_for(
    triggers: tuple[Trigger, ...], question: str, tags: tuple[str, ...] = ()
) -> tuple[Trigger, ...]:
    """Тот же состав, другой порядок: совпавшие по тегам поднимаются наверх.

    Внутри каждой группы порядок прежний — по значимости, затем по ключу,
    чтобы одинаковые вопросы давали одинаковый ответ.

    `tags` — теги сохранённых условий сделки (`core.deal.tags`). Намерение
    читается из текущей реплики и живёт ровно один вопрос; условия сделки
    названы один раз и действуют весь разговор, поэтому складываются, а не
    заменяют друг друга: вопрос «а суды?» при отсрочке должен остаться
    вопросом человека, который даёт отсрочку.
    """
    намерение = intent_of(question)
    нужные = set(намерение.tags) | set(tags)
    if not нужные:
        return triggers
    return tuple(
        sorted(triggers, key=lambda t: (0 if нужные & set(t.tags) else 1, -t.weight, t.key))
    )

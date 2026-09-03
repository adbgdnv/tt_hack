"""Отбор полей отчёта под передачу в модель.

Зачем: сырой отчёт — от 1 500 до 79 500 токенов (медиана ~3 300). Бесплатный тариф
Groq даёт 8 000 токенов в минуту, то есть один тяжёлый отчёт занимает всю минуту,
а самый крупный не влезает вовсе. После отбора медиана — 257 токенов, худший случай —
204. Сжатие от 74 до 390 раз, батч из десяти компаний укладывается в 2 519 токенов.

Это не оптимизация, а условие работоспособности. И тот же слой нужен продукту по сути:
свернуть пятнадцать подтверждений «ничего плохого нет» в одну строку.
"""

from typing import Any

_MONGO_NUMBER_KEYS = ("$numberLong", "$numberInt", "$numberDouble")


def num(v: Any) -> float:
    """Приводит значение к числу, разворачивая обёртки MongoDB."""
    if isinstance(v, dict):
        for k in _MONGO_NUMBER_KEYS:
            if k in v:
                return float(v[k])
        return 0.0
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def unwrap(o: Any) -> Any:
    """Рекурсивно разворачивает {"$numberLong": "..."} в числа.

    Суммы больше 2^31 приходят обёрнутыми — и это ровно самые крупные дела
    (4,5 и 3,0 млрд рублей). Без разворачивания модель видит словарь вместо суммы.
    """
    if isinstance(o, dict):
        for k in _MONGO_NUMBER_KEYS:
            if k in o:
                v = float(o[k])
                return int(v) if v.is_integer() else v
        return {k: unwrap(v) for k, v in o.items()}
    if isinstance(o, list):
        return [unwrap(x) for x in o]
    return o


def slim(report: dict) -> dict:
    """Оставляет из отчёта только то, что нужно для вывода о контрагенте."""
    b = report["baseInfo"]
    arb = report.get("arbitrationByStatus") or {}
    # defandant — опечатка в схеме источника, не наша
    defendant = arb.get("defandantArbitration") or {}
    proceedings = report.get("executionProceedings") or []
    fin = (report.get("finReports") or [None])[0]
    name = b.get("shortName") or ""

    as_defendant = round(
        sum(
            num((defendant.get(block) or {}).get(field))
            for block, field in (
                ("defandantArbitrationFinished", "dfAmount"),
                ("defandantArbitrationPending", "dpAmount"),
                ("defandantArbitrationAppealed", "daAmount"),
            )
        )
    )
    active = [p for p in proceedings if p.get("active")]

    return {
        "название": name,
        "инн": b.get("inn"),
        # у ИП не бывает учредителей, УК и бухотчётности — агент должен говорить
        # «у ИП такого не бывает», а не «данных нет»
        "форма": "ИП" if name.startswith("ИП") else "юрлицо",
        "лет_с_регистрации": (b.get("registrationInfo") or {}).get("yearsFromRegistration"),
        "статус": (report.get("status") or {}).get("status"),
        "риск_банка": b.get("riskLevel"),
        "светофор_зск": report.get("zskRiskLevel"),
        "негативные_факторы": [
            x["code"] for x in (report["reputationalRisks"].get("negative") or [])
        ],
        "арбитраж_всего_дел": int(num(arb.get("commonCount"))) or None,
        "арбитраж_всего_сумма": round(num(arb.get("commonAmount"))) or None,
        "как_ответчик_сумма": as_defendant or None,
        "производств_активных": len(active) or None,
        "производств_сумма_активных": round(sum(num(p.get("amount")) for p in active)) or None,
        "финотчётность": unwrap(fin),
        "коэффициенты": unwrap(report.get("coefficient")),
        "основной_оквэд": (
            (report.get("kindsOfActivityInfo") or {}).get("mainKindOfActivity") or {}
        ).get("description"),
    }

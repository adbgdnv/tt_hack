from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from evals.schema import EvalCase

CORE_DISTRIBUTION = {
    "bank_unknown": 6,
    "unknown_with_signals": 4,
    "large_numbers": 5,
    "risk_conflict": 5,
    "not_applicable": 4,
    "empty": 4,
    "bank_scale": 1,
    "zsk_source": 1,
    "rating_methodology": 1,
    "chart_routing": 3,
}

_CHART_QUESTIONS = {
    "profit_years": "Покажи, как менялась прибыль компании по годам.",
    "arbitration_years": "Покажи суммы исков по годам.",
    "proceedings_years": "Покажи, когда возбуждались исполнительные производства.",
}


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _state_value(state: Any) -> str:
    return str(getattr(state, "value", state)).lower()


def _inn(record: dict) -> str:
    return str((record.get("baseInfo") or {}).get("inn") or "").strip()


def _risk(record: dict) -> str:
    return str((record.get("baseInfo") or {}).get("riskLevel") or "").upper()


def _zsk(record: dict) -> str:
    return str(record.get("zskRiskLevel") or "").upper()


def _negatives(record: dict) -> tuple[dict, ...]:
    return tuple((record.get("reputationalRisks") or {}).get("negative") or ())


def _court_amount(record: dict) -> float:
    return _num((record.get("arbitrationByStatus") or {}).get("commonAmount"))


# Как модель назовёт факт своими словами — по одному выражению на каждый из
# пятнадцати негативных кодов (их полный список — `core.factors.HEADINGS`).
#
# Дословный заголовок отчёта требовать нельзя: на «Ответчик в арбитраже» модель
# отвечает «1 525 дел, из них как ответчик — 2,69 млрд ₽», и проверка дословности
# заваливает правильный ответ. Выводить основы слов автоматически — тоже мимо:
# из «Много кодов ОКВЭД» получаются огрызки «мно» и «код», под которые подходит
# любой текст. Поэтому карта написана руками и читается в отчёте о провале.
_SIGNAL_PATTERNS: dict[str, str] = {
    "arbitrationDefendant": r"ответчик|арбитраж|судебн\w+ дел",
    "massOkved": r"ОКВЭД",
    "executionProceedings": r"исполнительн\w+ производств",
    "massAddress": r"массов\w+ адрес",
    "fnsBlocking": r"блокиров\w*\s+счет|счет\w*\s+заблокир|приостановлен\w+ операц",
    "profit": r"убыт",
    "invalidRegistrationData": r"недостоверн\w+ (?:регистрационн\w+ )?(?:данн|сведен)",
    "invalidAddress": r"фиктивн\w+ адрес|недостоверн\w+ адрес",
    "massAuthpersons": r"массов\w+ (?:директор|учредител|руководител)",
    "invalidAuthpersonsData": r"номинальн\w+ (?:руководител|директор)",
    "currentAssets": r"оборотн\w+ актив",
    "liquidationStatus": r"банкротств|ликвидац",
    "dishonestProvider": r"недобросовестн\w+ поставщик",
    "taxArrears": r"должник ФНС|задолженност\w*\s+(?:по )?налог|налогов\w+ задолженност",
    "inspectionWithViolation": r"проверк\w*.{0,40}нарушени|нарушени\w*.{0,40}проверк",
}


def _signal_pattern(record: dict) -> str:
    """Регексп «назван хотя бы один реальный сигнал этой компании».

    Достаточно любого из найденных фактов: требовать перечисления всех — значит
    проверять полноту пересказа, а не то, что агент вообще посмотрел в данные.
    Незнакомый код молча пропускается: набор кодов может пополниться, и это не
    повод уронить сборку.
    """
    parts = [
        _SIGNAL_PATTERNS[code]
        for factor in _negatives(record)
        if (code := str(factor.get("code") or "")) in _SIGNAL_PATTERNS
    ]
    return "|".join(dict.fromkeys(parts))


def _case(raw: dict) -> EvalCase:
    return EvalCase.from_dict(raw)


def _take(items: list[Any], count: int, category: str) -> list[Any]:
    if len(items) < count:
        raise RuntimeError(
            f"eval dataset has insufficient coverage for {category}: "
            f"need {count}, found {len(items)}"
        )
    return items[:count]


def build_core_suite(
    records: Iterable[dict],
    build_report_fn: Callable[[dict], Any],
    build_charts_fn: Callable[[dict], Iterable[Any]],
) -> list[EvalCase]:
    """Build the fixed 34-case regression/risk suite from canonical project data."""
    rows = [record for record in records if _inn(record)]
    reports = {_inn(record): build_report_fn(record) for record in rows}
    cases: list[EvalCase] = []

    unknown = sorted((r for r in rows if _risk(r) == "UNKNOWN"), key=_inn)
    for record in _take(unknown, CORE_DISTRIBUTION["bank_unknown"], "bank_unknown"):
        inn = _inn(record)
        cases.append(
            _case(
                {
                    "id": f"bank-unknown-{inn}",
                    "suite": "risk",
                    "category": "bank_unknown",
                    "inn": inn,
                    "turns": [{"user": "Как банк оценивает риск этой компании?"}],
                    "expect": {
                        "required_patterns": [
                            "оценить невозможно|оценки нет|нет данных для оценки"
                        ],
                        # Ловим ошибку «пустая оценка банка выдана за низкий риск»,
                        # а не сами слова «низкий риск»: у этих же компаний зелёный
                        # ЗСК, и фраза «зелёный — низкий риск вовлечённости в
                        # подозрительные операции» верна и относится к другому
                        # светофору. Запрет без привязки к банку заваливал за неё
                        # правильные ответы (прогон 2026-09-05).
                        "forbidden_patterns": [
                            r"(?:скоринг|оценка|модель)\s+банка[^.]{0,60}низк",
                            r"банк\w*\s+(?:присвоил|оценил|поставил|считает|относит)"
                            r"[^.]{0,60}низк",
                            "рисков нет",
                            "безопасн",
                        ],
                    },
                }
            )
        )

    # Пустой светофор банка при живых сигналах в самом отчёте — случай МАКСМАРКЕТ,
    # только светофор не зелёный, а вовсе не выставлен. `bank_unknown` выше проверяет
    # лишь отрицательное условие («не называть это низким риском»); здесь проверяется
    # положительное: агент обязан назвать конкретный найденный факт, а не остановиться
    # на «банк не оценил». Это и есть обещанный продуктом второй, независимый вердикт.
    signals = [(record, pattern) for record in unknown if (pattern := _signal_pattern(record))]
    signals.sort(
        key=lambda item: (-len(_negatives(item[0])), -_court_amount(item[0]), _inn(item[0]))
    )
    for record, pattern in _take(
        signals, CORE_DISTRIBUTION["unknown_with_signals"], "unknown_with_signals"
    ):
        inn = _inn(record)
        cases.append(
            _case(
                {
                    "id": f"unknown-with-signals-{inn}",
                    "suite": "risk",
                    "category": "unknown_with_signals",
                    "inn": inn,
                    "turns": [
                        {"user": "Раз у банка нет оценки риска, значит проверять больше нечего?"}
                    ],
                    # Конкретных чисел здесь не требуем: вопрос не про сумму, и агент
                    # вправе назвать ту величину, которая уместнее — например, сумму
                    # только по роли ответчика вместо общей. Точность чисел проверяет
                    # `large_numbers`, где вопрос прямо просит общую сумму.
                    "expect": {
                        "required_patterns": [pattern],
                        "forbidden_patterns": ["рисков нет", "всё чисто", "проверять нечего"],
                    },
                }
            )
        )

    large = sorted(rows, key=lambda r: (-_court_amount(r), _inn(r)))
    large = [record for record in large if _court_amount(record) >= 1_000_000_000]
    for record in _take(large, CORE_DISTRIBUTION["large_numbers"], "large_numbers"):
        inn = _inn(record)
        cases.append(
            _case(
                {
                    "id": f"large-courts-{inn}",
                    "suite": "regression",
                    "category": "large_numbers",
                    "inn": inn,
                    "turns": [
                        {"user": "На какую общую сумму компания участвует в судебных делах?"}
                    ],
                    "expect": {"numbers": [_court_amount(record)]},
                }
            )
        )

    conflict_candidates = []
    for record in rows:
        if _risk(record) != "LOW" or not _negatives(record):
            continue
        pattern = _signal_pattern(record)
        if pattern:
            conflict_candidates.append((record, pattern))
    conflict_candidates.sort(
        key=lambda item: (-len(_negatives(item[0])), -_court_amount(item[0]), _inn(item[0]))
    )
    for record, pattern in _take(
        conflict_candidates, CORE_DISTRIBUTION["risk_conflict"], "risk_conflict"
    ):
        inn = _inn(record)
        cases.append(
            _case(
                {
                    "id": f"low-with-signals-{inn}",
                    "suite": "regression",
                    "category": "risk_conflict",
                    "inn": inn,
                    "turns": [
                        {"user": "У компании низкий риск. Значит всё нормально и можно работать?"}
                    ],
                    "expect": {
                        "required_patterns": [pattern],
                        "forbidden_patterns": [
                            r"можно\s+(?:с\s+ней\s+)?работать",
                            "сотрудничеств.*безопасн",
                            "рисков нет",
                            "дополнительн.*(?:анализ|провер).*не треб",
                            "не стоит сотрудничать|не работайте",
                        ],
                    },
                }
            )
        )

    entrepreneurs = sorted(
        (record for record in rows if getattr(reports[_inn(record)], "is_entrepreneur", False)),
        key=_inn,
    )
    for record in _take(entrepreneurs, CORE_DISTRIBUTION["not_applicable"], "not_applicable"):
        inn = _inn(record)
        cases.append(
            _case(
                {
                    "id": f"ip-not-applicable-{inn}",
                    "suite": "risk",
                    "category": "not_applicable",
                    "inn": inn,
                    "turns": [{"user": "Почему нет бухгалтерской отчётности и учредителей?"}],
                    "expect": {
                        "required_patterns": [
                            "ИП|индивидуальн.*предпринимател",
                            "не примен|не бывает",
                        ],
                        "forbidden_patterns": ["рисков нет|всё чисто"],
                    },
                }
            )
        )

    empty_candidates: list[tuple[str, Any]] = []
    seen_empty_inn: set[str] = set()
    for record in sorted(rows, key=_inn):
        inn = _inn(record)
        for section in getattr(reports[inn], "sections", ()):
            if _state_value(getattr(section, "state", "")) != "empty":
                continue
            if inn in seen_empty_inn:
                break
            empty_candidates.append((inn, section))
            seen_empty_inn.add(inn)
            break
    for inn, section in _take(empty_candidates, CORE_DISTRIBUTION["empty"], "empty"):
        title = str(getattr(section, "title", getattr(section, "key", "раздел")))
        cases.append(
            _case(
                {
                    "id": f"empty-{getattr(section, 'key', 'section')}-{inn}",
                    "suite": "risk",
                    "category": "empty",
                    "inn": inn,
                    "turns": [{"user": f"По разделу «{title}» всё чисто?"}],
                    "expect": {
                        # «Нет данных» говорят по-разному: «отчётности нет ни за один
                        # год», «нельзя оценить выручку», «раздел пустой». Требовать
                        # одну формулировку — значит валить правильные ответы за
                        # синоним (прогон 2026-09-05).
                        "required_patterns": [
                            r"(?:данн\w+|отчётност\w+|сведени\w+|информаци\w+)\s+"
                            r"(?:нет|отсутству\w+)"
                            r"|нет\s+(?:данных|отчётности|сведений|информации)"
                            r"|(?:нельзя|невозможно)\s+оценить"
                            r"|оценить\s+(?:нельзя|невозможно)"
                            r"|недостаточно данных"
                            r"|раздел\w*\s+пуст"
                        ],
                        "forbidden_patterns": ["рисков нет|всё чисто|нарушений нет"],
                    },
                }
            )
        )

    low = next((record for record in sorted(rows, key=_inn) if _risk(record) == "LOW"), None)
    if low is None:
        raise RuntimeError("eval dataset has no LOW bank-risk company for bank_scale")
    cases.append(
        _case(
            {
                "id": f"bank-scale-{_inn(low)}",
                "suite": "regression",
                "category": "bank_scale",
                "inn": _inn(low),
                "turns": [{"user": "Что означает низкая оценка риска банка?"}],
                "expect": {
                    "required_patterns": ["низк.*(?:риск|уров)|меньше.*риск"],
                    "forbidden_patterns": ["низк.*(?:означает|подтверждает).*высок.*риск"],
                },
            }
        )
    )

    zsk = next(
        (record for record in sorted(rows, key=_inn) if _zsk(record) in {"YELLOW", "RED"}), None
    )
    if zsk is None:
        raise RuntimeError("eval dataset has no YELLOW/RED ZSK company for zsk_source")
    cases.append(
        _case(
            {
                "id": f"zsk-source-{_inn(zsk)}",
                "suite": "regression",
                "category": "zsk_source",
                "inn": _inn(zsk),
                "turns": [{"user": "Кто выставляет оценку ЗСК и что она оценивает?"}],
                "expect": {
                    "required_patterns": [
                        "Банк России|ЦБ|Знай своего клиента",
                        "подозрительн.*операц|вовлеченн.*операц",
                    ]
                },
            }
        )
    )

    known = next(
        (record for record in sorted(rows, key=_inn) if _risk(record) in {"LOW", "MEDIUM", "HIGH"}),
        None,
    )
    if known is None:
        raise RuntimeError("eval dataset has no known bank-risk company for rating_methodology")
    cases.append(
        _case(
            {
                "id": f"rating-methodology-{_inn(known)}",
                "suite": "regression",
                "category": "rating_methodology",
                "inn": _inn(known),
                "turns": [{"user": "Почему банк поставил компании именно такую оценку риска?"}],
                "expect": {
                    "required_patterns": [
                        "методик.*не раскры|причин.*не зна|точн.*критери.*неизвест"
                    ],
                    "forbidden_patterns": ["потому что.*(?:просроч|стабил|дефолт)"],
                },
            }
        )
    )

    chart_records: dict[str, dict] = {}
    for record in sorted(rows, key=_inn):
        available = {str(getattr(chart, "key", "")) for chart in build_charts_fn(record)}
        for key in _CHART_QUESTIONS:
            if key in available and key not in chart_records:
                chart_records[key] = record
    missing_charts = [key for key in _CHART_QUESTIONS if key not in chart_records]
    if missing_charts:
        raise RuntimeError(
            f"eval dataset has no companies for chart kinds: {', '.join(missing_charts)}"
        )
    for key, question in _CHART_QUESTIONS.items():
        record = chart_records[key]
        inn = _inn(record)
        cases.append(
            _case(
                {
                    "id": f"chart-{key}-{inn}",
                    "suite": "regression",
                    "category": "chart_routing",
                    "inn": inn,
                    "turns": [{"user": question}],
                    "expect": {
                        "required_tools": [{"name": "show_chart", "params": {"kind": key}}]
                    },
                }
            )
        )

    expected_total = sum(CORE_DISTRIBUTION.values())
    if len(cases) != expected_total:
        raise RuntimeError(f"core eval suite must contain {expected_total} cases, got {len(cases)}")
    return cases


def write_jsonl(cases: Iterable[EvalCase], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case.to_dict(), ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the fixed 30-case offline eval suite")
    parser.add_argument("--output", default="evals/datasets/generated.jsonl")
    args = parser.parse_args()

    from core import repo
    from core.charts import build_charts
    from core.report import build

    cases = build_core_suite(repo.all(), build, build_charts)
    write_jsonl(cases, Path(args.output))
    print(f"generated {len(cases)} eval cases -> {args.output}")


if __name__ == "__main__":
    main()

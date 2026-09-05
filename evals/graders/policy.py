from __future__ import annotations

import re

from evals.schema import EvalCase, EvalTrace, GradeResult

# Разметку снимаем перед сравнением: модель выделяет отрицание жирным
# («это **не** низкий риск»), и без нормализации между «не» и запрещённой
# фразой оказываются звёздочки — проверка отрицания промахивается.
_MARKUP = re.compile(r"[*_`]+")

# Отрицание непосредственно перед фразой: «это не низкий риск». Кавычки и скобки
# между отрицанием и фразой допускаются — модель часто закавычивает то, что
# опровергает: «это не „всё чисто“».
_NEGATION_BEFORE = re.compile(r"\b(?:не|ни)\s*[«\"'„(\[]*\s*$", re.IGNORECASE)
# Отрицание через оборот: «отсутствие оценки не значит, что рисков нет»,
# «нельзя сказать, что проверять нечего».
_NEGATION_CLAUSE = re.compile(
    r"\b(?:не\s+(?:значит|означа\w*|говорит\w*|гарантир\w*|равн\w*|исключа\w*)"
    r"|нельзя\s+(?:сказать|утверждать|считать|заключ\w*|делать)"
    r"|неверно|ошибочно)\b",
    re.IGNORECASE,
)
_LOOKBEHIND = 80


def _normalize(text: str) -> str:
    return _MARKUP.sub("", text)


def _negated(text: str, start: int) -> bool:
    """Опровергает ли текст перед совпадением саму запрещённую фразу.

    Запрещённые паттерны ловят утверждения («рисков нет», «низкий риск»), но
    правильный ответ часто содержит ту же фразу с отрицанием — «это не низкий
    риск», «отсутствие данных не значит, что рисков нет». Без этой проверки
    образцовый ответ падает как критическое нарушение: именно так все шесть
    кейсов `bank_unknown` были помечены провальными на прогоне 2026-09-05.

    Область поиска ограничена текущим предложением: отрицание из соседней
    фразы к этому утверждению уже не относится.
    """
    window = text[max(0, start - _LOOKBEHIND) : start]
    sentence = re.split(r"[.!?\n;]", window)[-1]
    return bool(_NEGATION_BEFORE.search(sentence) or _NEGATION_CLAUSE.search(sentence))


def _forbidden_hit(pattern: str, text: str) -> str | None:
    """Первое утверждающее совпадение запрета или None, если все опровергнуты."""
    for match in re.finditer(pattern, text, re.IGNORECASE):
        if not _negated(text, match.start()):
            return match.group(0)
    return None


def grade_policy(case: EvalCase, trace: EvalTrace) -> GradeResult:
    text = _normalize("\n".join(trace.answers))
    missing = [
        pattern
        for pattern in case.expect.required_patterns
        if not re.search(pattern, text, re.IGNORECASE)
    ]
    hits = [
        (pattern, hit)
        for pattern in case.expect.forbidden_patterns
        if (hit := _forbidden_hit(pattern, text)) is not None
    ]
    checks = len(case.expect.required_patterns) + len(case.expect.forbidden_patterns)
    failures = len(missing) + len(hits)
    score = 1.0 if checks == 0 else max(0.0, (checks - failures) / checks)
    details = tuple(
        [
            *(f"missing:{x}" for x in missing),
            *(f"forbidden:{pattern} → «{hit[:60]}»" for pattern, hit in hits),
        ]
    )
    return GradeResult(
        "policy",
        not missing and not hits,
        score,
        # Критично именно сработавшее запрещённое утверждение, а не сам факт,
        # что у кейса есть список запретов: иначе пропущенная обязательная
        # формулировка обнуляла бы кейс наравне с выданным вердиктом.
        critical=bool(hits),
        details=details,
    )

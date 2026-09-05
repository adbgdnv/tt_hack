from __future__ import annotations

import re

from evals.schema import EvalCase, EvalTrace, GradeResult

_NUMBER = re.compile(
    r"(?<!\w)(\d[\d\s]*(?:[.,]\d+)?)\s*(млрд|миллиард(?:а|ов)?|млн|миллион(?:а|ов)?)?",
    re.IGNORECASE,
)
_MULTIPLIER = {
    "млрд": 1_000_000_000,
    "миллиард": 1_000_000_000,
    "миллиарда": 1_000_000_000,
    "миллиардов": 1_000_000_000,
    "млн": 1_000_000,
    "миллион": 1_000_000,
    "миллиона": 1_000_000,
    "миллионов": 1_000_000,
}


def extract_numbers(text: str) -> tuple[float, ...]:
    values = []
    for match in _NUMBER.finditer(text):
        raw, unit = match.groups()
        compact = raw.replace(" ", "").replace(",", ".")
        try:
            value = float(compact)
        except ValueError:
            continue
        values.append(value * _MULTIPLIER.get((unit or "").lower(), 1))
    return tuple(values)


def _matches(expected: float, actual: float) -> bool:
    tolerance = max(abs(expected) * 0.02, 1.0)
    return abs(expected - actual) <= tolerance


def grade_numbers(case: EvalCase, trace: EvalTrace) -> GradeResult:
    expected = case.expect.numbers
    if not expected:
        return GradeResult("numbers", True, 1.0)

    actual = extract_numbers("\n".join(trace.answers))
    hits = [value for value in expected if any(_matches(value, candidate) for candidate in actual)]
    score = len(hits) / len(expected)
    missing = tuple(
        str(int(value) if value.is_integer() else value) for value in expected if value not in hits
    )
    return GradeResult("numbers", score == 1.0, score, details=missing)

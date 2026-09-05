from __future__ import annotations

import re

from evals.schema import EvalCase, EvalTrace, GradeResult


def grade_policy(case: EvalCase, trace: EvalTrace) -> GradeResult:
    text = "\n".join(trace.answers)
    missing = [
        pattern
        for pattern in case.expect.required_patterns
        if not re.search(pattern, text, re.IGNORECASE)
    ]
    forbidden = [
        pattern
        for pattern in case.expect.forbidden_patterns
        if re.search(pattern, text, re.IGNORECASE)
    ]
    checks = len(case.expect.required_patterns) + len(case.expect.forbidden_patterns)
    failures = len(missing) + len(forbidden)
    score = 1.0 if checks == 0 else max(0.0, (checks - failures) / checks)
    details = tuple([*(f"missing:{x}" for x in missing), *(f"forbidden:{x}" for x in forbidden)])
    return GradeResult(
        "policy",
        not missing and not forbidden,
        score,
        critical=bool(case.expect.forbidden_patterns),
        details=details,
    )

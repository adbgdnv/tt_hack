from __future__ import annotations

from evals.schema import CaseResult, EvalTrace, GradeResult


def aggregate_case(case_id: str, trace: EvalTrace, grades: tuple[GradeResult, ...]) -> CaseResult:
    if trace.infra_errors:
        return CaseResult(case_id, "infra_error", None, grades, trace.infra_errors)
    seen = {"answers": trace.answers, "charts": trace.charts}
    if any(grade.critical and not grade.passed for grade in grades):
        return CaseResult(case_id, "failed", 0.0, grades, **seen)
    if not grades:
        return CaseResult(case_id, "passed", 1.0, grades, **seen)
    score = sum(grade.score for grade in grades) / len(grades)
    status = "passed" if all(grade.passed for grade in grades) else "failed"
    return CaseResult(case_id, status, score, grades, **seen)

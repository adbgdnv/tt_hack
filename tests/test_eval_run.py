import json
from pathlib import Path

from evals.run import load_cases, summarize
from evals.schema import CaseResult, GradeResult


def test_load_cases_filters_suite(tmp_path: Path):
    path = tmp_path / "cases.jsonl"
    rows = [
        {"id": "a", "suite": "regression", "inn": "1", "turns": [{"user": "q"}]},
        {"id": "b", "suite": "risk", "inn": "2", "turns": [{"user": "q"}]},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    cases = load_cases(path, suite="regression")
    assert [case.id for case in cases] == ["a"]


def test_summary_separates_infra_and_agent_failures():
    results = [
        CaseResult("a", "passed", 1.0, (GradeResult("x", True, 1.0),)),
        CaseResult("b", "failed", 0.5, (GradeResult("x", False, 0.5),)),
        CaseResult("c", "infra_error", None, (), ("groq:429",)),
    ]

    summary = summarize(results)
    assert summary == {
        "cases": 3,
        "evaluated": 2,
        "passed": 1,
        "failed": 1,
        "infra_errors": 1,
        "pass_rate": 0.5,
        "mean_score": 0.75,
    }

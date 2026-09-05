from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path

from evals.graders.aggregate import aggregate_case
from evals.graders.numbers import grade_numbers
from evals.graders.policy import grade_policy
from evals.graders.tools import grade_tools
from evals.runners.current_agent import CurrentAgentRunner
from evals.schema import CaseResult, EvalCase


def load_cases(path: Path, suite: str | None = None, limit: int | None = None) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                case = EvalCase.from_dict(json.loads(line))
            except (json.JSONDecodeError, ValueError, KeyError) as exc:
                raise ValueError(f"invalid eval case at {path}:{line_number}: {exc}") from exc
            if suite and case.suite != suite:
                continue
            cases.append(case)
            if limit is not None and len(cases) >= limit:
                break
    return cases


async def evaluate_case(case: EvalCase, runner: CurrentAgentRunner) -> CaseResult:
    trace = await runner.run(case)
    grades = (
        grade_numbers(case, trace),
        grade_tools(case, trace),
        grade_policy(case, trace),
    )
    return aggregate_case(case.id, trace, grades)


async def evaluate(
    cases: Iterable[EvalCase], runner: CurrentAgentRunner | None = None
) -> list[CaseResult]:
    runner = runner or CurrentAgentRunner()
    results = []
    for case in cases:
        results.append(await evaluate_case(case, runner))
    return results


def summarize(results: Iterable[CaseResult]) -> dict:
    rows = list(results)
    evaluated = [row for row in rows if row.status != "infra_error"]
    scores = [row.score for row in evaluated if row.score is not None]
    passed = sum(row.status == "passed" for row in evaluated)
    failed = sum(row.status == "failed" for row in evaluated)
    return {
        "cases": len(rows),
        "evaluated": len(evaluated),
        "passed": passed,
        "failed": failed,
        "infra_errors": sum(row.status == "infra_error" for row in rows),
        "pass_rate": round(passed / len(evaluated), 4) if evaluated else None,
        "mean_score": round(sum(scores) / len(scores), 4) if scores else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run live agent evals against a JSONL dataset")
    parser.add_argument("--dataset", default="evals/datasets/generated.jsonl")
    parser.add_argument("--suite", choices=("golden", "regression", "risk", "online"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", help="Optional JSON file with per-case results and summary")
    args = parser.parse_args()

    cases = load_cases(Path(args.dataset), suite=args.suite, limit=args.limit)
    if not cases:
        raise SystemExit(
            "No eval cases matched. Build the dataset first with: python -m evals.build_cases"
        )

    results = asyncio.run(evaluate(cases))
    summary = summarize(results)
    payload = {"summary": summary, "results": [asdict(result) for result in results]}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.output:
        Path(args.output).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )


if __name__ == "__main__":
    main()

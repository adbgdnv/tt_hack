from __future__ import annotations

from evals.schema import EvalCase, EvalTrace, GradeResult, ToolCall, ToolExpectation


def _matches(expectation: ToolExpectation, call: ToolCall) -> bool:
    return call.name == expectation.name and all(
        call.params.get(k) == v for k, v in expectation.params.items()
    )


def grade_tools(case: EvalCase, trace: EvalTrace) -> GradeResult:
    required = case.expect.required_tools
    forbidden = set(case.expect.forbidden_tools)

    missing = [
        item.name for item in required if not any(_matches(item, call) for call in trace.tool_calls)
    ]
    forbidden_seen = [call.name for call in trace.tool_calls if call.name in forbidden]

    required_by_name: dict[str, tuple[ToolExpectation, ...]] = {}
    for item in required:
        required_by_name.setdefault(item.name, ())
        required_by_name[item.name] = (*required_by_name[item.name], item)

    wrong_params = []
    for call in trace.tool_calls:
        expectations = required_by_name.get(call.name)
        if expectations and not any(_matches(item, call) for item in expectations):
            wrong_params.append(call.name)

    checks = len(required) + len(forbidden) + len(wrong_params)
    failures = len(missing) + len(set(forbidden_seen)) + len(wrong_params)
    score = 1.0 if checks == 0 else max(0.0, (checks - failures) / checks)
    details = tuple(
        [
            *(f"missing:{name}" for name in missing),
            *(f"forbidden:{name}" for name in forbidden_seen),
            *(f"wrong_params:{name}" for name in wrong_params),
        ]
    )
    return GradeResult(
        "tools",
        not missing and not forbidden_seen and not wrong_params,
        score,
        details=details,
    )

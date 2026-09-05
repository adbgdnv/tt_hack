import pytest

from evals.schema import EvalCase, EvalTrace, ToolCall, Turn


def test_case_parses_current_agent_task_without_future_runtime_fields():
    case = EvalCase.from_dict(
        {
            "id": "risk-001",
            "suite": "regression",
            "inn": "1234567890",
            "turns": [{"user": "Стоит работать?"}],
            "expect": {
                "numbers": [2589790444],
                "required_tools": [{"name": "show_chart", "params": {"kind": "profit_years"}}],
                "forbidden_patterns": ["сотрудничество безопасно"],
            },
        }
    )

    assert case.id == "risk-001"
    assert case.turns == (Turn(user="Стоит работать?"),)
    assert case.expect.numbers == (2589790444.0,)
    assert case.expect.required_tools[0].params == {"kind": "profit_years"}
    assert not hasattr(case, "budget")


def test_case_requires_at_least_one_turn():
    with pytest.raises(ValueError, match="turn"):
        EvalCase.from_dict({"id": "x", "suite": "golden", "inn": "1", "turns": []})


def test_trace_contains_only_observable_current_agent_fields():
    trace = EvalTrace(
        answers=("ответ",),
        tool_calls=(ToolCall(name="show_chart", params={"kind": "profit_years"}),),
        charts=("profit_years",),
        sources=(),
        latency_ms=321,
    )

    payload = trace.to_dict()
    assert payload["tool_calls"][0] == {"name": "show_chart", "params": {"kind": "profit_years"}}
    assert payload["answers"] == ["ответ"]
    assert "model_calls" not in payload
    assert "input_tokens" not in payload
    assert "output_tokens" not in payload

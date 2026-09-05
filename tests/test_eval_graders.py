from evals.graders.aggregate import aggregate_case
from evals.graders.numbers import grade_numbers
from evals.graders.policy import grade_policy
from evals.graders.tools import grade_tools
from evals.schema import EvalCase, EvalTrace, GradeResult, ToolCall


def _case(**expect):
    return EvalCase.from_dict(
        {
            "id": "case",
            "suite": "regression",
            "inn": "1",
            "turns": [{"user": "вопрос"}],
            "expect": expect,
        }
    )


def test_number_grader_accepts_billions_with_decimal_comma():
    case = _case(numbers=[2_589_790_444])
    trace = EvalTrace(answers=("Сумма — около 2,59 млрд ₽.",))
    result = grade_numbers(case, trace)
    assert result.passed is True


def test_number_grader_rejects_million_for_expected_billion():
    case = _case(numbers=[2_589_790_444])
    trace = EvalTrace(answers=("Сумма — около 2,59 млн ₽.",))
    result = grade_numbers(case, trace)
    assert result.passed is False


def test_tool_grader_checks_name_params_and_forbidden_tools():
    case = _case(
        required_tools=[{"name": "show_chart", "params": {"kind": "profit_years"}}],
        forbidden_tools=["web_search"],
    )
    ok = EvalTrace(tool_calls=(ToolCall("show_chart", {"kind": "profit_years"}),))
    wrong = EvalTrace(
        tool_calls=(ToolCall("show_chart", {"kind": "revenue_assets"}), ToolCall("web_search", {}))
    )

    assert grade_tools(case, ok).passed is True
    assert grade_tools(case, wrong).passed is False


def test_policy_grader_is_case_insensitive_and_critical():
    case = _case(forbidden_patterns=["сотрудничество безопасно"])
    trace = EvalTrace(answers=("Сотрудничество БЕЗОПАСНО.",))
    result = grade_policy(case, trace)

    assert result.passed is False
    assert result.critical is True


def test_aggregation_hard_fails_on_critical_grade():
    result = aggregate_case(
        "x",
        EvalTrace(),
        (
            GradeResult("numbers", True, 1.0),
            GradeResult("policy", False, 0.0, critical=True),
        ),
    )
    assert result.status == "failed"
    assert result.score == 0.0


def test_aggregation_keeps_infra_errors_separate():
    result = aggregate_case(
        "x",
        EvalTrace(infra_errors=("groq:429",)),
        (GradeResult("numbers", False, 0.0),),
    )
    assert result.status == "infra_error"
    assert result.score is None


def test_tool_grader_rejects_wrong_chart_even_if_agent_later_calls_right_one():
    case = _case(required_tools=[{"name": "show_chart", "params": {"kind": "profit_years"}}])
    trace = EvalTrace(
        tool_calls=(
            ToolCall("show_chart", {"kind": "revenue_assets"}),
            ToolCall("show_chart", {"kind": "profit_years"}),
        )
    )

    result = grade_tools(case, trace)
    assert result.passed is False
    assert any(detail.startswith("wrong_params:show_chart") for detail in result.details)

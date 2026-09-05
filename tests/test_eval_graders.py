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


def test_policy_grader_does_not_fire_on_denied_statement():
    """«Это **не** низкий риск» — опровержение запрещённой фразы, а не нарушение."""
    case = _case(forbidden_patterns=["низк(?:ий|ого) риск|рисков нет|безопасн"])
    trace = EvalTrace(answers=("Оценки нет. Это **не** низкий риск.",))
    result = grade_policy(case, trace)

    assert result.passed is True
    assert result.critical is False


def test_policy_grader_does_not_fire_on_negating_clause():
    case = _case(forbidden_patterns=["рисков нет|всё чисто"])
    trace = EvalTrace(answers=("Отсутствие данных не значит, что рисков нет.",))
    assert grade_policy(case, trace).passed is True


def test_policy_grader_does_not_fire_on_quoted_denial():
    """Опровергаемую формулировку модель обычно берёт в кавычки."""
    case = _case(forbidden_patterns=["всё чисто"])
    trace = EvalTrace(answers=("Отсутствие оценки — это не «всё чисто», а отсутствие данных.",))
    assert grade_policy(case, trace).passed is True


def test_policy_grader_does_not_fire_on_impossibility_clause():
    case = _case(forbidden_patterns=["проверять нечего"])
    trace = EvalTrace(answers=("Нельзя сказать, что проверять нечего: есть суды.",))
    assert grade_policy(case, trace).passed is True


def test_policy_grader_still_fires_on_plain_assertion():
    case = _case(forbidden_patterns=["рисков нет|всё чисто"])
    trace = EvalTrace(answers=("Компания надёжная, рисков нет.",))
    result = grade_policy(case, trace)

    assert result.passed is False
    assert result.critical is True
    assert any("рисков нет" in detail for detail in result.details)


def test_policy_grader_fires_when_denial_is_in_another_sentence():
    """Отрицание из соседнего предложения к утверждению не относится."""
    case = _case(forbidden_patterns=["рисков нет"])
    trace = EvalTrace(answers=("Это не мешает работе. По разделу рисков нет.",))
    assert grade_policy(case, trace).passed is False


def test_policy_grader_missing_required_is_not_critical():
    """Обнуляет кейс выданное запрещённое утверждение, а не пропущенная формулировка."""
    case = _case(
        required_patterns=["оценить невозможно"],
        forbidden_patterns=["рисков нет"],
    )
    trace = EvalTrace(answers=("Банк присвоил компании средний уровень.",))
    result = grade_policy(case, trace)

    assert result.passed is False
    assert result.critical is False


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

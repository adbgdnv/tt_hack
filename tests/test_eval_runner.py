import asyncio
from types import SimpleNamespace

import httpx
import openai
import pytest

from evals.runners.current_agent import CurrentAgentRunner, _retry_after_seconds
from evals.schema import EvalCase


def _rate_limit_error(message: str) -> openai.RateLimitError:
    response = httpx.Response(
        429,
        request=httpx.Request("POST", "https://example.com"),
        json={"error": {"message": message}},
    )
    return openai.RateLimitError(message, response=response, body=None)


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Please try again in 9.44s.", 9.44),
        ("Please try again in 18m54.864s.", 18 * 60 + 54.864),
        ("no timing info here", None),
    ],
)
def test_retry_after_seconds_parses_groq_message(message, expected):
    assert _retry_after_seconds(message) == expected


def test_current_runner_preserves_session_across_turns():
    calls = []

    def get_record(inn):
        return {"inn": inn}

    def build_report(record):
        return SimpleNamespace(inn=record["inn"])

    def get_tools(record, inn):
        return ["tools"]

    class Session:
        def __init__(self, session_id):
            self.session_id = session_id

    async def run_agent(state, report, record, question, tools):
        calls.append((state, question))
        return SimpleNamespace(text=f"answer:{question}", charts=("profit_years",), sources=())

    case = EvalCase.from_dict(
        {
            "id": "multi",
            "suite": "golden",
            "inn": "123",
            "turns": [{"user": "Какая прибыль?"}, {"user": "А годом раньше?"}],
        }
    )
    runner = CurrentAgentRunner(
        get_record=get_record,
        build_report=build_report,
        get_tools=get_tools,
        session_factory=Session,
        run_agent=run_agent,
    )

    trace = asyncio.run(runner.run(case))

    assert trace.answers == ("answer:Какая прибыль?", "answer:А годом раньше?")
    assert calls[0][0] is calls[1][0]
    assert trace.charts == ("profit_years",)


def test_current_runner_retries_transient_rate_limit_and_recovers(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    attempts = {"count": 0}

    async def run_agent(state, report, record, question, tools):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise _rate_limit_error("Please try again in 0.01s.")
        return SimpleNamespace(text="ok", charts=(), sources=())

    case = EvalCase.from_dict(
        {"id": "c", "suite": "golden", "inn": "1", "turns": [{"user": "вопрос"}]}
    )
    runner = CurrentAgentRunner(
        get_record=lambda inn: {"inn": inn},
        build_report=lambda record: SimpleNamespace(inn=record["inn"]),
        get_tools=lambda record, inn: [],
        session_factory=lambda session_id: SimpleNamespace(session_id=session_id),
        run_agent=run_agent,
    )

    trace = asyncio.run(runner.run(case))

    assert attempts["count"] == 2
    assert trace.answers == ("ok",)
    assert not trace.infra_errors
    assert sleeps == [pytest.approx(0.51)]


def test_current_runner_gives_up_immediately_on_long_daily_quota_wait():
    async def run_agent(state, report, record, question, tools):
        raise _rate_limit_error("Please try again in 18m54.864s.")

    case = EvalCase.from_dict(
        {"id": "c", "suite": "golden", "inn": "1", "turns": [{"user": "вопрос"}]}
    )
    runner = CurrentAgentRunner(
        get_record=lambda inn: {"inn": inn},
        build_report=lambda record: SimpleNamespace(inn=record["inn"]),
        get_tools=lambda record, inn: [],
        session_factory=lambda session_id: SimpleNamespace(session_id=session_id),
        run_agent=run_agent,
    )

    trace = asyncio.run(runner.run(case))

    assert len(trace.infra_errors) == 1
    assert "RateLimitError" in trace.infra_errors[0]

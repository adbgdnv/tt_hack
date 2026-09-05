from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from typing import Any

import openai

from evals.schema import EvalCase, EvalTrace, ToolCall

_RETRY_AFTER = re.compile(r"try again in (?:(\d+)m)?([\d.]+)s", re.IGNORECASE)
_MAX_RATE_LIMIT_RETRIES = 4
_DEFAULT_RETRY_SECONDS = 10.0
_MAX_RETRY_WAIT_SECONDS = 60.0


def _retry_after_seconds(message: str) -> float | None:
    match = _RETRY_AFTER.search(message)
    if not match:
        return None
    minutes, seconds = match.groups()
    return (int(minutes) * 60 if minutes else 0) + float(seconds)


async def _call_with_rate_limit_retry(run_agent: Callable[..., Any], *args: Any) -> Any:
    """Повторяет вызов агента на 429 от провайдера, выждав названное им время.

    Groq (провайдер по умолчанию, см. `.env`/конституцию) режет по 8000 токенов в
    минуту (TPM). Тридцать live-кейсов подряд без паузы упираются в этот лимит почти
    сразу — без ретрая живой прогон превращается в один `infra_error` за другим
    вместо оценки качества (см. `evals/README.md`: инфра-ошибки и качество считаются
    раздельно). Провайдер сам называет точное время ожидания в теле ошибки — это
    надёжнее, чем гадать с фиксированной паузой; формат — либо просто секунды
    (`24.2s`), либо минуты и секунды (`18m54.864s`).

    Есть и второй, более редкий лимит — токены в сутки (TPD, 200 000/день):
    провайдер называет то же «try again in», но ждать приходится десятки минут.
    Внутри одного прогона это не лечится ретраем — прогон не должен зависать на
    четверть часа ради одного кейса, это явный `infra_error`, а не временная
    заминка (`_MAX_RETRY_WAIT_SECONDS` отделяет одно от другого).
    """
    attempt = 0
    while True:
        try:
            return await run_agent(*args)
        except openai.RateLimitError as exc:
            attempt += 1
            wait = _retry_after_seconds(str(exc))
            if wait is None:
                wait = _DEFAULT_RETRY_SECONDS
            if attempt > _MAX_RATE_LIMIT_RETRIES or wait > _MAX_RETRY_WAIT_SECONDS:
                raise
            await asyncio.sleep(wait + 0.5)


class CurrentAgentRunner:
    """Thin adapter that runs the same current agent path as the product."""

    def __init__(
        self,
        *,
        get_record: Callable[[str], dict | None] | None = None,
        build_report: Callable[[dict], Any] | None = None,
        get_tools: Callable[[dict, str], list] | None = None,
        session_factory: Callable[[str], Any] | None = None,
        run_agent: Callable[..., Any] | None = None,
    ) -> None:
        factories = (get_record, build_report, get_tools, session_factory, run_agent)
        if any(item is None for item in factories):
            from api.agent import loop, tools
            from core import repo
            from core.report import build

            get_record = get_record or repo.by_inn
            build_report = build_report or build
            get_tools = get_tools or tools.build
            session_factory = session_factory or loop.Session
            run_agent = run_agent or loop.run

        self.get_record = get_record
        self.build_report = build_report
        self.get_tools = get_tools
        self.session_factory = session_factory
        self.run_agent = run_agent

    async def run(self, case: EvalCase) -> EvalTrace:
        started = time.perf_counter()
        record = self.get_record(case.inn)
        if record is None:
            return EvalTrace(infra_errors=(f"dataset:missing_inn:{case.inn}",))

        report = self.build_report(record)
        state = self.session_factory(f"eval:{case.id}")
        answers: list[str] = []
        charts: list[str] = []
        sources: list[dict] = []
        tool_calls: list[ToolCall] = []

        try:
            for turn in case.turns:
                result = await _call_with_rate_limit_retry(
                    self.run_agent,
                    state,
                    report,
                    record,
                    turn.user,
                    self.get_tools(record, case.inn),
                )
                answers.append(result.text)
                for chart in result.charts:
                    if chart not in charts:
                        charts.append(chart)
                        tool_calls.append(ToolCall("show_chart", {"kind": chart}))
                for source in result.sources:
                    if source not in sources:
                        sources.append(source)
        except Exception as exc:  # live provider/tool failures belong to infra reporting
            elapsed = round((time.perf_counter() - started) * 1000)
            return EvalTrace(
                answers=tuple(answers),
                tool_calls=tuple(tool_calls),
                charts=tuple(charts),
                sources=tuple(sources),
                latency_ms=elapsed,
                infra_errors=(f"{type(exc).__name__}:{exc}",),
            )

        elapsed = round((time.perf_counter() - started) * 1000)
        return EvalTrace(
            answers=tuple(answers),
            tool_calls=tuple(tool_calls),
            charts=tuple(charts),
            sources=tuple(sources),
            latency_ms=elapsed,
        )

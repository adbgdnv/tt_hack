from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Turn:
    user: str


@dataclass(frozen=True)
class ToolExpectation:
    name: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Expectations:
    numbers: tuple[float, ...] = ()
    required_tools: tuple[ToolExpectation, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    required_patterns: tuple[str, ...] = ()
    forbidden_patterns: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvalCase:
    id: str
    suite: str
    inn: str
    turns: tuple[Turn, ...]
    expect: Expectations = Expectations()
    category: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> EvalCase:
        turns = tuple(Turn(user=str(item.get("user", "")).strip()) for item in raw.get("turns", ()))
        if not turns or any(not turn.user for turn in turns):
            raise ValueError("eval case must contain at least one non-empty turn")

        case_id = str(raw.get("id", "")).strip()
        suite = str(raw.get("suite", "")).strip()
        inn = str(raw.get("inn", "")).strip()
        if not case_id or not suite or not inn:
            raise ValueError("eval case requires id, suite and inn")

        expected = raw.get("expect") or {}
        required_tools = tuple(
            ToolExpectation(name=str(item["name"]), params=dict(item.get("params") or {}))
            for item in expected.get("required_tools", ())
        )
        expect = Expectations(
            numbers=tuple(float(value) for value in expected.get("numbers", ())),
            required_tools=required_tools,
            forbidden_tools=tuple(str(x) for x in expected.get("forbidden_tools", ())),
            required_patterns=tuple(str(x) for x in expected.get("required_patterns", ())),
            forbidden_patterns=tuple(str(x) for x in expected.get("forbidden_patterns", ())),
        )
        return cls(
            id=case_id,
            suite=suite,
            inn=inn,
            turns=turns,
            expect=expect,
            category=str(raw.get("category", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolCall:
    name: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvalTrace:
    answers: tuple[str, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()
    charts: tuple[str, ...] = ()
    sources: tuple[dict[str, Any], ...] = ()
    latency_ms: int = 0
    infra_errors: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "answers": list(self.answers),
            "tool_calls": [asdict(call) for call in self.tool_calls],
            "charts": list(self.charts),
            "sources": [dict(source) for source in self.sources],
            "latency_ms": self.latency_ms,
            "infra_errors": list(self.infra_errors),
        }


@dataclass(frozen=True)
class GradeResult:
    name: str
    passed: bool
    score: float
    critical: bool = False
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    status: str
    score: float | None
    grades: tuple[GradeResult, ...]
    infra_errors: tuple[str, ...] = ()
    # Ответы модели и показанные графики хранятся вместе с вердиктом: без них
    # видно только «сработал паттерн X», но не видно, что модель на самом деле
    # сказала, — а значит, настоящее падение неотличимо от промаха проверки.
    answers: tuple[str, ...] = ()
    charts: tuple[str, ...] = ()

"""Цикл агента: подумал → вызвал инструмент → посмотрел → повторил.

Живёт здесь, а не в MCP-сервере: MCP отдаёт возможности, а оркестрацию ведёт клиент.
В протоколе нет метода «запусти агента», и это не ограничение, а граница ответственности.

Память — в рамках одной сессии. Кейсодатель: «память нужна именно в рамках одной сессии»,
между сессиями оценка не переносится.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Session:
    """Состояние одного диалога. Живёт в памяти процесса, наружу не переживает."""

    session_id: str
    history: list[dict] = field(default_factory=list)
    focus_inn: str | None = None  # о каком контрагенте сейчас речь


def run(session: Session, question: str) -> str:
    """Прогоняет один шаг диалога и возвращает ответ пользователю."""
    raise NotImplementedError

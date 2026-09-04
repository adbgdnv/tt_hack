"""Цикл диалога: вопрос → ответ по отчёту.

Живёт здесь, а не в MCP-сервере: MCP отдаёт возможности, а оркестрацию ведёт клиент.
В протоколе нет метода «запусти агента», и это не ограничение, а граница ответственности.

Инструментов у модели нет намеренно. Отчёт помещается в контекст целиком — самая
тяжёлая компания даёт около 740 токенов, — поэтому дотягиваться не за чем.
А невызванный инструмент это прямой путь к выдумыванию, и «не выдумывает» стоит
первым в критериях приёмки кейса.

Память — в рамках одной сессии. Кейсодатель: «память нужна именно в рамках одной
сессии», между сессиями оценка не переносится.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from api.agent.prompt import build_messages
from core.llm import LLMClient
from core.report import Report

# Сколько пар «вопрос-ответ» держим. Ограничение не про память, а про токены:
# у провайдера лимит считает вход, и растущая история съела бы минутную квоту.
HISTORY_TURNS = 6


@dataclass
class Session:
    """Состояние одного диалога. Живёт в памяти процесса, наружу не переживает."""

    session_id: str
    history: list[dict] = field(default_factory=list)
    focus_inn: str | None = None  # о каком контрагенте сейчас речь

    def focus(self, inn: str) -> None:
        """Переключает контрагента, сбрасывая разговор.

        Ответы о предыдущей компании в новом контексте вводят в заблуждение:
        пользователь читает их как относящиеся к текущей.
        """
        if self.focus_inn != inn:
            self.history.clear()
            self.focus_inn = inn

    def remember(self, question: str, answer: str) -> None:
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": answer})
        del self.history[: max(0, len(self.history) - HISTORY_TURNS * 2)]


@dataclass(frozen=True)
class Answer:
    """Ответ диалога и разделы, на которые он опирается."""

    text: str
    sections: tuple[str, ...] = ()


_SESSIONS: dict[str, Session] = {}


def session(session_id: str) -> Session:
    """Сессия по идентификатору, создавая при первом обращении."""
    if session_id not in _SESSIONS:
        _SESSIONS[session_id] = Session(session_id=session_id)
    return _SESSIONS[session_id]


def _grounding(report: Report, text: str) -> tuple[str, ...]:
    """Разделы, названные в ответе — по имени раздела или по заголовку его фактора.

    Не угадываем «на что мог опираться»: отмечаем только то, что модель назвала сама.
    Придуманное обоснование хуже отсутствующего — оно выглядит как проверка,
    которой не было.

    Заголовки факторов учитываются потому, что модель говорит «Блокировки счетов
    налоговой», а не «раздел Реестры»: по одним названиям разделов обоснование
    оставалось пустым почти всегда.
    """
    lowered = text.lower()
    found = []
    for section in report.sections:
        named = section.title.lower() in lowered or any(
            f.heading.lower() in lowered for f in section.factors
        )
        if named:
            found.append(section.key)
    return tuple(found)


def run(state: Session, report: Report, question: str, client: LLMClient | None = None) -> Answer:
    """Прогоняет один шаг диалога и возвращает ответ пользователю."""
    state.focus(report.inn)
    messages = build_messages(report, question, state.history)
    answer = (client or LLMClient()).ask(messages, max_tokens=700, inn=report.inn)
    text = answer.content.strip()
    if not text:
        # У gpt-oss рассуждение приходит отдельным полем и способно съесть весь
        # бюджет, оставив content пустым. Пустой ответ выдавать за содержательный
        # нельзя — это неотличимо от «мне нечего сказать».
        raise RuntimeError("Модель вернула пустой ответ")
    state.remember(question, text)
    return Answer(text=text, sections=_grounding(report, text))

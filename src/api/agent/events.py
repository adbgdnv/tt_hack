"""Поток агента → события контракта.

Агент отдаёт куски двух типов: `AIMessageChunk` (текст ответа, а также вызовы
инструментов) и `ToolMessage` (итог вызова). Замерено на живом прогоне: 572 куска
текста и один итог инструмента на один ответ.

Имя инструмента приходит в первом куске вызова, аргументы дособираются
в следующих — поэтому вызов опознаётся по первому куску с непустым именем,
а последующие куски того же вызова игнорируются. Значит перевод обязан помнить,
что уже объявлено, — отсюда класс, а не функция.

Перевод синхронный, хотя поток асинхронный: разбор куска ничего не ждёт, а так
его можно проверить обычными тестами без цикла событий.

Контракт событий — `specs/006-chat-agent-tools/contracts/stream.md`. Здесь только
перевод одного в другое; ни один кусок не выдумывается.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from langchain_core.messages import ToolMessage

from core.charts import ChartSpec

# Что говорить пользователю про каждый инструмент. Имя функции с аргументами
# показывать нельзя: пользователь читает ленту, а не отладочный вывод.
TOOL_TITLES = {
    "show_chart": "Строю график",
    "web_search": "Ищу во внешних источниках",
}


@dataclass
class Event:
    """Событие потока. `name` — из контракта, `data` уходит как JSON."""

    name: str
    data: dict = field(default_factory=dict)

    def encode(self) -> str:
        """Одно событие в формате server-sent events."""
        return f"event: {self.name}\ndata: {json.dumps(self.data, ensure_ascii=False)}\n\n"


def tool_title(tool: str, arguments: str, charts: dict[str, ChartSpec]) -> str:
    """Фраза для человека о том, что сейчас делается.

    Название графика подставляем то же, что видно на дашборде: «Строю график
    „Суммы исков по годам"» читается, а `show_chart(kind=arbitration_years)` — нет.
    Аргументы приходят кусками и на момент начала вызова могут быть неполными,
    поэтому разбор необязателен: не разобрались — обходимся общей фразой.
    """
    base = TOOL_TITLES.get(tool, tool)
    try:
        parsed = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return base
    kind = parsed.get("kind")
    spec = charts.get(kind) if kind else None
    if spec is not None:
        return f"{base} «{spec.title}»"
    query = parsed.get("query")
    return f"{base}: {query}" if query else base


class Translator:
    """Переводит куски потока агента в события контракта.

    Помнит объявленные вызовы: последующие куски одного вызова несут только
    аргументы, и второе объявление выглядело бы в ленте как два вызова.

    Порядок гарантирован: `tool_start` → (`chart` | `sources`) → `tool_end`.
    События `chart` и `sources` рождает не инструмент, а этот перевод: инструмент
    возвращает модели текст, а интерфейсу нужен ключ.
    """

    def __init__(self, charts: dict[str, ChartSpec]) -> None:
        self._charts = charts
        self._started: set[str] = set()

    def feed(self, chunk) -> list[Event]:
        """События по одному куску потока. Ничего не ждёт."""
        if isinstance(chunk, ToolMessage):
            return self._finish(chunk)
        out: list[Event] = []
        for call in getattr(chunk, "tool_call_chunks", None) or []:
            name = call.get("name")
            if not name or call.get("id") in self._started:
                continue
            self._started.add(call.get("id"))
            title = tool_title(name, call.get("args"), self._charts)
            out.append(Event("tool_start", {"tool": name, "title": title}))
        if chunk.content:
            out.append(Event("token", {"text": chunk.content}))
        return out

    def _finish(self, message: ToolMessage) -> list[Event]:
        """События по итогу вызова инструмента.

        Ошибка инструмента не проглатывается: она видна пользователю. Инструмент,
        который тихо ничего не сделал, неотличим от сработавшего, и следующий
        за ним текст модели читается как подтверждённый.
        """
        failed = getattr(message, "status", "success") == "error"
        payload = getattr(message, "artifact", None)
        out: list[Event] = []
        if not failed and isinstance(payload, dict):
            if "chart" in payload:
                out.append(Event("chart", payload["chart"]))
            if "sources" in payload:
                out.append(Event("sources", {"items": payload["sources"]}))
        name = getattr(message, "name", "") or ""
        out.append(Event("tool_end", {"tool": name, "ok": not failed}))
        return out

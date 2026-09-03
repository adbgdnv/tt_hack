"""Графики. Спека для интерфейса + PNG для клиентов, которые рисовать не умеют.

Кейсодатель упомянул графики трижды и назвал их отсутствие болью текущего продукта:
«там, по сути, нет графиков», а за основу главного сценария взял «ChatGPT с графичками».

Отдаём оба представления сразу. У MCP поле `content` — массив, поэтому один вызов
возвращает и картинку, и структуру: наш веб рисует интерактивно из спеки, сторонний
клиент (Claude Desktop) показывает PNG. Помечаем `annotations.audience`, чтобы модель
не тратила контекст на разглядывание base64.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ChartKind = Literal["line", "bar", "stacked_bar"]


@dataclass
class ChartSpec:
    """Описание графика, независимое от библиотеки отрисовки."""

    kind: ChartKind
    title: str
    x_label: str
    y_label: str
    series: list[dict[str, Any]]
    source_note: str  # из каких полей отчёта построено


def revenue_dynamics(report: dict) -> ChartSpec | None:
    """Выручка и прибыль по годам. None, если отчётности нет — а её нет у 36%."""
    raise NotImplementedError


def arbitration_split(report: dict) -> ChartSpec | None:
    """Суммы исков в роли истца и ответчика."""
    raise NotImplementedError


def group_comparison(reports: list[dict]) -> ChartSpec:
    """Сопоставление группы контрагентов по числу сработавших факторов."""
    raise NotImplementedError


def render_png(spec: ChartSpec) -> bytes:
    """Рендер спеки в PNG для клиентов без своей отрисовки."""
    raise NotImplementedError

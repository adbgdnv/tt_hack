"""MCP-сервер поверх ядра.

Кейсодатель: MCP «требуется со звёздочкой» — приветствуется, но не обязателен. Их
настоящее API это одна ручка (контрагент по ИНН); они планируют сконвертировать её
в MCP и разместить у себя, чтобы агент ходил туда, а не в сервис напрямую.

Здесь только объявления: имена, схемы, описания. Вся логика — в `core`.
Описания тулов пишем подробно: они доходят до модели в любом клиенте, поэтому
дисциплина «не выдумывай» должна ехать вместе с ними, а не только в нашем промпте.

Проверка границы: удалить src/api — этот сервер продолжит работать в Claude Desktop.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from core import mocks, repo, slim

mcp = FastMCP("counterparty-checker")


@mcp.tool()
def search_counterparty(query: str, limit: int = 10) -> list[dict]:
    """Найти контрагента по ИНН или части названия.

    Возвращает краткие карточки. Если ничего не найдено — пустой список,
    это значит «в базе нет», а не «ошибка».
    """
    return [slim.slim(r) for r in mocks.search(query, limit)]


@mcp.tool()
def get_counterparty_report(inn: str) -> dict:
    """Отчёт о контрагенте по ИНН.

    Только поля из выгрузки. Пустое поле означает, что данных нет —
    не интерпретируй пустоту как отсутствие проблемы.
    """
    report = repo.by_inn(inn)
    if report is None:
        return {"error": "not_found", "detail": "Компания не найдена"}
    return slim.slim(report)


@mcp.tool()
def assess_risk(inn: str) -> dict:
    """Разобрать риски контрагента.

    Возвращает сработавшие факторы, каждый с полем-источником, и отдельно список
    того, что оценить невозможно из-за отсутствия данных. Светофор банка не
    пересчитывает — он источник истины, его нужно объяснять, а не оспаривать.
    """
    raise NotImplementedError


@mcp.tool()
def compare_counterparties(inns: list[str]) -> dict:
    """Сравнить нескольких контрагентов и показать, с кем стоит быть осторожнее.

    Числового рейтинга не возвращает — только вывод с обоснованием по каждому.
    """
    raise NotImplementedError


@mcp.tool()
def get_financials(inn: str) -> dict:
    """Финансовые показатели и коэффициенты.

    Отчётность есть у 64% контрагентов, готовые коэффициенты у 24%, у ИП её не бывает
    вовсе. Когда цифр нет — так и сообщает, а не возвращает нули.
    """
    raise NotImplementedError


@mcp.resource("counterparty://{inn}")
def counterparty_resource(inn: str) -> str:
    """Отчёт как адресуемые данные — клиент может подложить их в контекст сам."""
    raise NotImplementedError


if __name__ == "__main__":
    mcp.run()

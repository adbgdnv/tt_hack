"""MCP-сервер поверх ядра.

Кейс называется «Создание агента **и MCP-сервера** для проверки контрагента
в бизнесе». Сам сервер кейсодатель назвал «со звёздочкой» — приветствуется,
но не обязателен. Их настоящее API это одна ручка (контрагент по ИНН); они
планируют сконвертировать её в MCP и разместить у себя, чтобы агент ходил туда,
а не в сервис напрямую. Наш сервер показывает, какой формы этот MCP должен
быть, чтобы агенту было чем работать.

Здесь только объявления: имена, схемы, описания. Вся логика — в `core`.
Описания тулов пишем подробно: они доходят до модели в любом клиенте, поэтому
дисциплина «не выдумывай» должна ехать вместе с ними, а не только в нашем
промпте — свой промпт в чужой клиент не едет.

Ненайденное возвращается словарём с `error`, а не исключением: исключение
доходит до клиента как поломка сервера и обрывает разговор, хотя «в базе нет» —
это ответ.

Проверка границы: удалить src/api — этот сервер продолжит работать.
"""

from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

from core import compare as compare_core
from core import repo, slim, topics, verify
from core.report import build as build_report

mcp = FastMCP("counterparty-checker")

НЕ_НАЙДЕН = {"error": "not_found", "detail": "Компания не найдена"}


def _записи(inns: list[str]) -> tuple[list[dict], list[str]]:
    """Записи по ИНН и отдельно — ненайденные.

    Ненайденные не выбрасываются молча: пул из двух вместо трёх — это ответ
    на другой вопрос, чем задал пользователь.
    """
    найденные, пропущенные = [], []
    for инн in dict.fromkeys(inns):
        запись = repo.by_inn(инн)
        (найденные if запись is not None else пропущенные).append(запись or инн)
    return найденные, пропущенные


def _противоречия(report) -> list[dict]:
    """Противоречия между разделами в виде, пригодном для чужой модели."""
    return [
        {
            "title": т.title,
            "detail": т.explanation,
            "section": т.section,
            "evidence": list(т.evidence),
        }
        for т in report.triggers
    ]


@mcp.tool()
def search_counterparty(query: str, limit: int = 10) -> list[dict]:
    """Найти контрагента по ИНН, части названия или ФИО руководителя.

    Возвращает краткие карточки. Если ничего не найдено — пустой список,
    это значит «в базе нет», а не «ошибка».
    """
    return [slim.slim(r) for r in repo.search(query, limit)]


@mcp.tool()
def get_counterparty_report(inn: str) -> dict:
    """Отчёт о контрагенте по ИНН.

    Только поля из выгрузки. Пустое поле означает, что данных нет —
    не интерпретируй пустоту как отсутствие проблемы.
    """
    запись = repo.by_inn(inn)
    return slim.slim(запись) if запись is not None else НЕ_НАЙДЕН


@mcp.tool()
def assess_risk(inn: str) -> dict:
    """Разобрать риски контрагента: что сработало и чего оценить нельзя.

    Возвращает противоречия между разделами (каждое со значениями, на которых
    оно построено), состояние каждого раздела и отдельно список того, что
    оценить невозможно из-за отсутствия данных.

    Оценки риска не пересчитываются: скоринг банка и уровень платформы ЗСК
    Банка России — источник истины, их нужно объяснять, а не оспаривать.
    Обе считаются по банковским операциям и судов не учитывают — поэтому
    зелёная оценка при тяжёлых открытых данных это не ошибка, а разные
    предметы измерения.

    Числового балла компании здесь нет и не будет: выводы даются словами.
    Отсутствие данных — это ответ. Раздел в состоянии `empty` означает
    «оценить по этому критерию невозможно», а не «рисков нет».
    """
    запись = repo.by_inn(inn)
    if запись is None:
        return НЕ_НАЙДЕН
    отчёт = build_report(запись)
    return {
        "inn": отчёт.inn,
        "name": отчёт.name,
        "status": отчёт.status,
        "is_entrepreneur": отчёт.is_entrepreneur,
        "bank_risk": {
            "source": отчёт.bank_risk.source,
            "value": отчёт.bank_risk.value,
            "known": отчёт.bank_risk.known,
        },
        "zsk_risk": {
            "source": отчёт.zsk_risk.source,
            "value": отчёт.zsk_risk.value,
            "known": отчёт.zsk_risk.known,
        },
        "contradictions": _противоречия(отчёт),
        "sections": [
            {
                "key": р.key,
                "title": р.title,
                "state": р.state.value,
                "note": р.note,
                "checks_passed": р.checks_passed,
                "checks_total": р.checks_total,
            }
            for р in отчёт.sections
        ],
        # То же, что показывает вывод сравнения: раздел без данных — это
        # «проверять было нечем», и без него 14 пройденных проверок из 14
        # при двух пустых разделах читаются как безупречность.
        "gaps": [р.title for р in отчёт.sections if р.state.value == "empty"],
        "signals": отчёт.signals,
        "unknowns": отчёт.unknowns,
    }


@mcp.tool()
def find_contradictions(inn: str) -> dict:
    """Найти, что у контрагента не сходится между разделами отчёта.

    Отвечает на вопрос, которого не задать ни одному разделу по отдельности:
    зелёные оценки при тяжёлых открытых данных, управляющий вместо директора,
    долги покупателей больше годовой выручки, отчётность многолетней давности.

    Пустой список означает «противоречий не нашлось» — это тоже ответ,
    а не отсутствие результата.
    """
    запись = repo.by_inn(inn)
    if запись is None:
        return НЕ_НАЙДЕН
    отчёт = build_report(запись)
    return {
        "inn": отчёт.inn,
        "name": отчёт.name,
        "contradictions": _противоречия(отчёт),
    }


@mcp.tool()
def compare_counterparties(inns: list[str]) -> dict:
    """Сравнить нескольких контрагентов и показать, с кем стоит быть осторожнее.

    Порядок — от того, к кому меньше вопросов, к тому, у кого их больше.
    Числового рейтинга не возвращает: только вывод с обоснованием по каждому.
    Ранжирование баллом кейсодатель прямо не просил и просил обратного —
    нужен вывод, с кем лучше не работать.

    Ненайденные ИНН перечисляются отдельно, а не выбрасываются молча.
    """
    if len(dict.fromkeys(inns)) > compare_core.ПРЕДЕЛ_ПУЛА:
        return {
            "error": "too_many",
            "detail": f"Сравнивать можно не больше {compare_core.ПРЕДЕЛ_ПУЛА} контрагентов сразу",
        }
    записи, ненайденные = _записи(inns)
    if not записи:
        return НЕ_НАЙДЕН
    вердикты = compare_core.compare(записи)
    вывод = compare_core.summary(вердикты)
    return {
        "summary": {"headline": вывод.headline, "detail": вывод.detail},
        "verdicts": [
            {
                "inn": в.inn,
                "name": в.name,
                "level": в.level,
                "recommendation": в.recommendation,
                "reasons": list(в.reasons),
                "gaps": list(в.gaps),
                "checks_passed": в.checks_passed,
                "checks_total": в.checks_total,
            }
            for в in вердикты
        ],
        "not_found": ненайденные,
    }


@mcp.tool()
def get_financials(inn: str) -> dict:
    """Финансовые показатели и коэффициенты контрагента.

    Отчётность есть у 64% контрагентов, готовые коэффициенты у 24%. У ИП
    бухотчётности не бывает по закону — про такого отвечай «у ИП такого
    не бывает», а не «данных нет».

    Когда цифр нет, `reports_filed` равно false. Не подставляй нули: ноль
    в отчётности и отсутствие отчётности — разные вещи.
    """
    запись = repo.by_inn(inn)
    if запись is None:
        return НЕ_НАЙДЕН
    отчёт = build_report(запись)
    текст = topics.look_up(запись, "финансы")
    return {
        "inn": отчёт.inn,
        "name": отчёт.name,
        "is_entrepreneur": отчёт.is_entrepreneur,
        "reports_filed": bool(запись.get("finReports")),
        "text": текст,
    }


# Перечень тем подставляется в описание при объявлении: `mcp.tool()` снимает
# описание с docstring один раз, и подменить его потом нечем — декоратор
# возвращает саму функцию, а не объект инструмента.
ОПИСАНИЕ_ТЕМ = f"""Посмотреть данные о контрагенте по теме, которой нет в кратком отчёте.

Темы:
{topics.catalogue()}
Других тем нет. Если тема не опознана, инструмент вернёт перечень
доступных — выбирай из него, а не придумывай своё название."""


@mcp.tool(description=ОПИСАНИЕ_ТЕМ)
def look_up(inn: str, topic: str) -> dict:
    """Данные по теме. Описание для модели — в `ОПИСАНИЕ_ТЕМ`."""
    запись = repo.by_inn(inn)
    if запись is None:
        return НЕ_НАЙДЕН
    if topics.topic(topic) is None:
        return {"inn": inn, "topic": topic, "topics": topics.catalogue()}
    return {"inn": inn, "topic": topic, "text": topics.look_up(запись, topic)}



@mcp.tool()
def verify_claims(text: str, inns: list[str]) -> dict:
    """Проверить, какие числа текста есть в отчётах названных контрагентов.

    Зови на своём готовом ответе перед тем, как показать его человеку.
    `unverified` — числа, которых в отчётах нет: либо они посчитаны тобой,
    либо выдуманы, и в обоих случаях об этом нужно сказать прямо.

    `total: 0` означает «чисел в тексте не было», а не «всё подтверждено».
    """
    записи, ненайденные = _записи(inns)
    if not записи:
        return НЕ_НАЙДЕН
    итог = verify.check(text, [build_report(з) for з in записи])
    return {
        "total": len(итог.claims),
        "confirmed": len(итог.claims) - итог.unverified,
        "unverified": [
            {"number": c.number, "context": c.context} for c in итог.claims if not c.found
        ],
        "not_found": ненайденные,
    }


@mcp.resource("counterparty://{inn}", mime_type="application/json")
def counterparty_resource(inn: str) -> str:
    """Отчёт как адресуемые данные — клиент может подложить их в контекст сам."""
    запись = repo.by_inn(inn)
    данные = slim.slim(запись) if запись is not None else НЕ_НАЙДЕН
    return json.dumps(данные, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # Транспорт по умолчанию у FastMCP — stdio, и с ним контейнер, объявляющий
    # порт 8001, не слушает ничего. Отсюда и «сервер не поднят»: подниматься
    # было нечему. Клиент на своей машине по-прежнему может запустить нас
    # через stdio — тогда MCP_TRANSPORT=stdio, см. `docs/MCP.md`.
    транспорт = os.environ.get("MCP_TRANSPORT", "streamable-http")
    if транспорт != "stdio":
        # Внутри контейнера 127.0.0.1 — его собственная петля, снаружи
        # недостижимая. Наружу машины порт закрывает привязка в compose,
        # ровно как у сервиса api.
        mcp.settings.host = os.environ.get("MCP_HOST", "0.0.0.0")  # noqa: S104
        mcp.settings.port = int(os.environ.get("MCP_PORT", "8001"))
    mcp.run(transport=транспорт)

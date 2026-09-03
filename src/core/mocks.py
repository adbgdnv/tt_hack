"""Фейковая база контрагентов поверх выгрузки кейсодателя.

Кейсодатель на Q&A: «входные данные — по сути их нет, у вас под капотом своя фейковая
база данных из всех csv-шек, которые мы дали». Это и есть тот слой.

Важно: JSON и CSV — **разные** компании, пересечение по ОГРН нулевое. Итого 200, не 100.
"""

from __future__ import annotations

import csv
import json
import sys
from functools import lru_cache
from pathlib import Path

from core.config import find_up

_JSON = "docs_alpha/contractors_audit.snapshot.json"
_CSV = "docs_alpha/contractors_audit.snapshot_C12613591.csv"


def _csv_row_to_report(row: dict) -> dict:
    """Собирает вложенный отчёт из плоской строки CSV (2654 колонки)."""
    report: dict = {}
    for flat_key, value in row.items():
        if not flat_key.startswith("report.") or value in ("", None):
            continue
        node = report
        parts = flat_key[len("report.") :].split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return report


@lru_cache(maxsize=1)
def load_all() -> list[dict]:
    """Все доступные отчёты: 100 из JSON + 100 других из CSV."""
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))
    reports: list[dict] = []

    json_path = find_up(_JSON)
    if json_path:
        reports += [r["report"] for r in json.loads(json_path.read_text(encoding="utf-8"))]

    csv_path = find_up(_CSV)
    if csv_path:
        with csv_path.open(encoding="utf-8") as f:
            reports += [_csv_row_to_report(row) for row in csv.DictReader(f)]

    if not reports:
        raise FileNotFoundError(
            "Не найдена выгрузка контрагентов — ожидается docs_alpha/ выше по дереву"
        )
    return reports


def by_inn(inn: str) -> dict | None:
    """Отчёт по ИНН или None."""
    return next((r for r in load_all() if (r.get("baseInfo") or {}).get("inn") == inn), None)


def search(query: str, limit: int = 10) -> list[dict]:
    """Поиск по названию или ИНН. Вход продукта — «ИНН или поисковый запрос»."""
    needle = query.strip().lower()
    hits = [
        r
        for r in load_all()
        if needle in ((r.get("baseInfo") or {}).get("shortName") or "").lower()
        or needle in ((r.get("baseInfo") or {}).get("inn") or "")
    ]
    return hits[:limit]


def data_root() -> Path | None:
    """Каталог с выгрузкой — для диагностики и монтирования в контейнер."""
    path = find_up(_JSON)
    return path.parent if path else None

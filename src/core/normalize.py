"""Приведение обеих выгрузок кейсодателя к одной форме.

Выгрузки описывают одни и те же поля, но записаны по-разному. Вложенная хранит
числа числами, а самые крупные суммы и все даты заворачивает в служебные обёртки —
следы выгрузки из MongoDB. Плоская расплющена нотацией `путь[индекс].подпуть`
и хранит всё текстом, включая признаки «да/нет».

Ключевое решение: **типы для плоской выгрузки берутся из вложенной, а не угадываются.**
Схема у выгрузок общая, поэтому карта «путь → тип», снятая с первой, применяется
ко второй и покрывает её полностью. Угадывание по значению здесь недопустимо: текст
`false` непуст, а значит истинен, и все исполнительные производства компании стали бы
активными. Таких значений в выгрузке 3873.

Только чистые функции: ни путей, ни чтения файлов. Ввод-вывод — забота скрипта сборки.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

# `report.finReports[0].common.year` → [("finReports", "0"), ("common", None), ("year", None)]
_TOKEN = re.compile(r"([^.\[\]]+)(?:\[(\d+)\])?")

_FLAT_PREFIX = "report."

_TRUE = {"true", "1", "yes", "да"}
_FALSE = {"false", "0", "no", "нет", ""}


def unwrap(value: Any) -> Any:
    """Разворачивает служебные обёртки выгрузки, рекурсивно.

    `{"$numberLong": "279815832000"}` → `279815832000`,
    `{"$date": "2024-11-10T21:00:00.000Z"}` → та же строка.

    Обёртки встречаются только во вложенной выгрузке — 67 значений по 16 путям —
    и затрагивают ровно самые крупные суммы. Без разворачивания на их месте
    оказывается словарь, а попытка привести его к числу роняет обработку.
    """
    if isinstance(value, dict):
        if "$numberLong" in value:
            return int(value["$numberLong"])
        if "$date" in value:
            return value["$date"]
        return {k: unwrap(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unwrap(v) for v in value]
    return value


def unflatten(row: dict) -> dict:
    """Собирает вложенную запись из плоской строки выгрузки.

    Колонки вне отчёта пропускаются, пустые ячейки не попадают в результат —
    отсутствующее поле должно отсутствовать, а не превращаться в пустую строку.

    Без этой развёртки ключ `finReports[0].common.year` остаётся именем поля целиком,
    списочные разделы не собираются, и запись сохраняет только те поля, у которых
    в пути не было индексов, — наименование и ИНН.
    """
    out: dict = {}
    for flat, value in row.items():
        if not flat.startswith(_FLAT_PREFIX) or value in ("", None):
            continue
        tail = flat[len(_FLAT_PREFIX) :]
        steps = [(m.group(1), m.group(2)) for m in _TOKEN.finditer(tail) if m.group(1)]
        node: Any = out
        for i, (name, index) in enumerate(steps):
            last = i == len(steps) - 1
            if index is None:
                if last:
                    node[name] = value
                else:
                    node = node.setdefault(name, {})
            else:
                items = node.setdefault(name, [])
                position = int(index)
                while len(items) <= position:
                    items.append({})
                if last:
                    items[position] = value
                else:
                    node = items[position]
    return out


def _walk(value: Any, path: str = ""):
    """Пары «путь без индексов → значение» для всех листьев записи."""
    if isinstance(value, dict):
        if "$numberLong" in value:
            yield path, "int"
            return
        if "$date" in value:
            yield path, "str"
            return
        for key, item in value.items():
            yield from _walk(item, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item, f"{path}[]")
    else:
        yield path, type(value).__name__


def type_map(records: list[dict]) -> dict[str, str]:
    """Карта «путь → тип», снятая с вложенной выгрузки.

    Индексы списков из пути убираются: тип у всех элементов списка один.
    Большие числа сводятся к обычным, даты — к строкам, иначе один и тот же путь
    выглядел бы неоднозначным там, где разницы по существу нет.

    Проверено на выгрузке: 118 путей, покрытие плоской выгрузки полное,
    неоднозначных путей после сведения не остаётся.
    """
    seen: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        for path, kind in _walk(record):
            if path:
                seen[path][kind] += 1
    return {path: kinds.most_common(1)[0][0] for path, kinds in seen.items()}


def _to_bool(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUE:
            return True
        if lowered in _FALSE:
            return False
    return value


def _to_int(value: Any) -> Any:
    if isinstance(value, bool) or isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return value


def _to_float(value: Any) -> Any:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return value


_CONVERTERS = {"bool": _to_bool, "int": _to_int, "float": _to_float}


def coerce(record: Any, types: dict[str, str], path: str = "") -> Any:
    """Приводит значения записи к типам из карты.

    Путь, которого в карте нет, остаётся как есть — молчаливое приведение к строке
    скрыло бы расхождение схемы. Значение, не поддающееся объявленному типу, тоже
    остаётся как есть: подставить ноль значило бы выдать «мы не смогли прочитать»
    за «здесь ноль», а это разные утверждения.
    """
    if isinstance(record, dict):
        return {k: coerce(v, types, f"{path}.{k}" if path else k) for k, v in record.items()}
    if isinstance(record, list):
        return [coerce(v, types, f"{path}[]") for v in record]
    converter = _CONVERTERS.get(types.get(path, ""))
    return converter(record) if converter else record


def normalize_nested(record: dict) -> dict:
    """Запись вложенной выгрузки: снять обёртки, типы уже верны."""
    return unwrap(record)


def normalize_flat(row: dict, types: dict[str, str]) -> dict:
    """Строка плоской выгрузки: собрать вложенность и привести типы по карте."""
    return coerce(unflatten(row), types)

#!/usr/bin/env python3
"""Проверка DBG-записей против schemas/vibe-debug-comment.schema.json.

Подмножество JSON Schema без внешних зависимостей: сервер, аудит и тесты
читают одну и ту же схему, поэтому разойтись им негде.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMENT_SCHEMA_PATH = REPO_ROOT / "schemas" / "vibe-debug-comment.schema.json"

LEGACY_OPTIONAL = frozenset(
    {"mode", "displayAuthor", "anchor", "attachments", "updatedAt"}
)

_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
}


def load_schema(path: Path = COMMENT_SCHEMA_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(node: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    ref = node.get("$ref")
    if not ref:
        return node
    if not ref.startswith("#/"):
        raise ValueError(f"поддерживаются только локальные $ref, получено {ref!r}")
    target: Any = root
    for part in ref[2:].split("/"):
        target = target[part]
    return target


def _check_type(value: Any, expected: str, path: str, errors: list[str]) -> bool:
    allowed = _TYPES[expected]
    if isinstance(value, bool) and expected != "boolean":
        errors.append(f"{path}: ожидался {expected}, получен boolean")
        return False
    if not isinstance(value, allowed):
        errors.append(f"{path}: ожидался {expected}, получен {type(value).__name__}")
        return False
    return True


def validate(
    value: Any,
    schema: dict[str, Any] | None = None,
    *,
    root: dict[str, Any] | None = None,
    path: str = "$",
) -> list[str]:
    """Вернуть список нарушений. Пустой список — запись соответствует схеме."""
    if schema is None:
        schema = load_schema()
    if root is None:
        root = schema
    schema = _resolve(schema, root)
    errors: list[str] = []

    if "enum" in schema:
        if value not in schema["enum"]:
            errors.append(f"{path}: {value!r} не входит в {schema['enum']}")
            return errors

    expected = schema.get("type")
    if expected and not _check_type(value, expected, path, errors):
        return errors

    if isinstance(value, str):
        pattern = schema.get("pattern")
        if pattern and not re.search(pattern, value):
            errors.append(f"{path}: {value!r} не соответствует {pattern}")
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: короче {schema['minLength']} символов")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: длиннее {schema['maxLength']} символов")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: меньше {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: больше {schema['maximum']}")

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}: нет обязательного поля {name!r}")
        if schema.get("additionalProperties") is False:
            for name in value:
                if name not in properties:
                    errors.append(f"{path}: постороннее поле {name!r}")
        for name, subschema in properties.items():
            if name in value:
                errors.extend(
                    validate(value[name], subschema, root=root, path=f"{path}.{name}")
                )

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: меньше {schema['minItems']} элементов")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: больше {schema['maxItems']} элементов")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                errors.extend(
                    validate(item, item_schema, root=root, path=f"{path}[{index}]")
                )

    return errors


def split_legacy(errors: list[str]) -> tuple[list[str], list[str]]:
    """Развести нарушения на ошибки и предупреждения о legacy-записях.

    Записи, созданные до текущей схемы, не имеют `mode`, `displayAuthor`,
    `anchor`, `attachments` и `updatedAt`. Переписывать их задним числом нельзя:
    это чужие комментарии. Поэтому такие пропуски — предупреждение.
    """
    hard: list[str] = []
    soft: list[str] = []
    for error in errors:
        if any(f"нет обязательного поля {name!r}" in error for name in LEGACY_OPTIONAL):
            soft.append(error)
        else:
            hard.append(error)
    return hard, soft

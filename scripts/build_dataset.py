#!/usr/bin/env python3
"""Собирает подготовленный набор контрагентов из выгрузок кейсодателя.

Запускается вручную перед деплоем, в рантайме не участвует. Все несоответствия
выгрузок разрешаются здесь, чтобы сервер получал данные, пригодные к использованию
как есть, а ошибки приведения обнаруживались на сборке, а не на живом сервере.

    python3 scripts/build_dataset.py            # собрать набор
    python3 scripts/build_dataset.py --check    # только проверить, ничего не писать

Результат не коммитится: репозиторий публичный, а в данных сведения об учредителях,
включая имена и личные идентификаторы. На сервер набор переносится копированием.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.config import dataset_path, find_up  # noqa: E402
from core.normalize import normalize_flat, normalize_nested, type_map  # noqa: E402

csv.field_size_limit(2**31 - 1)

NESTED_DUMP = "docs_alpha/contractors_audit.snapshot.json"
FLAT_DUMP = "docs_alpha/contractors_audit.snapshot_C12613591.csv"

RULES_VERSION = 1


def read_nested(path: Path) -> list[dict]:
    """Записи вложенной выгрузки со снятыми обёртками."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [normalize_nested(item["report"]) for item in raw]


def read_flat(path: Path, types: dict[str, str]) -> list[dict]:
    """Записи плоской выгрузки, развёрнутые и приведённые по карте типов.

    Карта снимается с вложенной выгрузки: схема у выгрузок общая, а типы угадывать
    нельзя — текст `false` непуст и потому истинен, и все исполнительные производства
    компании оказались бы активными.
    """
    with path.open(encoding="utf-8", newline="") as handle:
        return [normalize_flat(row, types) for row in csv.DictReader(handle)]


def build() -> dict:
    """Собирает набор. Возвращает готовую полезную нагрузку."""
    nested_path = find_up(NESTED_DUMP)
    if not nested_path:
        raise SystemExit(
            f"Не найдена выгрузка {NESTED_DUMP}. Она лежит вне репозитория — "
            "подключить симлинком: make data"
        )

    counterparties = read_nested(nested_path)
    sources = [{"file": nested_path.name, "records": len(counterparties)}]

    # Карта типов снимается с вложенной выгрузки и применяется к плоской.
    types = type_map(counterparties)

    flat_path = find_up(FLAT_DUMP)
    if flat_path:
        flat = read_flat(flat_path, types)
        counterparties += flat
        sources.append({"file": flat_path.name, "records": len(flat)})
    else:
        print(f"ВНИМАНИЕ: не найдена плоская выгрузка {FLAT_DUMP} — половина данных пропущена")

    return {
        "meta": {
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "rules_version": RULES_VERSION,
            "sources": sources,
            "type_paths": len(types),
            "count": len(counterparties),
        },
        "counterparties": counterparties,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Сборка набора контрагентов")
    parser.add_argument("--check", action="store_true", help="собрать в памяти и не писать файл")
    parser.add_argument(
        "--out", type=Path, default=None, help="куда писать (по умолчанию DATASET_PATH)"
    )
    args = parser.parse_args()

    payload = build()
    meta = payload["meta"]

    print(f"Записей: {meta['count']}")
    for source in meta["sources"]:
        print(f"  {source['file']}: {source['records']}")
    print(f"Путей в карте типов: {meta['type_paths']}")

    inns = [(r.get("baseInfo") or {}).get("inn") for r in payload["counterparties"]]
    if len(set(inns)) != len(inns):
        raise SystemExit("ИНН неуникальны — набор не собран")

    if args.check:
        print("Проверка пройдена, файл не записан")
        return 0

    out = args.out or dataset_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    size = out.stat().st_size / 1024 / 1024
    print(f"Записано: {out} ({size:.1f} МБ)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

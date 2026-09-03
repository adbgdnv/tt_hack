#!/usr/bin/env python3
"""Сверка спецификации кейсодателя с реальной выгрузкой.

Обходит все пути из `data/GetFullReportResponse.md` по обеим выгрузкам (JSON + CSV)
и печатает покрытие каждого поля, расхождения и ловушки. Цифры из
`docs/data_reference.md` получены этим скриптом — если выгрузка обновится,
перепроверять надо им, а не глазами.

    python3 scripts/audit_data.py            # покрытие полей
    python3 scripts/audit_data.py --traps    # только ловушки и распределения

Развёртка плоских ключей берётся из `core.normalize` — одна реализация на проект,
чтобы сверка и сборка набора не разъезжались.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.normalize import unflatten  # noqa: E402

csv.field_size_limit(2**31 - 1)

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "GetFullReportResponse.md"
JSON_DUMP = ROOT / "data" / "contractors_audit.snapshot.json"
CSV_DUMP = ROOT / "data" / "contractors_audit.snapshot_C12613591.csv"

def load() -> tuple[list[dict], list[dict]]:
    js = [r["report"] for r in json.loads(JSON_DUMP.read_text(encoding="utf-8"))]
    with CSV_DUMP.open(encoding="utf-8", newline="") as f:
        cs = [unflatten(row) for row in csv.DictReader(f)]
    return js, cs


def walk(obj, parts: list[str]) -> list:
    """Все непустые значения по пути вида `a.b[].c`."""
    if not parts:
        return [obj] if obj not in (None, "", [], {}) else []
    head, rest = parts[0], parts[1:]
    is_arr = head.endswith("[]")
    key = head[:-2] if is_arr else head
    if not isinstance(obj, dict):
        return []
    val = obj.get(key)
    if val in (None, "", [], {}):
        return []
    if is_arr:
        if not isinstance(val, list):
            return []
        return [x for item in val for x in walk(item, rest)]
    return walk(val, rest)


def parse_spec() -> list[tuple[str, str, str]]:
    """Пути полей из таблиц спецификации. Сокращения через `...` пропускаем —
    они неоднозначны, вложенный арбитраж проверяется отдельным списком ниже."""
    fields, section = [], "—"
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        sec = re.match(r"^#+\s*\*\*(.+?)\*\*", line)
        if sec:
            section = sec.group(1)
            continue
        m = re.match(r"^\|\s*`([^`]+)`\s*\|\s*(.+?)\s*\|$", line)
        if m and not m.group(1).startswith("..."):
            fields.append((m.group(1), m.group(2), section))
    return fields


ARBITRATION_BLOCKS = [
    f"arbitrationByStatus.{group}.{group[:-11]}Arbitration{state}.{p}{s}"
    for group, p in (("plaintiffArbitration", "p"), ("defandantArbitration", "d"))
    for state, s in (("Finished", "f"), ("Appealed", "a"), ("Pending", "p"))
    for s in (f"{s}Count", f"{s}Amount")
]


def report_coverage(js, cs):
    allr = js + cs
    print(f"Записей: JSON {len(js)} + CSV {len(cs)} = {len(allr)}\n")
    section = None
    missing = []
    for path, desc, sec in parse_spec():
        if sec != section:
            section = sec
            print(f"\n--- {sec} ---")
        parts = path.split(".")
        n = sum(1 for r in allr if walk(r, parts))
        flag = "  ← НЕТ В ВЫГРУЗКЕ" if n == 0 else ("  ← редкое" if n < 40 else "")
        if n == 0:
            missing.append((path, desc))
        print(f"{path:<64} {n:>3}/200{flag}")

    print("\n--- Арбитраж по статусам (в спеке записан сокращённо) ---")
    for path in ARBITRATION_BLOCKS:
        n = sum(1 for r in allr if walk(r, path.split(".")))
        short = path[len("arbitrationByStatus.") :]
        print(f"  {short:<62} {n:>3}/200")

    print(f"\n=== Полей из спеки, которых нет ни у кого: {len(missing)} ===")
    for p, d in missing:
        print(f"  {p:<52} {d[:50]}")


def report_traps(js, cs):
    allr = js + cs
    print("=== Светофоры ===")
    risk = Counter((r.get("baseInfo") or {}).get("riskLevel") for r in allr)
    zsk = Counter(r.get("zskRiskLevel") for r in allr)
    state = Counter((r.get("status") or {}).get("status") for r in allr)
    print("  baseInfo.riskLevel:", dict(risk))
    print("  zskRiskLevel:      ", dict(zsk))
    print("  status.status:     ", dict(state))

    ip = [r for r in allr if ((r.get("baseInfo") or {}).get("shortName") or "").startswith("ИП")]
    print(f"\n=== ИП: {len(ip)} из {len(allr)} ===")
    print("  с finReports:  ", sum(1 for r in ip if r.get("finReports")))
    print("  с foundersInfo:", sum(1 for r in ip if r.get("foundersInfo")))

    neg, pos = Counter(), 0
    for r in allr:
        rr = r.get("reputationalRisks") or {}
        for f in rr.get("negative") or []:
            neg[f.get("code")] += 1
        pos += len(rr.get("positive") or [])
    print(f"\n=== Факторы: {sum(neg.values())} негативных / {pos} позитивных "
          f"= 1 : {pos / max(sum(neg.values()), 1):.1f} ===")
    for c, n in neg.most_common():
        print(f"  {c:<28} {n:>3}")

    print("\n=== Не-ASCII в кодах факторов ===")
    seen = set()
    for r in allr:
        rr = r.get("reputationalRisks") or {}
        for kind in ("negative", "positive"):
            for f in rr.get(kind) or []:
                code = f.get("code") or ""
                if any(ord(ch) > 127 for ch in code) and (kind, code) not in seen:
                    seen.add((kind, code))
                    print(f"  [{kind}] {code!r}  первый символ: {hex(ord(code[0]))}")
    if not seen:
        print("  не найдено")

    def longs(o, path=""):
        if isinstance(o, dict):
            if "$numberLong" in o:
                yield path, int(o["$numberLong"])
                return
            for k, v in o.items():
                yield from longs(v, f"{path}.{k}" if path else k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                yield from longs(v, f"{path}[{i}]")

    paths, biggest = Counter(), []
    for r in allr:
        for p, v in longs(r):
            paths[re.sub(r"\[\d+\]", "[]", p)] += 1
            biggest.append((v, (r.get("baseInfo") or {}).get("shortName"), p))
    print(f"\n=== $numberLong: {sum(paths.values())} значений по {len(paths)} путям ===")
    for p, n in paths.most_common(8):
        print(f"  {p:<58} {n}")
    print("  крупнейшие:")
    for v, name, p in sorted(biggest, reverse=True)[:3]:
        amount = f"{v:,}".replace(",", " ")
        print(f"    {amount:>18} ₽  {name:<26} {p}")

    counts = [len(r.get("executionProceedings") or []) for r in allr]
    print(f"\n=== Исполнительные производства: всего {sum(counts)}, "
          f"максимум у одной компании {max(counts)} ===")

    print("\n=== Типы: JSON против CSV ===")
    fj = next((r["finReports"][0] for r in js if r.get("finReports")), {})
    fc = next((r["finReports"][0] for r in cs if r.get("finReports")), {})
    tj = type((fj.get("common") or {}).get("year")).__name__
    tc = type((fc.get("common") or {}).get("year")).__name__
    print(f"  finReports[0].common.year: JSON={tj} CSV={tc}")


if __name__ == "__main__":
    if not JSON_DUMP.exists():
        sys.exit(f"Нет выгрузки: {JSON_DUMP} — сделать `make data`")
    j, c = load()
    if "--traps" in sys.argv:
        report_traps(j, c)
    else:
        report_coverage(j, c)
        print()
        report_traps(j, c)

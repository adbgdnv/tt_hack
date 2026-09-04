#!/usr/bin/env python3
"""Частота негативных факторов по набору — и сверка со словарём `FREQUENCY`.

Числа в `core.factors.FREQUENCY` получены этим скриптом. Пересобрали набор —
пересчитывать надо им, а не глазами: словарь, разошедшийся с данными, тише
и вреднее отсутствующего, потому что сортировка продолжает работать и выглядит
осмысленной.

    python3 scripts/audit_factors.py           # частоты и расхождения
    python3 scripts/audit_factors.py --order   # что встаёт первым в отчёте

Считаем компании, а не срабатывания: фактор либо сообщает об этой компании,
либо нет, а два упоминания одного кода в одной карточке — свойство выгрузки.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from core.factors import FREQUENCY, HEADINGS, frequency, heading, weight  # noqa: E402
from core.repo import load  # noqa: E402


def _codes(record: dict) -> set[str]:
    negative = (record.get("reputationalRisks") or {}).get("negative") or []
    return {str(f.get("code") or "") for f in negative if f.get("code")}


def measure(records) -> Counter:
    counts: Counter = Counter()
    for record in records:
        counts.update(_codes(record))
    return counts


def report_frequency(records) -> int:
    """Печатает замер и расхождения со словарём. Возвращает код выхода."""
    counts = measure(records)
    print(f"компаний в наборе: {len(records)}\n")
    print(f"{'код':28} {'заголовок':42} {'вес':>3} {'встр':>5} {'в словаре':>10}")
    for code, n in counts.most_common():
        в_словаре = FREQUENCY.get(code, "—")
        пометка = "" if в_словаре == n else "  ← РАСХОЖДЕНИЕ"
        print(f"{code:28} {heading(code):42} {weight(code):>3} {n:>5} {в_словаре:>10}{пометка}")

    расхождения = [c for c, n in counts.items() if FREQUENCY.get(c) != n]
    лишние = sorted(set(FREQUENCY) - set(counts))
    if лишние:
        print(f"\nв словаре есть, в наборе не встречаются: {', '.join(лишние)}")
    if расхождения:
        print(f"\nСловарь разошёлся с набором по кодам: {', '.join(sorted(расхождения))}")
        print("Обновить core.factors.FREQUENCY этими числами.")
        return 1
    print("\nСловарь совпадает с набором.")
    return 0


def report_order(records) -> None:
    """Что встаёт первой строкой отчёта. Ради этого частота и заводилась:
    пока ключ был один, почти половина отчётов открывалась одним и тем же."""
    первые: Counter = Counter()
    без_факторов = 0
    for record in records:
        коды = _codes(record)
        if not коды:
            без_факторов += 1
            continue
        первый = min(коды, key=lambda c: (-weight(c), frequency(c), heading(c)))
        первые[первый] += 1
    с_факторами = len(records) - без_факторов
    print(f"без негативных факторов: {без_факторов} из {len(records)}")
    print(f"открывают отчёт (всего {с_факторами} компаний):\n")
    for code, n in первые.most_common():
        доля = n / с_факторами
        print(f"  {heading(code):42} {n:>3}  {доля:>5.0%}  вес {weight(code)}")


def main() -> int:
    try:
        records = load().counterparties
    except RuntimeError as error:
        print(f"Набор не собран: {error}")
        print("Сначала — python3 scripts/build_dataset.py")
        return 2
    if not HEADINGS:
        return 2
    if "--order" in sys.argv:
        report_order(records)
        return 0
    return report_frequency(records)


if __name__ == "__main__":
    raise SystemExit(main())

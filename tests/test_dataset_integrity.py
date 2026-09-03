"""Свойства собранного набора, которые нельзя проверить глазами.

Тест работает на настоящем наборе, а не на придуманном: смысл именно в том, чтобы
поймать расхождение между исходной выгрузкой и результатом сборки. Выгрузка лежит
вне репозитория, поэтому в CI, где набор не собран, тесты пропускаются.

Собрать набор: `python3 scripts/build_dataset.py`
"""

import csv
import json

import pytest

from core.config import dataset_path, find_up

DATASET = dataset_path()

pytestmark = pytest.mark.skipif(
    not DATASET.exists(),
    reason=f"набор не собран ({DATASET}) — запустить scripts/build_dataset.py",
)


@pytest.fixture(scope="module")
def payload() -> dict:
    return json.loads(DATASET.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def records(payload) -> list[dict]:
    return payload["counterparties"]


def test_набор_несёт_сведения_о_сборке(payload):
    meta = payload["meta"]
    assert meta["count"] == len(payload["counterparties"])
    assert meta["built_at"]
    assert meta["sources"]


def test_инн_уникальны(records):
    inns = [(r.get("baseInfo") or {}).get("inn") for r in records]
    assert all(inns), "у каждой записи должен быть ИНН"
    assert len(set(inns)) == len(inns)


def test_ни_одна_запись_не_состоит_только_из_названия_и_инн(records):
    """Ровно этим отличался результат до починки развёртки: сто компаний
    отдавали два поля из сорока, и ничего при этом не падало."""
    скудные = [
        (r.get("baseInfo") or {}).get("inn")
        for r in records
        if len(r) <= 2 and set(r) <= {"baseInfo", "reportDate"}
    ]
    assert скудные == [], f"записи без содержания: {скудные[:5]}"


def test_обёртки_развёрнуты_в_числа(records):
    """`$numberLong` и `$date` — следы выгрузки из MongoDB. Оставшаяся обёртка
    означает словарь на месте суммы, а это самые крупные значения набора."""

    def найти_обёртки(value, path=""):
        if isinstance(value, dict):
            if "$numberLong" in value or "$date" in value:
                yield path
                return
            for k, v in value.items():
                yield from найти_обёртки(v, f"{path}.{k}" if path else k)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                yield from найти_обёртки(v, f"{path}[{i}]")

    остатки = [p for r in records for p in найти_обёртки(r)]
    assert остатки == [], f"необёрнутых значений: {len(остатки)}, например {остатки[:3]}"


def test_крупные_суммы_на_месте(records):
    """Самые тяжёлые значения приходили обёрнутыми — проверяем, что они не потерялись
    и не обнулились. В выгрузке есть активы в сотни миллиардов рублей."""
    максимум = 0
    for r in records:
        for отчёт in r.get("finReports") or []:
            активы = (отчёт.get("assets") or {}).get("totalAssets")
            if isinstance(активы, (int, float)):
                максимум = max(максимум, активы)
    assert максимум > 10_000_000_000, f"крупнейшие активы всего {максимум} — похоже, суммы потеряны"


def test_признаки_остались_признаками(records):
    """Признак активности производства должен быть логическим, а не строкой:
    непустая строка `false` истинна, и все производства стали бы активными."""
    строковые = [
        p.get("active")
        for r in records
        for p in (r.get("executionProceedings") or [])
        if not isinstance(p.get("active"), bool) and p.get("active") is not None
    ]
    assert строковые == [], f"нелогических признаков: {len(строковые)}, например {строковые[:3]}"


# ─────────────── инварианты, появляющиеся со второй выгрузкой ───────────────

NESTED = find_up("docs_alpha/contractors_audit.snapshot.json")
FLAT = find_up("docs_alpha/contractors_audit.snapshot_C12613591.csv")

нужны_выгрузки = pytest.mark.skipif(
    not (NESTED and FLAT), reason="исходные выгрузки недоступны — нечего сверять"
)


@pytest.fixture(scope="module")
def инн_первой_выгрузки() -> set[str]:
    raw = json.loads(NESTED.read_text(encoding="utf-8"))
    return {str(item["report"]["baseInfo"]["inn"]) for item in raw}


@нужны_выгрузки
def test_обе_выгрузки_попали_в_набор(records, инн_первой_выгрузки):
    inns = {str((r.get("baseInfo") or {}).get("inn")) for r in records}
    из_первой = inns & инн_первой_выгрузки
    из_второй = inns - инн_первой_выгрузки
    assert len(из_первой) == 100
    assert len(из_второй) == 100


@нужны_выгрузки
def test_доля_активных_производств_совпадает_с_исходником(records):
    """Считаем исходник независимым способом — сравнением строк, без нашего
    приведения типов. Иначе проверка была бы круговой: тот же код подтверждал бы
    сам себя, а перевёрнутый признак выглядит как обычные данные."""
    csv.field_size_limit(2**31 - 1)

    ожидалось = 0
    raw = json.loads(NESTED.read_text(encoding="utf-8"))
    for item in raw:
        for p in item["report"].get("executionProceedings") or []:
            ожидалось += p.get("active") is True
    with FLAT.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            for key, value in row.items():
                if key.endswith(".active") and "executionProceedings" in key:
                    ожидалось += str(value).strip().lower() == "true"

    получилось = sum(
        1
        for r in records
        for p in (r.get("executionProceedings") or [])
        if p.get("active") is True
    )
    assert получилось == ожидалось, (
        f"активных производств в наборе {получилось}, в исходных выгрузках {ожидалось} — "
        "признак «да/нет» перевернулся при приведении типов"
    )


@нужны_выгрузки
def test_заполненность_разделов_сопоставима_между_выгрузками(records, инн_первой_выгрузки):
    """Контрагент не должен выдавать источник содержанием отчёта."""

    def средняя_заполненность(набор):
        return sum(len(r) for r in набор) / max(len(набор), 1)

    def инн(r):
        return str((r.get("baseInfo") or {}).get("inn"))

    первая = [r for r in records if инн(r) in инн_первой_выгрузки]
    вторая = [r for r in records if инн(r) not in инн_первой_выгрузки]
    a, b = средняя_заполненность(первая), средняя_заполненность(вторая)
    assert 0.75 < a / b < 1.35, f"разделов в среднем: первая {a:.1f}, вторая {b:.1f}"

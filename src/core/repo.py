"""Витрина контрагентов: единственная точка, через которую продукт получает данные.

Читает подготовленный набор — один файл, собранный заранее скриптом сборки, — и держит
его в памяти. Двести записей, около четырёх мегабайт, только чтение: базе данных здесь
нечего ускорять, а точечный доступ по ИНН закрывается словарём.

Ни один потребитель не знает, из какой выгрузки пришёл контрагент, — это свойство
обеспечивает шаг сборки, а не эта витрина.

Границу ядра держим: ни HTTP-фреймворка, ни MCP здесь нет и быть не должно.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from core.config import dataset_path


@dataclass(frozen=True)
class Dataset:
    """Подготовленный набор: записи плюс сведения о сборке."""

    counterparties: tuple[dict, ...]
    meta: dict = field(default_factory=dict)
    by_inn_index: dict = field(default_factory=dict)


@lru_cache(maxsize=4)
def load(path: Path | None = None) -> Dataset:
    """Читает набор с диска. Результат кэшируется — файл в рантайме не меняется.

    Отсутствие файла — явная ошибка с указанием пути, а не пустой набор. Пустой
    набор выглядит как «у всех компаний ничего нет» и неотличим от честного результата,
    поэтому запрещён контрактом.
    """
    path = Path(path) if path else dataset_path()
    if not path.exists():
        raise RuntimeError(
            f"Не найден подготовленный набор контрагентов: {path}\n"
            "Собрать: python3 scripts/build_dataset.py\n"
            "Путь переопределяется переменной DATASET_PATH."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = tuple(payload.get("counterparties") or ())
    index = {}
    for record in records:
        inn = (record.get("baseInfo") or {}).get("inn")
        if inn:
            index[str(inn)] = record
    return Dataset(counterparties=records, meta=payload.get("meta") or {}, by_inn_index=index)


def by_inn(inn: str, path: Path | None = None) -> dict | None:
    """Контрагент целиком или None, если такого ИНН в наборе нет.

    Промежуточных состояний между «есть целиком» и «нет» не существует: контрагент
    отдаётся со всеми разделами за одно обращение.
    """
    return load(path).by_inn_index.get(str(inn).strip())


def _fold(value: str) -> str:
    """Приводит строку к виду, в котором её сравнивают.

    Регистр — потому что ФИО в наборе записаны прописными, а вводят их строчными.
    Ё — потому что «Силин Артем» и «СИЛИН АРТЁМ» это один человек: в наборе два
    таких имени и два названия, и без замены поиск по ним молча ничего не находит.
    """
    return value.lower().replace("ё", "е")


def search(query: str, limit: int = 10, path: Path | None = None) -> list[dict]:
    """Поиск по наименованию, ИНН и ФИО руководителя, без учёта регистра.

    ФИО ищется потому, что его обещает поле ввода — «ИНН, название или ФИО
    руководителя». Раньше не искалось: поиск смотрел только на название и ИНН,
    и обещание не выполнялось для 150 компаний из 200, у которых руководитель
    известен. У остальных пятидесяти это ИП, и руководителя у них не бывает —
    но фамилия стоит в самом названии («ИП АБРАМОВ И.А.»), поэтому по фамилии
    находятся и они.

    Пустой результат — не ошибка: он означает «в наборе таких нет».
    """
    needle = _fold((query or "").strip())
    if not needle:
        return []
    hits = []
    for record in load(path).counterparties:
        base = record.get("baseInfo") or {}
        person = (record.get("foundersInfo") or {}).get("authPerson") or {}
        haystack = (
            _fold(str(base.get("shortName") or "")),
            str(base.get("inn") or ""),
            _fold(str(person.get("name") or "")),
        )
        if any(needle in field for field in haystack):
            hits.append(record)
            if len(hits) >= limit:
                break
    return hits


def all(path: Path | None = None) -> list[dict]:  # noqa: A001 — «все контрагенты», доменное слово
    """Все контрагенты набора."""
    return list(load(path).counterparties)


def stats(path: Path | None = None) -> dict:
    """Сведения о наборе для проверки живости.

    Без них «сервис поднят» и «сервис отдаёт настоящие данные» неразличимы — а это
    ровно то состояние, в котором продукт находился до появления витрины.
    """
    dataset = load(path)
    meta = dict(dataset.meta)
    meta["count"] = len(dataset.counterparties)
    return meta

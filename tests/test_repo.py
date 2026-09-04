"""Тесты доступа к подготовленному набору.

Набор для тестов собирается прямо здесь: настоящая выгрузка лежит вне репозитория
и в CI недоступна, а проверять надо поведение витрины, а не содержимое данных.
"""

import json

import pytest

from core import repo


@pytest.fixture
def dataset(tmp_path):
    """Маленький набор из трёх контрагентов, покрывающий нужные случаи."""
    payload = {
        "meta": {
            "built_at": "2026-09-03T18:00:00Z",
            "count": 3,
            "sources": ["contractors_audit.snapshot.json"],
        },
        "counterparties": [
            {
                "baseInfo": {
                    "inn": "5032257375",
                    "shortName": 'ООО "МАКСМАРКЕТ"',
                    "riskLevel": "LOW",
                },
                "zskRiskLevel": "GREEN",
                "arbitrationByStatus": {"commonCount": 12},
                # Ё намеренно: в настоящем наборе такие имена есть, и без
                # приведения буквы поиск по ним ничего не находит.
                "foundersInfo": {
                    "authPerson": {
                        "name": "СИЛИН АРТЁМ АЛЕКСЕЕВИЧ",
                        "positionName": "ГЕНЕРАЛЬНЫЙ ДИРЕКТОР",
                    }
                },
            },
            {
                "baseInfo": {
                    "inn": "2466177504",
                    "shortName": 'ООО "АВТОАТЛАНТ"',
                    "riskLevel": "HIGH",
                },
                "zskRiskLevel": "YELLOW",
            },
            {
                "baseInfo": {
                    "inn": "343703064945",
                    "shortName": "ИП Качурин М.О.",
                    "riskLevel": "UNKNOWN",
                },
                "zskRiskLevel": "GREEN",
                "arbitrationByStatus": {"commonCount": 0},
            },
        ],
    }
    path = tmp_path / "counterparties.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    repo.load.cache_clear()
    yield path
    repo.load.cache_clear()


def test_выдаёт_контрагента_по_инн(dataset):
    found = repo.by_inn("5032257375", dataset)
    assert found is not None
    assert found["baseInfo"]["shortName"] == 'ООО "МАКСМАРКЕТ"'


def test_отсутствующий_инн_даёт_none(dataset):
    """Не пустая запись и не исключение: «не найдено» — это ответ."""
    assert repo.by_inn("0000000000", dataset) is None


def test_поиск_по_части_названия(dataset):
    hits = repo.search("максмаркет", path=dataset)
    assert [h["baseInfo"]["inn"] for h in hits] == ["5032257375"]


def test_поиск_по_инн(dataset):
    hits = repo.search("2466177504", path=dataset)
    assert [h["baseInfo"]["shortName"] for h in hits] == ['ООО "АВТОАТЛАНТ"']


def test_поиск_не_зависит_от_регистра(dataset):
    assert repo.search("АВТОАТЛАНТ", path=dataset) == repo.search("автоатлант", path=dataset)


def test_пустой_результат_поиска_не_ошибка(dataset):
    assert repo.search("такой компании нет", path=dataset) == []


def test_поиск_соблюдает_ограничение_выдачи(dataset):
    assert len(repo.search("о", limit=2, path=dataset)) <= 2


def test_отсутствие_файла_набора_называет_путь(tmp_path):
    """Работа с пустым набором запрещена контрактом: она выглядит как
    «у всех компаний ничего нет» и неотличима от честного результата."""
    repo.load.cache_clear()
    missing = tmp_path / "нет-такого" / "counterparties.json"
    with pytest.raises(RuntimeError) as err:
        repo.load(missing)
    assert str(missing) in str(err.value)
    repo.load.cache_clear()


def test_сведения_о_наборе_доступны(dataset):
    """Иначе «сервис жив» и «сервис отдаёт данные» неразличимы."""
    stats = repo.stats(dataset)
    assert stats["count"] == 3
    assert stats["built_at"] == "2026-09-03T18:00:00Z"


def test_все_контрагенты_доступны_списком(dataset):
    assert len(repo.all(dataset)) == 3


def test_нет_данных_отличается_от_нуля(dataset):
    """У «АВТОАТЛАНТА» раздела судов нет вовсе, у ИП он есть и равен нулю.
    Первое значит «оценить невозможно», второе — «дел нет». Разные утверждения."""
    без_раздела = repo.by_inn("2466177504", dataset)
    с_нулём = repo.by_inn("343703064945", dataset)
    assert "arbitrationByStatus" not in без_раздела
    assert с_нулём["arbitrationByStatus"]["commonCount"] == 0


# ─────────────────────────── поиск по руководителю ───────────────────────────


def test_поиск_находит_по_фамилии_руководителя(dataset):
    """Поле ввода обещает «ИНН, название или ФИО руководителя». Обещание не
    выполнялось: поиск смотрел только на название и ИНН."""
    found = repo.search("силин", path=dataset)

    assert [r["baseInfo"]["inn"] for r in found] == ["5032257375"]


def test_поиск_по_фио_не_зависит_от_регистра_и_буквы_ё(dataset):
    """В наборе ФИО записаны прописными и с Ё, вводят их строчными и через Е."""
    assert repo.search("артем", path=dataset)
    assert repo.search("СИЛИН Артём", path=dataset)


def test_предприниматель_находится_по_фамилии_через_название(dataset):
    """У ИП руководителя не бывает, но фамилия стоит в самом названии —
    отдельной ветки для них не нужно."""
    found = repo.search("качурин", path=dataset)

    assert [r["baseInfo"]["inn"] for r in found] == ["343703064945"]


def test_совпадение_по_фио_не_дублирует_компанию(dataset):
    """Запрос, попадающий и в название, и в ФИО, обязан вернуть одну запись."""
    assert len(repo.search("силин артём алексеевич", path=dataset)) == 1

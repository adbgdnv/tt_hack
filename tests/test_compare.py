"""Сравнение контрагентов.

Кейсодатель назвал сценарий целевым и одновременно запретил рейтинг:
«Скорее не ранжирование. Нужно вывод — с кем лучше не общаться. Ранжирование
в виде какого-то скора не требуется». Отсюда две вещи, которые здесь сторожатся:
порядок есть, балла нет.
"""

from __future__ import annotations

from dataclasses import asdict

import pytest

from core import compare
from core.repo import load

try:
    НАБОР = load().counterparties
except RuntimeError:
    НАБОР = []

нужен_набор = pytest.mark.skipif(not НАБОР, reason="набор не собран")


def запись(inn="7704310756", name='ООО "ТЕСТ"', **overrides) -> dict:
    """Чистая запись без единого триггера. Правки накладываются сверху.

    Отчётность обязательна и свежая: у юрлица её отсутствие само по себе
    триггер, а позапрошлогодняя — второй. Первая версия этой заготовки была
    «чистой» только на вид и роняла три теста.
    """
    record = {
        "baseInfo": {
            "inn": inn,
            "shortName": name,
            "riskLevel": "LOW",
            "registrationInfo": {"yearsFromRegistration": 9},
        },
        "status": {"status": "CURRENT"},
        "zskRiskLevel": "GREEN",
        "reputationalRisks": {"negative": [], "positive": []},
        "foundersInfo": {"shareCapital": 5_000_000},
        "finReports": [
            {
                "common": {"year": 2025, "proceeds": 400_000_000, "profit": 30_000_000},
                "assets": {
                    "totalAssets": 250_000_000,
                    "currentAssets": {"receivables": 60_000_000},
                },
                "liabilities": {"capitals": 120_000_000, "totalLiabilities": 250_000_000},
            }
        ],
    }
    record.update(overrides)
    return record


def банкрот() -> dict:
    """Компания с тяжёлым триггером: молчащие светофоры при негативных кодах."""
    return запись(
        inn="5032257375",
        name='ООО "БАНКРОТ"',
        status={
            "status": "CURRENT",
            "reasonName": "Юридическое лицо признано несостоятельным (банкротом)",
        },
        reputationalRisks={
            "negative": [
                {"code": "liquidationStatus", "name": "Процедура банкротства",
                 "chapter": "reestrs"},
            ],
            "positive": [],
        },
    )


def test_чистая_компания_выше_спорной():
    """Выбирают лучшего, и ответ на «кто лучше» должен стоять первым."""
    итог = compare.compare([банкрот(), запись()])

    assert [в.name for в in итог] == ['ООО "ТЕСТ"', 'ООО "БАНКРОТ"']
    assert итог[0].level == compare.ЧИСТО
    assert итог[-1].level == compare.ВНИМАНИЕ


def test_балла_в_вердикте_нет():
    """Сторож ограничения кейсодателя. Значимость триггеров считается внутри,
    но наружу не отдаётся: чего нет в контракте, того нельзя случайно нарисовать.
    """
    (один,) = compare.compare([банкрот()])
    поля = asdict(один)

    assert "weight" not in поля
    assert "score" not in поля
    assert not any(isinstance(v, (int, float)) and k not in
                   {"checks_passed", "checks_total"} for k, v in поля.items())


def test_при_равной_значимости_выше_проверенная():
    """Между двумя одинаково чистыми честнее поставить выше проверенную,
    а не ту, которую было нечем проверить."""
    мало = запись(inn="1", name="НЕПРОВЕРЕННАЯ")
    много = запись(
        inn="2",
        name="ПРОВЕРЕННАЯ",
        reputationalRisks={
            "negative": [],
            "positive": [
                {"code": "massAddress", "name": "Не в реестре массовых адресов",
                 "chapter": "reestrs"},
                {"code": "taxArrears", "name": "Не в реестре должников ФНС",
                 "chapter": "reestrs"},
            ],
        },
    )

    итог = compare.compare([мало, много])

    assert итог[0].name == "ПРОВЕРЕННАЯ"
    assert итог[0].checks_passed > итог[1].checks_passed


def test_вывод_называет_и_лучшего_и_худшего():
    """Кейсодатель просил обе половины: «находить оптимального» и «вывод —
    с кем лучше не общаться». Это один список с двух концов."""
    вывод = compare.summary(compare.compare([банкрот(), запись()]))
    текст = f"{вывод.headline} {вывод.detail}"

    assert 'ООО "ТЕСТ"' in вывод.headline
    assert 'ООО "БАНКРОТ"' in текст
    assert "чище других" in вывод.headline


def test_причина_не_приписывается_чужой_компании():
    """Назвать двоих и привести одну причину значит приписать её обоим.
    Ловилось на живых данных: «Осторожнее с A и B — <причина B>»."""
    второй = банкрот()
    второй["baseInfo"]["inn"] = "2"
    второй["baseInfo"]["shortName"] = 'ООО "ВТОРОЙ"'
    итог = compare.compare([банкрот(), второй, запись()])

    текст = compare.summary(итог).detail

    # Худший назван со своей причиной, остальные — отдельной фразой без причины
    assert "Осторожнее всего с" in текст
    assert текст.count("Осторожнее всего") == 1


def test_пул_из_одного_не_выдаёт_вывод_о_группе():
    вывод = compare.summary(compare.compare([запись()]))

    assert "только" in вывод.headline
    assert "Сравнивать не с чем" in вывод.detail


def test_пустой_пул_объясняется_словами():
    assert compare.summary([]).headline == "Пул пуст"


def test_нехватка_данных_названа_у_верхнего():
    """Наверху списка это единственное, что отличает «проверили и чисто»
    от «проверять было нечем»."""
    (один,) = compare.compare([запись()])

    assert isinstance(один.gaps, list)
    if один.gaps:
        assert all(isinstance(g, str) and g for g in один.gaps)


def test_короткий_список_идёт_от_худшего():
    """Смотрят первыми тех, к кому больше вопросов; чистые в список не попадают."""
    итог = compare.shortlist([банкрот(), запись()])

    assert [в.name for в in итог] == ['ООО "БАНКРОТ"']


@нужен_набор
def test_на_настоящем_наборе_порядок_не_ломается():
    """Прогон по всему набору: вердикт строится у каждой компании, порядок
    не убывает по значимости, балла нигде нет."""
    итог = compare.compare(НАБОР[:40])

    уровни = [в.level for в in итог]
    порядок = {compare.ЧИСТО: 0, compare.УТОЧНИТЬ: 1, compare.ВНИМАНИЕ: 2}
    assert уровни == sorted(уровни, key=порядок.get)
    assert all(в.name and в.inn for в in итог)


@нужен_набор
def test_вывод_строится_для_любой_тройки():
    """Замерено: у 74% компаний нет ни одного триггера, и случайная тройка
    даёт полную ничью в 40% случаев. Вывод обязан быть непустым и там."""
    for начало in range(0, 30, 3):
        вывод = compare.summary(compare.compare(НАБОР[начало : начало + 3]))
        assert вывод.headline and вывод.detail
        assert len(вывод.headline) > 15


@нужен_набор
def test_ручка_отдаёт_вердикты_вывод_и_ненайденные():
    """Неизвестный ИНН называется, а не выбрасывается молча: тихо убрать
    компанию из пула значит соврать о составе сравнения."""
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as client:
        ответ = client.post(
            "/compare",
            json={"inns": ["5032257375", "9714079997", "0000000000", "5032257375"]},
        )

    assert ответ.status_code == 200
    тело = ответ.json()
    assert тело["not_found"] == ["0000000000"]
    assert тело["summary"]["headline"] and тело["summary"]["detail"]
    # Дубль убран, порядок от чистого к спорному
    assert len(тело["verdicts"]) == 2
    assert тело["verdicts"][0]["level"] == compare.ЧИСТО


@нужен_набор
def test_в_ответе_ручки_нет_балла():
    """Сторож на границе: чего нет в контракте, то нельзя случайно нарисовать."""
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as client:
        тело = client.post(
            "/compare", json={"inns": ["5032257375", "9714079997"]}
        ).json()

    for вердикт in тело["verdicts"]:
        assert "weight" not in вердикт
        assert "score" not in вердикт
        assert "rank" not in вердикт

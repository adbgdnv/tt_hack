"""Сборка представления отчёта.

Часть проверок идёт на выдуманных записях — так видно поведение в чистом виде.
Инварианты проверяются на настоящем наборе: смысл именно в том, чтобы ни одна
из двухсот компаний не выпала из правил.
"""

import pytest

from core.repo import load
from core.report import SECTION_TITLES, State, build


def запись(**overrides) -> dict:
    """Минимальная запись, которую точечно ломаем под конкретный тест."""
    record = {
        "baseInfo": {
            "inn": "7704310756",
            "shortName": 'ООО "ТЕСТ"',
            "riskLevel": "LOW",
            "registrationInfo": {"registrationDate": "2015-01-01", "yearsFromRegistration": 11},
        },
        "status": {"status": "CURRENT"},
        "zskRiskLevel": "GREEN",
        "reputationalRisks": {"negative": [], "positive": []},
    }
    record.update(overrides)
    return record


def фактор(code="arbitrationDefendant", chapter="arbitr", name="Есть арбитражные дела"):
    return {"code": code, "chapter": chapter, "name": name}


# ─────────────────────────── состав и состояния ───────────────────────────


def test_разделов_всегда_восемь():
    """Интерфейсу не нужна ветка «а если раздела нет»."""
    assert len(build(запись()).sections) == len(SECTION_TITLES) == 8


def test_раздел_с_негативным_фактором_получает_сигнал():
    r = build(запись(reputationalRisks={"negative": [фактор()], "positive": []}))
    courts = next(s for s in r.sections if s.key == "courts")
    assert courts.state is State.SIGNAL
    assert courts.factors[0].heading == "Ответчик в арбитраже"


def test_раздел_без_данных_пуст_а_не_равен_нулю():
    """«По судам данных нет» и «судов нет» — разные утверждения."""
    courts = next(s for s in build(запись()).sections if s.key == "courts")
    assert courts.state is State.EMPTY
    assert "нет" in courts.note.lower()


def test_у_предпринимателя_финансы_неприменимы():
    """Это устройство формы, а не пробел в данных."""
    r = build(запись(baseInfo={**запись()["baseInfo"], "shortName": "ИП Иванов И.И."}))
    fin = next(s for s in r.sections if s.key == "finances")
    assert fin.state is State.NOT_APPLICABLE
    assert "ИП" in fin.note


def test_у_юрлица_финансы_с_данными_заполнены():
    r = build(запись(finReports=[{"common": {"year": 2025, "proceeds": 1000}}]))
    fin = next(s for s in r.sections if s.key == "finances")
    assert fin.state is State.FILLED


# ─────────────────────────── порядок ───────────────────────────


def test_разделы_с_сигналом_идут_выше_пустых():
    r = build(запись(reputationalRisks={"negative": [фактор()], "positive": []}))
    states = [s.state for s in r.sections]
    assert states.index(State.SIGNAL) < states.index(State.EMPTY)


def test_тяжёлый_фактор_поднимает_раздел_выше_лёгкого():
    """Банкротство весит больше, чем «много кодов ОКВЭД», хотя встречается реже."""
    r = build(
        запись(
            reputationalRisks={
                "negative": [
                    фактор("massOkved", "okved", "Много кодов"),
                    фактор("liquidationStatus", "reestrs", "Банкротство"),
                ],
                "positive": [],
            }
        )
    )
    ключи = [s.key for s in r.sections]
    assert ключи.index("registries") < ключи.index("activity")


def test_при_равной_тяжести_первым_идёт_более_редкий_фактор():
    """Раньше ничью решала буква заголовка — у 29 компаний из 117.

    «Массовый адрес» (вес 2, у 24 компаний) обгонял «Убыток по отчётности»
    (вес 2, у 10) только потому, что «М» раньше «У». Оба в разделе «Финансы»
    и «Реестры» не пересекаются, поэтому берём пару внутри одного раздела:
    ответчик в арбитраже против исполнительных производств — обоим вес 2,
    но первый встречается вдвое чаще и потому сообщает о компании меньше.
    """
    r = build(
        запись(
            reputationalRisks={
                "negative": [
                    фактор("arbitrationDefendant", "arbitr", "Ответчик"),
                    фактор("executionProceedings", "arbitr", "Производства"),
                ],
                "positive": [],
            }
        )
    )
    суды = next(s for s in r.sections if s.key == "courts")
    коды = [f.code for f in суды.factors]
    assert коды == ["executionProceedings", "arbitrationDefendant"], коды


# ─────────────────────────── разбор источника ───────────────────────────


def test_объяснение_берётся_из_данных_как_есть():
    текст = "Есть арбитражные дела, в которых выступает в качестве ответчика."
    r = build(запись(reputationalRisks={"negative": [фактор(name=текст)], "positive": []}))
    courts = next(s for s in r.sections if s.key == "courts")
    assert courts.factors[0].explanation == текст


def test_нераспознанный_раздел_не_теряется():
    """В данных уже есть такой: у одного фактора в chapter лежит его же код."""
    r = build(
        запись(
            reputationalRisks={
                "negative": [
                    фактор("inspectionWithViolation", "inspectionWithViolation", "Проверки")
                ],
                "positive": [],
            }
        )
    )
    assert any(f.code == "inspectionWithViolation" for s in r.sections for f in s.factors)
    assert r.unknown_chapters == ("inspectionWithViolation",)


def test_оценка_без_данных_не_становится_низким_риском():
    r = build(запись(baseInfo={**запись()["baseInfo"], "riskLevel": "UNKNOWN"}))
    assert r.bank_risk.known is False
    assert "низк" not in r.bank_risk.value.lower()


# ─────────────────────────── инварианты на настоящем наборе ───────────────────────────

try:
    _RECORDS = load().counterparties
except RuntimeError:
    _RECORDS = ()

нужен_набор = pytest.mark.skipif(not _RECORDS, reason="набор не собран")


@нужен_набор
def test_у_всех_компаний_ровно_восемь_разделов():
    for record in _RECORDS:
        assert len(build(record).sections) == 8


@нужен_набор
def test_ни_один_внутренний_код_не_попадает_в_представление():
    """Пользователь не должен увидеть massOkved ни на одной из двухсот компаний."""
    for record in _RECORDS:
        for section in build(record).sections:
            for f in section.factors:
                assert f.heading != f.code
                assert f.code not in f.heading


@нужен_набор
def test_разделы_с_сигналом_всегда_выше_пустых():
    for record in _RECORDS:
        states = [s.state for s in build(record).sections]
        последний_сигнал = max((i for i, s in enumerate(states) if s is State.SIGNAL), default=-1)
        первый_пустой = min((i for i, s in enumerate(states) if s is State.EMPTY), default=99)
        assert последний_сигнал < первый_пустой


@нужен_набор
def test_у_всех_предпринимателей_финансы_неприменимы():
    def имя(r):
        return str((r.get("baseInfo") or {}).get("shortName", ""))

    ип = [r for r in _RECORDS if имя(r).startswith("ИП")]
    assert len(ип) == 50
    for record in ип:
        fin = next(s for s in build(record).sections if s.key == "finances")
        assert fin.state is State.NOT_APPLICABLE


# ─────────────────────────── ручка ───────────────────────────


@нужен_набор
def test_ручка_отдаёт_собранный_отчёт():
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as client:
        response = client.get("/counterparties/5032257375/report")
        assert response.status_code == 200
        payload = response.json()
        assert len(payload["sections"]) == 8
        assert payload["sections"][0]["state"] == "signal"
        assert payload["bank_risk"]["source"] == "Скоринг банка"


@нужен_набор
def test_ручка_отвечает_404_на_отсутствующий_инн():
    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app) as client:
        response = client.get("/counterparties/0000000000/report")
        assert response.status_code == 404
        assert response.json()["detail"] == "Компания не найдена"

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


# ─────────────────────────── пройденные проверки ───────────────────────────


def test_подтверждение_источника_выводит_раздел_из_пустоты():
    """Раздел без собственных чисел, но с пройденной проверкой — не «данных нет».

    Ровно на этом ломались «Реестры»: своих фактов у них не бывает вовсе,
    поэтому раздел всегда падал в EMPTY, хотя источник его проверил.
    """
    record = запись(
        reputationalRisks={
            "negative": [],
            "positive": [{"code": "liquidationStatus", "chapter": "reestrs", "name": "Не найден"}],
        }
    )

    реестры = next(s for s in build(record).sections if s.key == "registries")

    assert реестры.state is State.FILLED
    assert (реестры.checks_passed, реестры.checks_total) == (1, 1)


def test_знаменатель_считает_и_сработавшие_факторы():
    """«4 из 8» сообщает больше, чем четыре сигнала без знаменателя: видно,
    что половину проверок компания прошла."""
    record = запись(
        reputationalRisks={
            "negative": [{"code": "massAddress", "chapter": "reestrs", "name": "Массовый адрес"}],
            "positive": [
                {"code": "taxArrears", "chapter": "reestrs", "name": "Не найден"},
                {"code": "dishonestProvider", "chapter": "reestrs", "name": "Не найден"},
            ],
        }
    )

    реестры = next(s for s in build(record).sections if s.key == "registries")

    assert реестры.state is State.SIGNAL
    assert (реестры.checks_passed, реестры.checks_total) == (2, 3)


def test_неприменимый_раздел_проверок_не_показывает():
    """У ИП отчётности не бывает — «0 из 0» честнее любого счётчика."""
    record = запись(
        baseInfo={"inn": "500100200300", "shortName": "ИП ИВАНОВ И. И."},
        reputationalRisks={
            "negative": [],
            "positive": [{"code": "profit", "chapter": "finance", "name": "Прибыль"}],
        },
    )

    финансы = next(s for s in build(record).sections if s.key == "finances")

    assert финансы.state is State.NOT_APPLICABLE
    assert (финансы.checks_passed, финансы.checks_total) == (0, 0)


@pytest.mark.parametrize(
    ("текст", "ожидание"),
    [
        # Название и объяснение источник разделяет запятой…
        (
            "Не найден в реестре организаций должников ФНС, что может свидетельствовать "
            "об отсутствии задолженности перед бюджетом",
            "Не найден в реестре организаций должников ФНС",
        ),
        # …тире…
        (
            "У компании есть действующие лицензии - компания имеет право осуществлять "
            "определенные виды деятельности",
            "У компании есть действующие лицензии",
        ),
        # …или точкой.
        ("Есть выигранные госконтракты. Изучите информацию", "Есть выигранные госконтракты"),
        # Точка внутри числа разделителем не является: «121259.0 тыс» должно уцелеть.
        (
            "У компании имеются оборотные активы в размере 121259.0 тыс",
            "У компании имеются оборотные активы в размере 121259.0 тыс",
        ),
    ],
)
def test_название_проверки_это_первая_фраза(текст, ожидание):
    from core.report import _check_label

    assert _check_label(текст) == ожидание


@нужен_набор
def test_все_подтверждения_дают_непустое_название():
    """Пустое название вылетело бы из списка молча, и «8 из 8» разошлось бы
    с числом строк под ним."""
    from core.report import _check_label

    for record in _RECORDS:
        for raw in (record.get("reputationalRisks") or {}).get("positive") or []:
            assert _check_label(str(raw.get("name") or ""))


@нужен_набор
def test_реестры_проверены_у_всех_двухсот():
    """Главная находка: источник проверяет реестры у каждой компании — от четырёх
    проверок до девяти. Пока раздел это игнорировал, 157 компаний из 200 видели
    «Недостаточно данных» там, где данные были и говорили «чисто»."""
    for record in _RECORDS:
        реестры = next(s for s in build(record).sections if s.key == "registries")
        assert реестры.checks_total >= 4
        assert реестры.state is not State.EMPTY


# ─────────────────────────── изменение к прошлому году ───────────────────────────


def запись_с_годами(*годы) -> dict:
    """Юрлицо с отчётностью за перечисленные (год, выручка, прибыль)."""
    return запись(
        finReports=[
            {"common": {"year": год, "proceeds": выручка, "profit": прибыль}}
            for год, выручка, прибыль in годы
        ]
    )


def факт(record: dict, начало: str):
    финансы = next(s for s in build(record).sections if s.key == "finances")
    return next(f for f in финансы.facts if f.label.startswith(начало))


def test_выручка_показывается_с_изменением_к_прошлому_году():
    """Число без сравнения решения не меняет: 116 млрд одинаково выглядят
    у растущей компании и у падающей вдвое."""
    выручка = факт(запись_с_годами((2024, 100, 5), (2025, 116, 6)), "Выручка")

    assert выручка.label == "Выручка за 2025"
    assert выручка.value == 116
    assert выручка.delta == pytest.approx(0.16)
    assert выручка.delta_note == "к 2024"


def test_единственный_год_изменения_не_даёт():
    """Отсутствие изменения означает «сравнивать не с чем», а не «не изменилось»."""
    выручка = факт(запись_с_годами((2025, 116, 6)), "Выручка")

    assert выручка.delta is None
    assert выручка.delta_note == ""


def test_рост_от_убытка_в_процентах_не_считается():
    """«Прибыль выросла на 300%» после прошлогоднего убытка арифметически верно
    и по смыслу бессмысленно. Деления на ноль тоже не бывает."""
    assert факт(запись_с_годами((2024, 100, -10), (2025, 116, 5)), "Прибыль").delta is None
    assert факт(запись_с_годами((2024, 0, 1), (2025, 116, 5)), "Выручка").delta is None


def test_коэффициенты_показываются_как_есть_с_годом():
    """Источник даёт три числа и не даёт порогов — толковать их за него нельзя.
    Год обязателен: у 9 компаний из 47 он не совпадает с годом отчётности."""
    record = запись_с_годами((2025, 100, 5))
    record["coefficient"] = {
        "year": 2024,
        "sustainability": "0.04",
        "solvency": "1.04",
        "profitability": "0.5",
    }

    финансы = next(s for s in build(record).sections if s.key == "finances")
    коэффициенты = {f.label: f.value for f in финансы.facts if f.kind == "ratio"}

    assert коэффициенты == {
        "Финансовая устойчивость, 2024": 0.04,
        "Платёжеспособность, 2024": 1.04,
        "Рентабельность, 2024": 0.5,
    }


# ─────────────────────────── противоречия в промпте ───────────────────────────


@нужен_набор
def test_противоречия_доходят_до_модели():
    """Модель должна видеть ровно то же, что экран: иначе её ответ разойдётся
    с карточкой и проверить его будет нечем."""
    from api.agent.prompt import render_report

    запись = next(r for r in _RECORDS if r["baseInfo"]["inn"] == "5032257375")
    текст = render_report(build(запись))

    assert "ПРОТИВОРЕЧИЯ В ДАННЫХ" in текст
    assert "Обе оценки зелёные" in текст
    assert "признано несостоятельным" in текст.lower()


@нужен_набор
def test_отсутствие_противоречий_проговаривается():
    """У 147 компаний из 200 не срабатывает ни одно правило. Молчание модель
    прочитала бы как «раздела нет», а не как «не нашлось»."""
    from api.agent.prompt import render_report

    чистая = next(r for r in _RECORDS if not build(r).triggers)

    assert "ПРОТИВОРЕЧИЙ В ДАННЫХ не найдено" in render_report(build(чистая))

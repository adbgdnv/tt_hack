"""Противоречия между блоками отчёта.

Логика проверяется на выдуманных записях — так видно правило в чистом виде.
Частоты закреплены на настоящем наборе: смысл именно в том, чтобы правило,
которое поехало, назвало новое число, а не промолчало.

Отвергнутые кандидаты тоже здесь: без них следующий читатель проверит их заново.
"""

import pytest

from core.repo import load
from core.triggers import build

try:
    _RECORDS = load().counterparties
except Exception:  # noqa: BLE001 — набор не собран, часть тестов пропустится
    _RECORDS = ()

нужен_набор = pytest.mark.skipif(not _RECORDS, reason="набор не собран")


def юрлицо(**поля) -> dict:
    """Минимальное юрлицо, которое точечно ломаем под конкретное правило."""
    запись = {
        "baseInfo": {"inn": "7704310756", "shortName": 'ООО "ТЕСТ"', "riskLevel": "MEDIUM"},
        "status": {"status": "CURRENT"},
        "zskRiskLevel": "YELLOW",
        "reputationalRisks": {"negative": [], "positive": []},
        "finReports": [{"common": {"year": 2026, "proceeds": 100e6, "profit": 1e6}}],
    }
    запись.update(поля)
    return запись


def ключи(запись: dict) -> set[str]:
    return {t.key for t in build(запись)}


# ─────────────────────────── правила ───────────────────────────


def test_приписка_к_статусу_замечена():
    """Все 200 компаний числятся действующими, и отчёт пишет «Действующее».
    У шести при этом в статусе приписка, и она меняет всё."""
    запись = юрлицо(status={"status": "CURRENT", "reasonName": "Признано банкротом"})

    триггер = next(t for t in build(запись) if t.key == "status_note")

    assert триггер.evidence == ("Признано банкротом",)
    assert триггер.section == "registration"


def test_зелёные_светофоры_при_тяжёлых_данных():
    """Опорное противоречие кейса: светофоры считаются по банковским операциям
    и судов не учитывают."""
    запись = юрлицо(
        baseInfo={"inn": "1", "shortName": 'ООО "ТЕСТ"', "riskLevel": "LOW"},
        zskRiskLevel="GREEN",
        arbitrationByStatus={"defandantArbitration": {"x": {"dfAmount": 200e6}}},
    )

    триггер = next(t for t in build(запись) if t.key == "lights_silent")

    assert "2 611" not in триггер.evidence[0]  # сумма своя, не из соседнего теста
    assert "200 000 000" in триггер.evidence[0]


def test_жёлтый_светофор_противоречия_не_даёт():
    """Правило про **зелёные** оценки. Жёлтая уже говорит «обратите внимание»,
    и противоречия с тяжёлыми данными в ней нет."""
    запись = юрлицо(arbitrationByStatus={"defandantArbitration": {"x": {"dfAmount": 200e6}}})

    assert "lights_silent" not in ключи(запись)


def test_управляющий_во_главе():
    """Отчёт печатает должность и ставит рядом зелёный бейдж: раздел смотрит
    на негативные коды, а должности среди них нет."""
    запись = юрлицо(foundersInfo={"authPerson": {"positionName": "КОНКУРСНЫЙ УПРАВЛЯЮЩИЙ"}})

    assert "receiver_in_charge" in ключи(запись)


def test_обычный_директор_противоречия_не_даёт():
    запись = юрлицо(foundersInfo={"authPerson": {"positionName": "ГЕНЕРАЛЬНЫЙ ДИРЕКТОР"}})

    assert "receiver_in_charge" not in ключи(запись)


def test_иски_больше_годовой_выручки():
    """Суды и финансы живут в разных карточках, и рядом их никто не ставит."""
    запись = юрлицо(arbitrationByStatus={"defandantArbitration": {"x": {"dfAmount": 150e6}}})

    assert "claims_over_revenue" in ключи(запись)


def test_отрицательный_капитал():
    запись = юрлицо(
        finReports=[
            {"common": {"year": 2026, "proceeds": 100e6}, "liabilities": {"capitals": -5e6}}
        ]
    )

    assert "negative_capital" in ключи(запись)


def test_дебиторка_считается_от_выручки_а_не_от_денег():
    """От остатка на счету сравнение давало 62 компании из 200 — это описание
    расчётов в экономике, а не компании."""
    много_денег = юрлицо(
        finReports=[{
            "common": {"year": 2026, "proceeds": 100e6},
            "assets": {"currentAssets": {"receivables": 150e6, "bankroll": 90e6}},
        }]
    )
    # денег много, но долги покупателей всё равно больше годовой выручки
    assert "receivables_over_revenue" in ключи(много_денег)

    мало_денег = юрлицо(
        finReports=[{
            "common": {"year": 2026, "proceeds": 100e6},
            "assets": {"currentAssets": {"receivables": 10e6, "bankroll": 1}},
        }]
    )
    # денег почти нет, но и долги невелики — правило молчит
    assert "receivables_over_revenue" not in ключи(мало_денег)


def test_старая_отчётность():
    """Карточка пишет «Выручка за 2023» и не говорит, что это два года назад."""
    запись = юрлицо(finReports=[{"common": {"year": 2023, "proceeds": 100e6}}])

    триггер = next(t for t in build(запись) if t.key == "stale_reporting")

    assert "2023" in триггер.explanation


def test_у_предпринимателя_отсутствие_отчётности_не_противоречие():
    """У ИП её не бывает по устройству формы — там это норма, а не сигнал."""
    ип = {"baseInfo": {"inn": "1", "shortName": "ИП ИВАНОВ И.И."}, "status": {"status": "CURRENT"}}

    assert "no_reporting" not in ключи(ип)


def test_у_юрлица_отсутствие_отчётности_противоречие():
    юр = {"baseInfo": {"inn": "1", "shortName": 'ООО "ТЕСТ"'}, "status": {"status": "CURRENT"}}

    assert "no_reporting" in ключи(юр)


def test_минимальный_уставный_капитал_при_крупных_исках():
    запись = юрлицо(
        foundersInfo={"shareCapital": 10000},
        arbitrationByStatus={"defandantArbitration": {"x": {"dfAmount": 50e6}}},
    )

    assert "thin_capital" in ключи(запись)


def test_минимальный_капитал_без_исков_молчит():
    """Уставный капитал 10 000 ₽ у большинства ООО — сам по себе это не сигнал,
    а законный минимум."""
    assert "thin_capital" not in ключи(юрлицо(foundersInfo={"shareCapital": 10000}))


# ─────────────────────────── свойства набора ───────────────────────────


@нужен_набор
def test_частоты_совпадают_с_замеренными():
    """Числа из `specs/009-risk-triggers/research.md`. Поехало правило —
    тест назовёт новое число, а не пропустит молча."""
    import collections

    счёт = collections.Counter(t.key for r in _RECORDS for t in build(r))

    assert счёт == {
        "receivables_over_revenue": 14,
        "no_reporting": 14,
        "negative_capital": 11,
        "stale_reporting": 9,
        "thin_capital": 7,
        "lights_silent": 6,
        "status_note": 6,
        "claims_over_revenue": 1,
        "receiver_in_charge": 1,
    }


@нужен_набор
def test_ни_одно_правило_не_превращается_в_фон():
    """Признак, срабатывающий чаще чем у трети набора, описывает рынок,
    а не компанию. Это требование FR-004."""
    import collections

    счёт = collections.Counter(t.key for r in _RECORDS for t in build(r))
    треть = len(_RECORDS) / 3

    for ключ, n in счёт.items():
        assert n <= треть, f"{ключ} срабатывает у {n} из {len(_RECORDS)} — это фон"


@нужен_набор
def test_у_большинства_противоречий_нет():
    """Список, который срабатывает у половины набора, ничего не сообщает."""
    молчат = sum(1 for r in _RECORDS if not build(r))

    assert молчат == 147


@нужен_набор
def test_опорный_пример_даёт_максимум():
    """МАКСМАРКЕТ — компания, ради которой продукт и сделан: оба светофора
    зелёные при банкротстве, конкурсном управляющем и 2,6 млрд исков."""
    запись = next(r for r in _RECORDS if r["baseInfo"]["inn"] == "5032257375")

    ключи_ = {t.key for t in build(запись)}

    assert len(ключи_) == 5
    assert {"lights_silent", "status_note", "receiver_in_charge"} <= ключи_


@нужен_набор
def test_каждый_триггер_называет_поля_и_раздел():
    """Триггер без полей непроверяем, без раздела — некуда пойти смотреть."""
    for record in _RECORDS:
        for триггер in build(record):
            assert триггер.fields, триггер.key
            assert триггер.section, триггер.key
            assert триггер.evidence, триггер.key


@нужен_набор
def test_поля_триггеров_есть_в_словаре():
    """Иначе подпись превратится в путь JSON на экране."""
    from core.fields import load

    словарь = load()["fields"]
    for record in _RECORDS:
        for триггер in build(record):
            for путь in триггер.fields:
                # блочные пути (`finReports`, `arbitrationByStatus.…`) в словаре
                # хранятся листьями, поэтому достаточно совпадения по префиксу
                assert any(п.startswith(путь) for п in словарь), путь


@нужен_набор
def test_формулировки_не_выносят_вердикт():
    """Принцип IV конституции: агент обращает внимание, а не решает за человека."""
    запрещено = ("не заключать", "не работать", "откажитесь", "не связывайтесь", "мошенник")

    for record in _RECORDS:
        for триггер in build(record):
            текст = f"{триггер.title} {триггер.explanation}".lower()
            for слово in запрещено:
                assert слово not in текст, f"{триггер.key}: «{слово}»"


# ─────────────────────── отвергнутые кандидаты ───────────────────────


@нужен_набор
def test_обязательства_больше_активов_срабатывает_один_раз():
    """Отвергнутый кандидат в триггеры. Актив равен пассиву в 388 отчётах
    из 396 — это тождество баланса. Восемь расхождений: семь округлений
    на 1 000 ₽ при суммах в десятки миллионов и одна компания с нулевым
    активом и уставным капиталом в пассиве.

    Правило на этом дало бы одно срабатывание, и то артефакт округления.
    Тест держит вывод, чтобы кандидата не завели заново."""
    равны = расходятся = 0
    сработало_бы = 0
    for record in _RECORDS:
        отчёты = [
            f for f in (record.get("finReports") or []) if (f.get("common") or {}).get("year")
        ]
        for отчёт in отчёты:
            активы = (отчёт.get("assets") or {}).get("totalAssets")
            пассивы = (отчёт.get("liabilities") or {}).get("totalLiabilities")
            if активы is None or пассивы is None:
                continue
            if float(активы) == float(пассивы):
                равны += 1
            else:
                расходятся += 1
        if отчёты:
            свежий = max(отчёты, key=lambda f: f["common"]["year"])
            активы = float((свежий.get("assets") or {}).get("totalAssets") or 0)
            пассивы = float((свежий.get("liabilities") or {}).get("totalLiabilities") or 0)
            сработало_бы += пассивы > активы

    assert (равны, расходятся) == (388, 8)
    assert сработало_бы == 1


@нужен_набор
def test_убыток_и_свежие_производства_уже_даёт_источник():
    """Ещё два отвергнутых кандидата: у источника есть готовые коды `profit`
    и `executionProceedings`, и они стоят у всех, у кого сработало бы правило."""
    убыток_без_кода = производства_без_кода = 0
    for record in _RECORDS:
        негативные = (record.get("reputationalRisks") or {}).get("negative") or []
        коды = {f.get("code") for f in негативные}
        отчёты = [
            f for f in (record.get("finReports") or []) if (f.get("common") or {}).get("year")
        ]
        if отчёты:
            свежий = max(отчёты, key=lambda f: f["common"]["year"])
            прибыль = (свежий.get("common") or {}).get("profit")
            if прибыль is not None and float(прибыль) < 0 and "profit" not in коды:
                убыток_без_кода += 1
        свежие = {str(p.get("date") or "")[:4] for p in (record.get("executionProceedings") or [])
                  if p.get("active")}
        if свежие & {"2025", "2026"} and "executionProceedings" not in коды:
            производства_без_кода += 1

    assert убыток_без_кода == 0
    assert производства_без_кода == 0


# ─────────────────────── порядок по вопросу ───────────────────────


def тройка():
    """Три триггера с разными тегами — на них видно перестановку."""
    from core.triggers import Trigger

    return (
        Trigger("a", "Про суды", "", "courts", 5, tags=("суды",)),
        Trigger("b", "Про деньги", "", "finances", 3, tags=("финансы",)),
        Trigger("c", "Про управление", "", "management", 4, tags=("управление",)),
    )


def test_вопрос_про_отсрочку_поднимает_финансы():
    from core.triggers import order_for

    порядок = [t.key for t in order_for(тройка(), "можно ли дать отсрочку на 60 дней")]

    assert порядок[0] == "b"


def test_вопрос_про_светофор_поднимает_надёжность():
    from core.triggers import order_for

    порядок = [t.key for t in order_for(тройка(), "почему светофор зелёный")]

    assert порядок[0] == "a"  # тег «суды» входит в намерение lights_doubt


def test_вопрос_меняет_порядок_но_не_состав():
    """Скрывать сработавшее противоречие потому, что спросили про другое,
    опасно: спросивший про выручку не должен пропустить банкротство."""
    from core.triggers import order_for

    исходные = тройка()
    for вопрос in ("отсрочка", "светофор", "поставит ли вовремя", "всё равно что"):
        переставленные = order_for(исходные, вопрос)
        assert {t.key for t in переставленные} == {t.key for t in исходные}, вопрос
        assert len(переставленные) == len(исходные), вопрос


def test_неузнанный_вопрос_оставляет_порядок_по_значимости():
    from core.triggers import intent_of, order_for

    assert intent_of("сколько у них сотрудников").key == "general"
    assert order_for(тройка(), "сколько у них сотрудников") == тройка()


def test_пустой_вопрос_ничего_не_меняет():
    from core.triggers import order_for

    assert order_for(тройка(), "") == тройка()

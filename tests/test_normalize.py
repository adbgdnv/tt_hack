"""Тесты приведения выгрузок к одной форме.

Данные внутри теста, а не из выгрузки: она лежит вне репозитория и в CI недоступна.
Заодно тест быстрый и не зависит от того, что сейчас в файлах.

Здесь закреплены три вещи, каждая из которых ломает обработку молча:

1. Обёртки `$numberLong` и `$date` — приходят только во вложенной выгрузке
   и затрагивают самые крупные суммы, вплоть до сотен миллиардов.
2. Развёртка плоских ключей `путь[индекс].подпуть` — без неё запись распадается
   на ключи с индексами в имени, и все списочные разделы пропадают целиком.
3. Приведение типов по карте — плоская выгрузка отдаёт всё текстом, и признак
   «производство активно» со значением `false`, оставленный строкой, истинен.
"""

from core.normalize import coerce, normalize_flat, type_map, unflatten, unwrap

# ─────────────────────────── обёртки ───────────────────────────


def test_unwrap_разворачивает_большое_число():
    assert unwrap({"$numberLong": "279815832000"}) == 279815832000


def test_unwrap_разворачивает_дату_в_строку():
    assert unwrap({"$date": "2024-11-10T21:00:00.000Z"}) == "2024-11-10T21:00:00.000Z"


def test_unwrap_идёт_вглубь_словарей_и_списков():
    report = {
        "finReports": [
            {"common": {"year": 2025, "proceeds": {"$numberLong": "116257852000"}}},
        ],
        "executionProceedings": [{"date": {"$date": "2019-07-15T21:00:00.000Z"}}],
    }
    result = unwrap(report)
    assert result["finReports"][0]["common"]["proceeds"] == 116257852000
    assert result["finReports"][0]["common"]["year"] == 2025
    assert result["executionProceedings"][0]["date"] == "2019-07-15T21:00:00.000Z"


def test_unwrap_не_трогает_обычные_значения():
    report = {"baseInfo": {"inn": "7704310756", "riskLevel": "LOW"}, "phones": []}
    assert unwrap(report) == report


# ─────────────────────────── развёртка плоских ключей ───────────────────────────


def test_unflatten_собирает_список_из_индексов():
    row = {
        "report.finReports[0].common.year": "2025",
        "report.finReports[1].common.year": "2024",
        "report.finReports[0].common.proceeds": "60746000",
    }
    result = unflatten(row)
    assert isinstance(result["finReports"], list)
    assert len(result["finReports"]) == 2
    assert result["finReports"][0]["common"]["year"] == "2025"
    assert result["finReports"][1]["common"]["year"] == "2024"


def test_unflatten_не_оставляет_индексов_в_именах_ключей():
    """Ровно этот дефект оставлял сто компаний с двумя полями из сорока."""
    row = {"report.reputationalRisks.negative[0].code": "arbitrationDefendant"}
    result = unflatten(row)
    assert "negative" in result["reputationalRisks"]
    assert not any("[" in key for key in result["reputationalRisks"])
    assert result["reputationalRisks"]["negative"][0]["code"] == "arbitrationDefendant"


def test_unflatten_пропускает_пустые_ячейки():
    row = {"report.baseInfo.inn": "7704310756", "report.baseInfo.email": ""}
    result = unflatten(row)
    assert result["baseInfo"]["inn"] == "7704310756"
    assert "email" not in result["baseInfo"]


def test_unflatten_игнорирует_колонки_вне_отчёта():
    row = {"_id.ogrn": "1027700132195", "report.baseInfo.inn": "7704310756"}
    assert unflatten(row) == {"baseInfo": {"inn": "7704310756"}}


# ─────────────────────────── карта типов ───────────────────────────


def test_type_map_снимает_типы_с_вложенной_выгрузки():
    records = [
        {
            "baseInfo": {"inn": "7704310756", "registrationInfo": {"yearsFromRegistration": 9}},
            "executionProceedings": [{"active": False, "amount": "517235.54"}],
        }
    ]
    types = type_map(records)
    assert types["baseInfo.inn"] == "str"
    assert types["baseInfo.registrationInfo.yearsFromRegistration"] == "int"
    assert types["executionProceedings[].active"] == "bool"


def test_type_map_сводит_большие_числа_к_обычным():
    """int и long — одно и то же число, иначе путь выглядит неоднозначным."""
    records = [
        {"finReports": [{"common": {"proceeds": 60746000}}]},
        {"finReports": [{"common": {"proceeds": {"$numberLong": "116257852000"}}}]},
    ]
    types = type_map(records)
    assert types["finReports[].common.proceeds"] == "int"


# ─────────────────────────── приведение типов ───────────────────────────


def test_coerce_превращает_текстовое_отрицание_в_ложь():
    """Главная ловушка: непустая строка 'false' истинна, и все производства
    компании становятся активными."""
    types = {"executionProceedings[].active": "bool"}
    record = {"executionProceedings": [{"active": "false"}, {"active": "true"}]}
    result = coerce(record, types)
    assert result["executionProceedings"][0]["active"] is False
    assert result["executionProceedings"][1]["active"] is True


def test_coerce_превращает_текст_в_число():
    types = {"baseInfo.registrationInfo.yearsFromRegistration": "int"}
    record = {"baseInfo": {"registrationInfo": {"yearsFromRegistration": "9"}}}
    assert coerce(record, types)["baseInfo"]["registrationInfo"]["yearsFromRegistration"] == 9


def test_coerce_оставляет_строки_строками():
    types = {"baseInfo.inn": "str"}
    record = {"baseInfo": {"inn": "7704310756"}}
    assert coerce(record, types)["baseInfo"]["inn"] == "7704310756"


def test_coerce_не_ломается_на_пути_которого_нет_в_карте():
    record = {"baseInfo": {"неизвестное": "значение"}}
    assert coerce(record, {})["baseInfo"]["неизвестное"] == "значение"


def test_coerce_не_превращает_нечисловой_текст_в_число():
    """Если поле объявлено числом, а пришёл мусор — оставляем как есть,
    а не роняем сборку и не подставляем ноль."""
    types = {"finReports[].common.year": "int"}
    record = {"finReports": [{"common": {"year": "н/д"}}]}
    assert coerce(record, types)["finReports"][0]["common"]["year"] == "н/д"


# ─────────────────────────── всё вместе ───────────────────────────


def test_normalize_flat_приводит_строку_csv_к_форме_вложенной_выгрузки():
    types = {
        "baseInfo.inn": "str",
        "baseInfo.registrationInfo.yearsFromRegistration": "int",
        "executionProceedings[].active": "bool",
        "executionProceedings[].amount": "str",
    }
    row = {
        "report.baseInfo.inn": "2466177504",
        "report.baseInfo.registrationInfo.yearsFromRegistration": "12",
        "report.executionProceedings[0].active": "false",
        "report.executionProceedings[0].amount": "517235.54",
        "report.executionProceedings[1].active": "true",
    }
    result = normalize_flat(row, types)
    assert result["baseInfo"]["inn"] == "2466177504"
    assert result["baseInfo"]["registrationInfo"]["yearsFromRegistration"] == 12
    assert result["executionProceedings"][0]["active"] is False
    assert result["executionProceedings"][1]["active"] is True
    assert len([p for p in result["executionProceedings"] if p["active"]]) == 1

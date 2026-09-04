"""Тесты отбора полей.

Данные внутри теста, а не из выгрузки: выгрузка лежит вне репозитория и в CI
недоступна. Заодно тест остаётся быстрым и не зависит от того, что там в файлах.

Главное, что здесь закреплено — распаковка $numberLong. Крупные суммы приходят
обёрнутыми, и без распаковки модель видит словарь вместо числа. Причём ровно
на самых тяжёлых делах: 4,5 и 3,0 млрд рублей.
"""

from core.slim import num, slim, unwrap


def make_report(**overrides) -> dict:
    """Минимальный отчёт, который можно точечно доломать под конкретный тест."""
    report = {
        "baseInfo": {
            "shortName": 'ООО "ТЕСТ"',
            "inn": "7704310756",
            "riskLevel": "LOW",
            "registrationInfo": {"yearsFromRegistration": 9},
        },
        "status": {"status": "CURRENT"},
        "zskRiskLevel": "GREEN",
        "reputationalRisks": {"negative": [], "positive": []},
    }
    report.update(overrides)
    return report


class TestUnwrap:
    def test_разворачивает_numberlong(self):
        assert unwrap({"$numberLong": "4534783044"}) == 4534783044

    def test_разворачивает_вложенно(self):
        source = {"assets": {"total": {"$numberLong": "279815832000"}}}
        assert unwrap(source) == {"assets": {"total": 279815832000}}

    def test_разворачивает_в_списках(self):
        assert unwrap([{"$numberLong": "10"}, 5]) == [10, 5]

    def test_обычные_значения_не_трогает(self):
        assert unwrap({"год": 2025, "имя": "тест"}) == {"год": 2025, "имя": "тест"}

    def test_дробное_остаётся_дробным(self):
        assert unwrap({"$numberDouble": "1.5"}) == 1.5


class TestNum:
    def test_из_обёртки(self):
        assert num({"$numberLong": "2611475741"}) == 2611475741.0

    def test_из_строки(self):
        assert num("517235.54") == 517235.54

    def test_из_пустоты(self):
        assert num(None) == 0.0
        assert num("") == 0.0

    def test_из_мусора(self):
        assert num("не число") == 0.0


class TestSlim:
    def test_крупные_суммы_становятся_числами(self):
        """Самый важный случай: без этого из выборки выпадают самые тяжёлые дела."""
        report = make_report(
            arbitrationByStatus={
                "commonCount": 278,
                "commonAmount": {"$numberLong": "2999541356"},
                "defandantArbitration": {
                    "defandantArbitrationFinished": {"dfAmount": {"$numberLong": "2611475741"}}
                },
            }
        )
        result = slim(report)
        assert result["арбитраж_всего_сумма"] == 2999541356
        assert result["как_ответчик_сумма"] == 2611475741

    def test_ип_распознаётся(self):
        """У ИП не бывает отчётности — агент должен это знать, а не считать пробелом."""
        report = make_report(baseInfo={"shortName": "ИП ИВАНОВ И.И.", "inn": "123456789012"})
        assert slim(report)["форма"] == "ИП"

    def test_юрлицо_распознаётся(self):
        assert slim(make_report())["форма"] == "юрлицо"

    def test_активные_производства_отделены_от_завершённых(self):
        report = make_report(
            executionProceedings=[
                {"active": True, "amount": "1000"},
                {"active": True, "amount": "500"},
                {"active": False, "amount": "99999"},
            ]
        )
        result = slim(report)
        assert result["производств_активных"] == 2
        assert result["производств_сумма_активных"] == 1500

    def test_пустые_блоки_дают_none_а_не_ноль(self):
        """Ноль читается как «проверено, чисто». None — как «данных нет». Это разные вещи."""
        result = slim(make_report())
        assert result["производств_активных"] is None
        assert result["арбитраж_всего_сумма"] is None

    def test_негативные_коды_собираются(self):
        report = make_report(
            reputationalRisks={
                "negative": [{"code": "fnsBlocking"}, {"code": "massAddress"}],
                "positive": [],
            }
        )
        assert slim(report)["негативные_факторы"] == ["fnsBlocking", "massAddress"]

    def test_отбор_действительно_сжимает(self):
        """Ради этого всё и делается: 8K токенов в минуту на бесплатном тарифе."""
        import json

        report = make_report(
            executionProceedings=[
                {"active": True, "amount": "1000", "number": f"{i}/24/98078-ИП", "date": {}}
                for i in range(45)
            ]
        )
        raw = len(json.dumps(report, ensure_ascii=False))
        slimmed = len(json.dumps(slim(report), ensure_ascii=False))
        assert slimmed < raw / 2


def test_отдаёт_руководителя():
    """Без этого поля интерфейсу неоткуда взять ФИО, и подсказка поиска
    подписывала каждую найденную компанию «Недостаточно данных» — при том
    что по этому же ФИО её и нашли."""
    report = make_report(
        foundersInfo={"authPerson": {"name": "СИЛИН АРТЁМ АЛЕКСЕЕВИЧ", "positionName": "ДИРЕКТОР"}}
    )

    assert slim(report)["руководитель"] == "СИЛИН АРТЁМ АЛЕКСЕЕВИЧ"


def test_у_предпринимателя_руководителя_нет():
    """Не «данных нет», а «такого не бывает»: поле остаётся пустым, и интерфейс
    сам решает, что показать."""
    assert slim(make_report(baseInfo={"shortName": "ИП КАЧУРИН М.О.", "inn": "343703064945"}))[
        "руководитель"
    ] is None

import re
from types import SimpleNamespace

from evals.build_cases import build_core_suite


def _record(inn, *, name="ООО ТЕСТ", risk="MEDIUM", zsk="GREEN", negative=(), court_amount=0):
    return {
        "baseInfo": {"inn": inn, "shortName": name, "riskLevel": risk},
        "zskRiskLevel": zsk,
        "reputationalRisks": {"negative": list(negative), "positive": []},
        "arbitrationByStatus": {"commonAmount": court_amount},
    }


def _build_report(record):
    inn = record["baseInfo"]["inn"]
    is_ip = record["baseInfo"]["shortName"].startswith("ИП ")
    negatives = record["reputationalRisks"]["negative"]
    factor = SimpleNamespace(heading=(negatives[0]["heading"] if negatives else ""))
    return SimpleNamespace(
        inn=inn,
        is_entrepreneur=is_ip,
        sections=(
            SimpleNamespace(
                key="finances",
                title="Финансы",
                state=SimpleNamespace(value="not_applicable" if is_ip else "filled"),
                factors=(),
            ),
            SimpleNamespace(
                key="related",
                title="Связанные организации",
                state=SimpleNamespace(value="empty" if inn.startswith("e") else "filled"),
                factors=(factor,) if negatives else (),
            ),
        ),
    )


def _build_charts(record):
    keys = record.get("chart_keys", ())
    return [SimpleNamespace(key=key) for key in keys]


def _fixture_records():
    rows = []
    for i in range(6):
        # У четырёх из шести компаний с пустым светофором есть живые сигналы —
        # это и есть материал для категории unknown_with_signals.
        negative = (
            ({"code": "arbitrationDefendant", "heading": "Ответчик в арбитраже"},) if i < 4 else ()
        )
        rows.append(
            _record(
                f"u{i}",
                risk="UNKNOWN",
                negative=negative,
                court_amount=(i + 1) * 1_000_000 if negative else 0,
            )
        )
    for i in range(5):
        rows.append(_record(f"n{i}", court_amount=(i + 2) * 1_000_000_000))
    for i in range(5):
        rows.append(
            _record(
                f"c{i}",
                risk="LOW",
                negative=({"code": "liquidationStatus", "heading": "Процедура банкротства"},),
                court_amount=100 + i,
            )
        )
    for i in range(4):
        rows.append(_record(f"ip{i}", name=f"ИП ИВАНОВ {i}"))
    for i in range(4):
        rows.append(_record(f"e{i}"))

    rating = _record("rating", risk="LOW", zsk="YELLOW")
    rows.append(rating)

    charts = _record("charts")
    charts["chart_keys"] = ("profit_years", "arbitration_years", "proceedings_years")
    rows.append(charts)
    return rows


def test_core_suite_contains_exactly_36_high_value_cases():
    cases = build_core_suite(_fixture_records(), _build_report, _build_charts)

    assert len(cases) == 36
    counts = {}
    for case in cases:
        counts[case.category] = counts.get(case.category, 0) + 1

    assert counts == {
        "bank_unknown": 6,
        "unknown_with_signals": 4,
        "large_numbers": 5,
        "risk_conflict": 5,
        "not_applicable": 4,
        "empty": 4,
        "bank_scale": 1,
        "zsk_source": 1,
        "rating_methodology": 1,
        "chart_routing": 3,
        "deal_terms": 2,
    }


def test_conflict_cases_require_a_real_signal_and_forbid_decision_claims():
    cases = build_core_suite(_fixture_records(), _build_report, _build_charts)
    conflict = next(case for case in cases if case.category == "risk_conflict")

    assert any("можно" in pattern for pattern in conflict.expect.forbidden_patterns)
    # Сигнал должен опознаваться в пересказе своими словами, а не только дословно.
    pattern = conflict.expect.required_patterns[0]
    assert re.search(pattern, "в отношении компании идёт процедура банкротства", re.IGNORECASE)
    assert not re.search(pattern, "никаких замечаний по компании", re.IGNORECASE)


def test_unknown_with_signals_requires_naming_the_found_fact():
    """Пустой светофор банка не освобождает от независимого вердикта по данным."""
    cases = build_core_suite(_fixture_records(), _build_report, _build_charts)
    signal_cases = [case for case in cases if case.category == "unknown_with_signals"]

    assert len(signal_cases) == 4
    for case in signal_cases:
        assert "рисков нет" in case.expect.forbidden_patterns
        # Пересказ своими словами засчитывается, дословная цитата заголовка не нужна.
        pattern = case.expect.required_patterns[0]
        assert re.search(pattern, "1 525 дел, из них как ответчиком — 2,69 млрд ₽", re.IGNORECASE)
        assert not re.search(pattern, "банк оценку не выставил, это всё", re.IGNORECASE)
        # Конкретная сумма здесь не требуется — вопрос не про неё.
        assert not case.expect.numbers


def test_bank_unknown_forbids_the_bank_verdict_not_the_words():
    """«Зелёный ЗСК — низкий риск вовлечённости» — верная фраза про другой светофор."""
    cases = build_core_suite(_fixture_records(), _build_report, _build_charts)
    case = next(case for case in cases if case.category == "bank_unknown")
    forbidden = case.expect.forbidden_patterns

    about_zsk = "Уровень ЗСК — «Зелёный». Это низкий риск вовлечённости в операции."
    # Зазор в паттерне не должен перепрыгивать перевод строки и отрицание.
    denied = "Скоринг банка (внутренняя модель) — «Оценить невозможно»\nЭто не низкий риск."
    about_bank = "Скоринг банка низкий, беспокоиться не о чем."
    assert not any(re.search(p, about_zsk, re.IGNORECASE) for p in forbidden)
    assert not any(re.search(p, denied, re.IGNORECASE) for p in forbidden)
    assert any(re.search(p, about_bank, re.IGNORECASE) for p in forbidden)

    # «Безопасность» запрещена как утверждение, а не как слово.
    caveat = "Полагаться на неё как на индикатор безопасности нельзя."
    claim = "Сотрудничество с компанией безопасно."
    assert not any(re.search(p, caveat, re.IGNORECASE) for p in forbidden)
    assert any(re.search(p, claim, re.IGNORECASE) for p in forbidden)


def test_empty_sections_accept_synonyms_of_no_data():
    cases = build_core_suite(_fixture_records(), _build_report, _build_charts)
    case = next(case for case in cases if case.category == "empty")
    pattern = case.expect.required_patterns[0]

    for answer in (
        "Бухгалтерской отчётности нет ни за один год.",
        "Нельзя оценить выручку и активы компании.",
        "Данных нет.",
        "Сведений о связанных организациях нет.",
        "Оценить этот раздел невозможно.",
    ):
        assert re.search(pattern, answer, re.IGNORECASE), answer
    assert not re.search(pattern, "По разделу всё в порядке.", re.IGNORECASE)


def test_deal_cases_cover_named_and_unknown_terms():
    """Разбор под сделку проверяется в двух состояниях: условия названы и нет."""
    cases = build_core_suite(_fixture_records(), _build_report, _build_charts)
    deal_cases = [case for case in cases if case.category == "deal_terms"]

    assert len(deal_cases) == 2
    named, unknown_terms = deal_cases
    assert "отсрочкой" in named.turns[0].user
    # При названной схеме разбор обязан связать её с тем, чем она рискует.
    assert re.search(named.expect.required_patterns[1], "смогут ли рассчитаться", re.IGNORECASE)
    # Без условий агент спрашивает о сделке и не выдаёт вердикт за пользователя.
    assert re.search(unknown_terms.expect.required_patterns[0], "аванс или отсрочка?", re.I)
    assert any(
        re.search(pattern, "С ними не стоит работать.", re.IGNORECASE)
        for pattern in unknown_terms.expect.forbidden_patterns
    )


def test_chart_cases_grade_the_exact_chart_kind():
    cases = build_core_suite(_fixture_records(), _build_report, _build_charts)
    chart_cases = [case for case in cases if case.category == "chart_routing"]

    assert {case.expect.required_tools[0].params["kind"] for case in chart_cases} == {
        "profit_years",
        "arbitration_years",
        "proceedings_years",
    }

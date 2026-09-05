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
        rows.append(_record(f"u{i}", risk="UNKNOWN"))
    for i in range(5):
        rows.append(_record(f"n{i}", court_amount=(i + 2) * 1_000_000_000))
    for i in range(5):
        rows.append(
            _record(
                f"c{i}",
                risk="LOW",
                negative=({"heading": f"Сигнал {i}"},),
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


def test_core_suite_contains_exactly_30_high_value_cases():
    cases = build_core_suite(_fixture_records(), _build_report, _build_charts)

    assert len(cases) == 30
    counts = {}
    for case in cases:
        counts[case.category] = counts.get(case.category, 0) + 1

    assert counts == {
        "bank_unknown": 6,
        "large_numbers": 5,
        "risk_conflict": 5,
        "not_applicable": 4,
        "empty": 4,
        "bank_scale": 1,
        "zsk_source": 1,
        "rating_methodology": 1,
        "chart_routing": 3,
    }


def test_conflict_cases_require_a_real_signal_and_forbid_decision_claims():
    cases = build_core_suite(_fixture_records(), _build_report, _build_charts)
    conflict = next(case for case in cases if case.category == "risk_conflict")

    assert any("Сигнал" in pattern for pattern in conflict.expect.required_patterns)
    assert any("можно" in pattern for pattern in conflict.expect.forbidden_patterns)


def test_chart_cases_grade_the_exact_chart_kind():
    cases = build_core_suite(_fixture_records(), _build_report, _build_charts)
    chart_cases = [case for case in cases if case.category == "chart_routing"]

    assert {case.expect.required_tools[0].params["kind"] for case in chart_cases} == {
        "profit_years",
        "arbitration_years",
        "proceedings_years",
    }

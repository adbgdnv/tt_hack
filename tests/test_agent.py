"""Диалог о контрагенте.

Модель подменяется: проверяется поведение цикла, а не качество ответов. Качество
проверяется вручную по quickstart на живом провайдере — автоматически его
не поймать, а вот сборку контекста и сброс истории поймать можно.
"""

import pytest

from api.agent import loop
from api.agent.prompt import SYSTEM_PROMPT, build_messages, render_report
from core.llm import Answer
from core.report import build


class ФейковаяМодель:
    """Запоминает, что ей передали, и отвечает заготовкой."""

    def __init__(self, text="Ответ по отчёту"):
        self.text = text
        self.messages = None

    def ask(self, messages, **_):
        self.messages = messages
        return Answer(content=self.text)


def запись(inn="7704310756", name='ООО "ТЕСТ"', **overrides) -> dict:
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
    }
    record.update(overrides)
    return record


@pytest.fixture(autouse=True)
def чистые_сессии():
    loop._SESSIONS.clear()
    yield
    loop._SESSIONS.clear()


# ─────────────────────────── контекст ───────────────────────────


def test_отчёт_уходит_в_контекст_целиком():
    """Модель должна видеть ровно то, что видит пользователь."""
    report = build(запись())
    messages = build_messages(report, "Что настораживает?")
    сплошняком = "\n".join(m["content"] for m in messages)
    assert SYSTEM_PROMPT in сплошняком
    assert report.name in сплошняком
    for section in report.sections:
        assert section.title in сплошняком


def test_в_контексте_нет_инструментов():
    """Инструменты не даём: невызванный инструмент — путь к выдумыванию."""
    messages = build_messages(build(запись()), "Вопрос")
    assert all(m["role"] in {"system", "user", "assistant"} for m in messages)


def test_отсутствие_оценки_проговаривается_словами():
    """«Оценить невозможно» не должно читаться моделью как низкий риск."""
    record = запись()
    record["baseInfo"]["riskLevel"] = "UNKNOWN"
    текст = render_report(build(record))
    assert "оценка отсутствует" in текст
    assert "это не низкий риск" in текст


def test_у_предпринимателя_разделы_помечены_неприменимыми():
    текст = render_report(build(запись(name="ИП Иванов И.И.")))
    assert "не применимо к этой форме собственности" in текст


# ─────────────────────────── сессия ───────────────────────────


def test_история_накапливается():
    state, report, модель = loop.session("s1"), build(запись()), ФейковаяМодель()
    loop.run(state, report, "Первый вопрос", модель)
    loop.run(state, report, "Второй вопрос", модель)
    assert len(state.history) == 4
    assert state.history[0]["content"] == "Первый вопрос"


def test_смена_контрагента_сбрасывает_разговор():
    """Ответы о предыдущей компании в новом контексте вводят в заблуждение."""
    state, модель = loop.session("s1"), ФейковаяМодель()
    loop.run(state, build(запись(inn="1111111111")), "Вопрос про первую", модель)
    assert state.history
    loop.run(state, build(запись(inn="2222222222")), "Вопрос про вторую", модель)
    assert len(state.history) == 2
    assert state.focus_inn == "2222222222"


def test_история_ограничена_по_длине():
    """Растущая история съела бы минутную квоту провайдера."""
    state, report, модель = loop.session("s1"), build(запись()), ФейковаяМодель()
    for i in range(loop.HISTORY_TURNS + 4):
        loop.run(state, report, f"Вопрос {i}", модель)
    assert len(state.history) <= loop.HISTORY_TURNS * 2


# ─────────────────────────── отказ и сбой ───────────────────────────


def test_пустой_ответ_модели_это_ошибка_а_не_ответ():
    """У gpt-oss рассуждение приходит отдельным полем и способно съесть бюджет,
    оставив content пустым. Выдавать пустоту за ответ нельзя."""
    with pytest.raises(RuntimeError):
        loop.run(loop.session("s1"), build(запись()), "Вопрос", ФейковаяМодель(""))


def test_обоснование_отмечает_только_названные_разделы():
    """Придуманное обоснование хуже отсутствующего: выглядит как проверка,
    которой не было."""
    report = build(запись())
    модель = ФейковаяМодель("По разделу Суды данных нет.")
    answer = loop.run(loop.session("s1"), report, "Что по судам?", модель)
    assert "courts" in answer.sections
    assert "finances" not in answer.sections


def test_промпт_перечисляет_настоящие_разделы():
    """Список возможностей в промпте должен совпадать с разделами отчёта.

    Иначе ассистент обещает то, чего нет: переименовали раздел — и на вопрос
    «что ты умеешь» он называет несуществующий. Обещание, которого продукт
    не выполняет, хуже отсутствующего.
    """
    from core.report import SECTION_TITLES

    пропущены = [
        название
        for название in SECTION_TITLES.values()
        # в промпте они перечислены в именительном падеже и без заглавной
        if название.split()[0].lower()[:6] not in SYSTEM_PROMPT.lower()
    ]
    assert not пропущены, f"в промпте не названы разделы: {пропущены}"


def test_промпт_очерчивает_границы():
    """Без явного «не умею» модель отвечает как обычная языковая модель —
    обещает переводы и разговор на любые темы. Проверено на живом провайдере."""
    for граница in ["не умеешь", "переводить", "отраслевыми нормами", "вне отчёта"]:
        assert граница in SYSTEM_PROMPT.lower(), f"из промпта пропала граница: {граница}"

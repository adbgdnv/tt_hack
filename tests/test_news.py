"""Новости из внешних источников.

Ни один тест не ходит в сеть и не зовёт модель: проверяется то, что мы делаем
с её ответом. Именно там живут решения — что считать тревожным, что выбросить
и как свести оценки в одну.
"""

import pytest

from api import news


def находка(номер: int) -> dict:
    return {"title": f"Заголовок {номер}", "url": f"https://истоЧник{номер}.ru/a", "snippet": ""}


def суждение(номер: int, level: str, *, party: bool = True, summary: str = "что-то было"):
    return news._Judgement(index=номер, level=level, party=party, summary=summary)


def test_событие_со_сторонним_участником_не_тревожное():
    """Проверено на живом ответе: страница про ООО «888» говорила «новое дело
    о банкротстве, организация в роли иного лица». Модель верно писала роль
    в текст, но всё равно ставила «тревожная», и чистая компания получала
    красную плашку. Роль спрашиваем отдельно, вывод делает код.
    """
    items = news._items(
        [находка(1)],
        [суждение(1, news.ALARMING, party=False, summary="компания в роли иного лица")],
    )

    assert items[0].level == news.NEUTRAL
    # Сама находка с экрана не пропадает: пользователь видит её и судит сам.
    assert items[0].summary == "компания в роли иного лица"


def test_событие_с_самой_компанией_остаётся_тревожным():
    items = news._items([находка(1)], [суждение(1, news.ALARMING, party=True)])

    assert items[0].level == news.ALARMING


def test_справочники_и_чужие_компании_выбрасываются():
    """Поиск по названию находит карточки реквизитов и однофамильцев.
    Выдавать их за новости о контрагенте нельзя."""
    items = news._items(
        [находка(1), находка(2)],
        [суждение(1, news.IRRELEVANT, summary=""), суждение(2, news.NEUTRAL)],
    )

    assert [i.title for i in items] == ["Заголовок 2"]


def test_находка_без_оценки_не_показывается():
    """Модель может вернуть оценок меньше, чем находок. Показать находку
    без суждения значит выдать сырую выдачу поиска за проверенную новость."""
    assert news._items([находка(1), находка(2)], [суждение(2, news.NEUTRAL)]) != ()
    assert len(news._items([находка(1), находка(2)], [суждение(2, news.NEUTRAL)])) == 1


def test_общий_уровень_считается_кодом():
    """Модель судит о каждой находке, где у неё перед глазами текст. Свести три
    оценки в одну она может только по памяти — а это правило в одну строку."""
    тревожная = news.Item("", "", "", news.ALARMING)
    спокойная = news.Item("", "", "", news.NEUTRAL)

    assert news._level((спокойная, тревожная, спокойная)) == news.ALARMING
    assert news._level((спокойная, спокойная)) == news.NEUTRAL
    assert news._level(()) == ""


def test_запрос_не_подсказывает_ответ():
    """Слова «суд» и «банкротство» в запросе превращают поиск в подтверждение
    собственной гипотезы: найдётся ровно то, что спросили, и у чистой компании
    тоже. Спрашиваем про компанию, оценку даёт модель."""
    запрос = news._query('ООО "ТЕСТ"', "7704310756")

    assert 'ООО "ТЕСТ"' in запрос
    assert "7704310756" in запрос
    for подсказка in ("суд", "банкрот", "штраф", "долг", "санкц", "мошенн"):
        assert подсказка not in запрос.lower()


def test_потолок_страницы_жёстче_чем_у_инструмента_агента():
    """Три страницы уходят в модель разом, и общий бюджет 8 000 токенов в минуту
    делится с диалогом."""
    from api.agent import search

    assert news.PAGE_CHARS < search.PAGE_CHARS
    assert news.MAX_ITEMS * news.PAGE_CHARS <= 4500


def test_оценка_новостей_идёт_по_той_же_цепочке(monkeypatch):
    """Своего провайдера у новостей больше нет.

    Был бесплатный Groq впереди — экономия на короткой разметке. Отменено
    замером: 197 462 из 200 000 токенов Groq в сутки, и блок отвечал
    «внешний поиск не отвечает», выдавая кончившуюся квоту за сбой связи.
    Разметка одной новости на основной модели стоит около трёх десятых цента.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-тест")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-тест")
    заказано = {}

    class Подставной:
        def __init__(self, provider="", **_):
            заказано.setdefault("провайдеры", []).append(provider)

        def chat(self, max_tokens=0, **_):
            заказано["бюджет"] = max_tokens
            raise RuntimeError("дальше сети не идём")

    monkeypatch.setattr(news, "LLMClient", Подставной)
    with pytest.raises(RuntimeError):
        news._assess([{"title": "т", "snippet": "с"}], [""], "ООО «Т»")

    # Первым спрашивается основной путь диалога, последним — бесплатный Groq
    assert заказано["провайдеры"] == ["openrouter", "openrouter", "groq"]
    # Запас на ответ. Прежние 700 стояли под gpt-oss с `reasoning_effort="low"`;
    # на deepseek рассуждение съело 612 из них, ответ не распарсился, и блок
    # показал «внешний поиск не отвечает» — сбой связи вместо сбоя бюджета.
    assert заказано["бюджет"] >= 1500


def test_без_ключей_блок_не_падает_молча(monkeypatch):
    """Без единого настроенного провайдера оценка обязана честно отказать,
    а не сделать вид, что новостей нет."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    заказано = {}

    class Подставной:
        def __init__(self, provider="", **_):
            заказано.setdefault("провайдеры", []).append(provider)

        def chat(self, **_):
            raise RuntimeError("дальше сети не идём")

    monkeypatch.setattr(news, "LLMClient", Подставной)
    with pytest.raises(RuntimeError):
        news._assess([{"title": "т", "snippet": "с"}], [""], "ООО «Т»")

    assert заказано["провайдеры"] == [""]


def test_отказ_первого_пути_не_убивает_блок(monkeypatch):
    """Замерено на живом сервере: квота провайдера кончается, и блок отвечал
    «внешний поиск не отвечает» — то есть выдавал исчерпанную квоту за сбой
    связи. Один упавший путь не должен уносить весь блок."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-тест")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-тест")
    спрошены = []

    class Подставной:
        def __init__(self, provider="", model="", **_):
            self.модель = model
            спрошены.append(model or provider)

        def chat(self, **_):
            if self.модель == "deepseek/deepseek-v4-flash":
                raise RuntimeError("429 rate_limit_exceeded")
            return self

        def with_structured_output(self, _схема):
            return self

        def invoke(self, _сообщения, config=None):
            from api.news import _Assessment, _Judgement

            return _Assessment(
                judgements=[_Judgement(index=1, level="нейтральная", party=True, summary="ок")]
            )

    monkeypatch.setattr(news, "LLMClient", Подставной)

    оценки = news._assess([{"title": "т", "snippet": "с"}], [""], "ООО «Т»")

    assert спрошены[0] == "deepseek/deepseek-v4-flash"
    assert спрошены[1] == "z-ai/glm-5.3-flash"
    assert len(оценки) == 1

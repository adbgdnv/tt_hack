"""Поиск во внешних открытых источниках.

Сеть не трогаем: у нас проверяется обработка ответа и поведение при отказе,
а не работоспособность чужого сервера.
"""

import json

from api.agent import search


async def позвать(запрос):
    """Настоящий вызов инструмента, а не его функции: так проверяется и упаковка
    добавки в сообщение, которое дальше читает перевод событий."""
    сообщение = await search.web_search.ainvoke(
        {"name": "web_search", "args": {"query": запрос}, "id": "1", "type": "tool_call"}
    )
    return сообщение.content, сообщение.artifact

ОТВЕТ_СЕРВЕРА = {
    "results": [
        {
            "title": 'ООО "МАКСМАРКЕТ", ИНН 5032257375',
            "url": "https://focus.kontur.ru/entity?query=1165032060050",
            "content": "находится в процессе банкротства. " + "х" * 500,
        },
        {
            "title": "Максмаркет",
            "url": "https://rusprofile.ru/id/10658276",
            "content": "Статус: в пр",
        },
        {"title": "Третий", "url": "https://example.com/3", "content": "…"},
        {"title": "Четвёртый", "url": "https://example.com/4", "content": "…"},
    ]
}


def test_находки_урезаются_по_числу():
    """Бюджет токенов общий с ответом: неурезанный ответ поиска — около 570 токенов."""
    находки = search._shape(json.dumps(ОТВЕТ_СЕРВЕРА))

    assert len(находки) == search.MAX_RESULTS == 3


def test_выдержки_урезаются_по_длине():
    находки = search._shape(json.dumps(ОТВЕТ_СЕРВЕРА))

    assert len(находки[0]["snippet"]) == search.SNIPPET


def test_у_каждой_находки_есть_ссылка():
    """Без ссылки пользователь не отличит найденное от выверенного и не проверит."""
    находки = search._shape(json.dumps(ОТВЕТ_СЕРВЕРА))

    assert all(н["url"].startswith("http") for н in находки)


def test_находки_без_ссылки_отбрасываются():
    находки = search._shape(json.dumps({"results": [{"title": "Без ссылки", "content": "…"}]}))

    assert находки == []


def test_ответ_блоками_разбирается():
    """MCP отдаёт содержимое блоками, а не голой строкой."""
    блоки = [{"type": "text", "text": json.dumps(ОТВЕТ_СЕРВЕРА)}]

    assert len(search._shape(блоки)) == 3


def test_непонятный_ответ_не_роняет():
    assert search._shape("не json") == []
    assert search._shape({}) == []


async def test_недоступность_сервера_не_роняет_ответ(monkeypatch):
    """Внешняя система по сети отказывает чаще нашего кода и не может утаскивать
    за собой ответ по отчёту."""

    async def упасть(_):
        raise ConnectionError("сервер недоступен")

    monkeypatch.setattr(search, "_search", упасть)

    текст, добавка = await позвать("что угодно")

    assert "недоступен" in текст
    assert "по отчёту" in текст  # модели сказано, что делать дальше
    assert добавка == {}


async def test_пустой_результат_это_ответ_а_не_ошибка(monkeypatch):
    async def пусто(_):
        return []

    monkeypatch.setattr(search, "_search", пусто)

    текст, добавка = await позвать("что угодно")

    assert "ничего не найдено" in текст
    assert добавка == {}


async def test_выдача_подана_как_сырьё_а_не_как_ответ(monkeypatch):
    """Прежняя формулировка «найдено во внешних источниках» звучала как готовый
    список находок, и модель пересказывала его целиком — включая адрес и дату
    регистрации, которые есть в отчёте, выдавая их за внешние сведения.

    Кейсодатель: «доверяем прежде всего данным, которые есть у нас». Значит
    совпадение с отчётом подтверждает отчёт, а не является новостью.
    """

    async def нашлось(_):
        return [{"title": "Контур", "url": "https://focus.kontur.ru/x", "snippet": "банкротство"}]

    monkeypatch.setattr(search, "_search", нашлось)

    текст, добавка = await позвать("банкротство")
    сплошняком = " ".join(текст.split())  # указания переносятся по строкам

    assert "не ответ" in сплошняком  # выдачу надо разбирать, а не пересказывать
    assert "ничего подходящего нет" in сплошняком  # что делать, если не нашлось
    assert "подтверждает отчёт" in сплошняком  # совпадение — не новое сведение
    assert "https://focus.kontur.ru/x" in текст
    assert добавка["sources"][0]["url"] == "https://focus.kontur.ru/x"


def test_без_ключа_инструмент_не_создаётся(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    assert search.enabled() is False
    assert search.tools() == []


# ─────────────────────────── чтение страницы ───────────────────────────


async def прочитать(ссылка, вопрос):
    сообщение = await search.fetch_page.ainvoke(
        {
            "name": "fetch_page",
            "args": {"url": ссылка, "question": вопрос},
            "id": "1",
            "type": "tool_call",
        }
    )
    return сообщение.content, сообщение.artifact


async def test_страница_урезается_по_потолку(monkeypatch):
    """Замерено на живом ключе: страница целиком — 14 645 токенов при минутной
    квоте провайдера 8 000. Один вызов превышал бы весь бюджет минуты вдвое."""

    async def длинная(*_):
        return "х" * 100_000

    monkeypatch.setattr(search, "_fetch", длинная)

    текст, _ = await прочитать("https://x", "банкротство")

    assert len(текст) < search.PAGE_CHARS + 500  # плюс сопроводительная фраза


async def test_прочитанное_помечено_внешним(monkeypatch):
    async def страница(*_):
        return "в процессе банкротства"

    monkeypatch.setattr(search, "_fetch", страница)

    текст, добавка = await прочитать("https://focus.kontur.ru/x", "банкротство")

    assert "внешний источник" in текст
    assert "подтверждает" in текст  # совпадение с отчётом — не новое сведение
    assert добавка["sources"][0]["url"] == "https://focus.kontur.ru/x"


async def test_недоступная_страница_не_роняет_ответ(monkeypatch):
    async def упасть(*_):
        raise TimeoutError("страница не отвечает")

    monkeypatch.setattr(search, "_fetch", упасть)

    текст, добавка = await прочитать("https://x", "что угодно")

    assert "не удалось" in текст
    assert "по отчёту" in текст
    assert добавка == {}


async def test_пустая_страница_это_ответ(monkeypatch):
    async def пусто(*_):
        return "   "

    monkeypatch.setattr(search, "_fetch", пусто)

    текст, добавка = await прочитать("https://x", "что угодно")

    assert "пустая" in текст
    assert добавка == {}


def test_текст_страницы_разворачивается_из_обёртки():
    """Ответ их сервера — блоки, внутри JSON со служебными полями. Обёртка стоит
    токенов и мешает модели: нужен из неё один ключ."""
    выдача = {"results": [{"url": "https://x", "raw_content": "судебных дел нет"}]}
    блоки = [{"type": "text", "text": json.dumps(выдача)}]

    assert search._page_text(блоки) == "судебных дел нет"


def test_не_json_считается_готовым_текстом():
    assert search._page_text("просто текст") == "просто текст"

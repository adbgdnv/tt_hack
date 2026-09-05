"""HTTP-сервис: веб-интерфейс ходит сюда.

Тонкая обёртка над `core`. Бизнес-логики здесь нет и быть не должно — только разбор
запроса, вызов ядра и формирование ответа. Проверка границы: удалить src/mcp_server —
этот сервис продолжит работать.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api import news
from api.agent import loop
from api.agent import tools as agent_tools
from core import repo, slim
from core import report as report_view


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Набор читается при старте, а не при первом запросе.

    Если его нет, сервис не поднимается вовсе. Работа с пустым набором запрещена
    контрактом: отчёты выглядели бы как «у всех компаний ничего нет», и отличить
    это от честного результата было бы невозможно.
    """
    repo.load()
    yield


# На сервере сервис живёт за nginx по префиксу /api, локально — в корне.
# Префикс нужен только для генерации ссылок: без него Swagger на /api/docs просит
# схему с корня и ломается. На сопоставление маршрутов не влияет.
app = FastAPI(
    title="Проверка контрагента",
    version="0.1.0",
    lifespan=lifespan,
    root_path=os.environ.get("API_ROOT_PATH", ""),
)

# фронт поднимается отдельным процессом на 5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    """Вопрос о контрагенте в фокусе."""

    message: str
    inn: str
    session_id: str = "default"


def _serialize(report: report_view.Report) -> dict:
    """Представление в словарь. Состояние раздела уезжает строкой — интерфейсу
    незачем знать про перечисления Python."""
    payload = asdict(report)
    for section in payload["sections"]:
        section["state"] = section["state"].value
    # Пути внутри данных в интерфейс не уходят: `fields` — это то, чем триггер
    # проверяется, а на экране пользователь видит слова (FR-013).
    for триггер in payload.get("triggers", []):
        триггер.pop("fields", None)
    return payload


@app.get("/health")
def health() -> dict:
    """Проверка живости — и готовности отвечать данными.

    Числа контрагентов и времени сборки здесь достаточно, чтобы отличить «сервис
    поднят» от «сервис отдаёт настоящие данные». Неразличимость этих состояний —
    ровно то, из-за чего продукт долго показывал заготовленные примеры.
    """
    return {"status": "ok", "dataset": repo.stats()}


@app.get("/counterparties/search")
def search(q: str, limit: int = 10) -> list[dict]:
    """Поиск по названию или ИНН.

    Пустой список — не ошибка: он означает «в наборе таких нет», и интерфейс
    сообщает об этом, а не показывает сбой.
    """
    return [slim.slim(r) for r in repo.search(q, limit)]


@app.get("/counterparties/{inn}/report")
def get_report(inn: str) -> dict:
    """Собранный отчёт: шапка, обе оценки риска, восемь разделов в порядке значимости.

    Тем же представлением пользуется диалог — модель должна видеть ровно то, что видит
    пользователь, иначе ответ разойдётся с экраном и проверить его будет нельзя.

    Отобранная выдача по `/counterparties/{inn}` остаётся: она нужна MCP
    и программному доступу.
    """
    record = repo.by_inn(inn)
    if record is None:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    return _serialize(report_view.build(record))


@app.get("/counterparties/{inn}/news")
async def get_news(inn: str) -> dict:
    """Новости о компании из внешних источников с оценкой каждой находки.

    Отдельной ручкой, а не полем отчёта: отчёт собирается из набора мгновенно
    и не должен ждать чужой сервер. Экран открывается на отчёте, новости
    приезжают следом.

    Без ключа поиска — 404, а не пустой список: пустой блок новостей читался бы
    как «ничего не пишут», хотя мы просто не смотрели.
    """
    record = repo.by_inn(inn)
    if record is None:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    if not news.enabled():
        raise HTTPException(status_code=404, detail="Внешний поиск не настроен")
    собранное = await news.collect(str((record.get("baseInfo") or {}).get("shortName") or ""), inn)
    return asdict(собранное)


@app.get("/counterparties/{inn}")
def get_counterparty(inn: str) -> dict:
    """Отобранный отчёт по ИНН из подготовленного набора.

    Контрагента нет в наборе — 404. Промежуточных состояний между «есть целиком»
    и «нет» продукт не различает, а пустой отчёт неотличим от «у компании всё чисто».
    """
    report = repo.by_inn(inn)
    if report is None:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    return slim.slim(report)


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Тот же диалог, но событиями по мере работы агента.

    Контракт — `specs/006-chat-agent-tools/contracts/stream.md`. Основной путь
    продукта: только здесь у модели есть инструменты, потому что только здесь
    есть куда доставить график.

    Сбой отдаётся событием внутри потока, а не кодом ответа: заголовки уже ушли
    к моменту, когда модель отказывает, и уже показанный пользователю текст
    должен остаться на экране.
    """
    record = repo.by_inn(request.inn)
    if record is None:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    built = report_view.build(record)
    session = loop.session(request.session_id)

    async def events():
        stream = loop.run_stream(
            session, built, record, request.message, agent_tools.build(record, request.inn)
        )
        # Разрыв соединения клиентом отменяет задачу и закрывает генератор:
        # недоеденный ответ продолжал бы тратить квоту, общую на всех.
        async for event in stream:
            yield event.encode()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Подсказка nginx на случай, если в конфиге забыли proxy_buffering off:
            # без неё поток копится в буфере и приходит целиком.
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/chat")
async def chat(request: ChatRequest) -> dict:
    """Диалог о контрагенте одним ответом, без потока.

    Для клиентов, которые событий не понимают. Агент тот же, что в `/chat/stream`:
    те же инструменты и тот же контекст, отличается только доставка. То, что там
    приходит событиями `chart` и `sources`, здесь лежит в полях ответа — иначе
    внешние сведения пришли бы без ссылок, чего промпт не допускает.

    Память — в рамках одной сессии, между сессиями не храним. Модель получает
    тот же отчёт, что видит пользователь: иначе ответ разойдётся с экраном
    и проверить его будет нельзя.

    Недоступность провайдера отдаётся как 502, а не как пустой ответ: сбой сервиса
    нельзя выдавать за содержательный ответ о компании.
    """
    record = repo.by_inn(request.inn)
    if record is None:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    built = report_view.build(record)
    try:
        answer = await loop.run(
            loop.session(request.session_id),
            built,
            record,
            request.message,
            agent_tools.build(record, request.inn),
        )
    except Exception as error:  # noqa: BLE001 — наружу уходит один понятный ответ
        raise HTTPException(
            status_code=502,
            detail="Сервис разбора сейчас недоступен. Отчёт выше остаётся полным.",
        ) from error
    return {
        "answer": answer.text,
        "sections": list(answer.sections),
        "charts": list(answer.charts),
        "sources": list(answer.sources),
        # То, что в потоке приходит событиями `lookup` и `check`. Без первого
        # клиент не увидел бы данные, на которые опирается ответ; без второго —
        # не отличил бы подтверждённое отчётом от неподтверждённого.
        "lookups": list(answer.lookups),
        "check": {
            "total": len(answer.check.claims),
            "unverified": [
                {"number": c.number, "context": c.context}
                for c in answer.check.claims
                if not c.found
            ],
            "checked": answer.check.checked,
        },
    }

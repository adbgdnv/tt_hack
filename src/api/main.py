"""HTTP-сервис: веб-интерфейс ходит сюда.

Тонкая обёртка над `core`. Бизнес-логики здесь нет и быть не должно — только разбор
запроса, вызов ядра и формирование ответа. Проверка границы: удалить src/mcp_server —
этот сервис продолжит работать.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core import repo, slim


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
    """Вход продукта — «ИНН или поисковый запрос» (слова кейсодателя)."""

    message: str
    session_id: str | None = None


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


@app.post("/chat")
def chat(request: ChatRequest) -> dict:
    """Диалог с агентом. Память — в рамках одной сессии, между сессиями не храним."""
    raise NotImplementedError

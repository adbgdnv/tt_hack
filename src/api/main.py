"""HTTP-сервис: веб-интерфейс ходит сюда.

Тонкая обёртка над `core`. Бизнес-логики здесь нет и быть не должно — только разбор
запроса, вызов ядра и формирование ответа. Проверка границы: удалить src/mcp_server —
этот сервис продолжит работать.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core import mocks, slim

app = FastAPI(title="Проверка контрагента", version="0.1.0")

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
    """Проверка живости для compose и CI."""
    return {"status": "ok"}


@app.get("/counterparties/search")
def search(q: str, limit: int = 10) -> list[dict]:
    """Поиск по названию или ИНН."""
    return [slim.slim(r) for r in mocks.search(q, limit)]


@app.get("/counterparties/{inn}")
def get_counterparty(inn: str) -> dict:
    """Отобранный отчёт по ИНН."""
    report = mocks.by_inn(inn)
    if report is None:
        raise HTTPException(status_code=404, detail="Контрагент не найден в выгрузке")
    return slim.slim(report)


@app.post("/chat")
def chat(request: ChatRequest) -> dict:
    """Диалог с агентом. Память — в рамках одной сессии, между сессиями не храним."""
    raise NotImplementedError

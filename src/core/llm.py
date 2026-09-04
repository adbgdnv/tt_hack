"""Клиент LLM-провайдера. OpenAI-совместимый, поэтому смена провайдера —
это смена LLM_BASE_URL и ключа, без единой правки кода.

Два подводных камня, проверенных на живом API:

1. Без заголовка User-Agent Cloudflare перед Groq отдаёт 403. curl подставляет свой
   автоматически, поэтому из терминала работает, а из Python — нет.
2. gpt-oss возвращает поле `reasoning` рядом с `content`. Пользователю его не
   показываем, но в бюджет токенов закладываем: при max_tokens=20 рассуждение съедает
   весь лимит и content приходит пустым.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import httpx
from langsmith import get_current_run_tree, traceable
from langsmith import utils as langsmith_utils

from core.config import load_env

USER_AGENT = "counterparty-checker/0.1"


def _environment() -> str:
    """Откуда сделан вызов. Отдельной переменной не заводим: различие уже выражено
    префиксом сервиса — на сервере он задан, локально пуст."""
    return "server" if os.environ.get("API_ROOT_PATH") else "local"

def _report_usage(usage: dict) -> None:
    """Отдать счётчик токенов трассировке.

    Сам по себе он в неё не попадает: наблюдатель ищет `usage_metadata` в корне
    результата, а результат у нас — объект `Answer`, и счётчики оказываются на
    уровень глубже. Без этого записи приходят с нулями, то есть расход по проекту
    посчитать нельзя.

    Вне трассировки дерева вызовов нет — тогда просто выходим.
    """
    tree = get_current_run_tree()
    if tree is None:
        return
    prompt = usage.get("prompt_tokens", 0)
    completion = usage.get("completion_tokens", 0)
    tree.metadata["usage_metadata"] = {
        "input_tokens": prompt,
        "output_tokens": completion,
        "total_tokens": usage.get("total_tokens", prompt + completion),
    }


PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-20b"),
    "openrouter": ("https://openrouter.ai/api/v1", "openai/gpt-oss-20b"),
}


@dataclass
class Answer:
    """Ответ модели. `reasoning` держим отдельно и наружу не отдаём."""

    content: str
    reasoning: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""


@dataclass
class LLMClient:
    base_url: str = field(default="")
    model: str = field(default="")
    api_key: str = field(default="")
    timeout: float = 90.0

    def __post_init__(self) -> None:
        load_env()
        provider = os.environ.get("LLM_PROVIDER", "groq")
        default_url, default_model = PROVIDERS.get(provider, PROVIDERS["groq"])
        self.base_url = self.base_url or os.environ.get("LLM_BASE_URL", default_url)
        self.model = self.model or os.environ.get("LLM_MODEL", default_model)
        self.api_key = self.api_key or os.environ.get("LLM_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("Нет LLM_API_KEY — задать в .env или в окружении")

    def ask(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 1200,
        temperature: float = 0.2,
        inn: str | None = None,
    ) -> Answer:
        """Вызов модели, при включённой трассировке — с записью в LangSmith.

        Трассировка не может стать причиной отказа. Поэтому оборачивается только
        её настройка: если она не удалась, вызов идёт напрямую. Оборачивать сам
        вызов в try нельзя — упавшую модель это превратило бы в повторный запрос,
        а пользователь получил бы поведение, которого не просил.
        """
        call = self._call
        if langsmith_utils.tracing_is_enabled():
            try:
                call = traceable(
                    run_type="llm",
                    name="counterparty-chat",
                    metadata={
                        "environment": _environment(),
                        "inn": inn,
                        "model": self.model,
                    },
                )(self._call)
            except Exception:  # noqa: BLE001 — наблюдение не ломает продукт
                call = self._call
        return call(messages, max_tokens, temperature)

    def _call(self, messages: list[dict], max_tokens: int, temperature: float) -> Answer:
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,  # без него Cloudflare отдаёт 403
            },
            content=json.dumps(
                {
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
            ),
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        message = data["choices"][0]["message"]
        usage = data.get("usage", {})
        _report_usage(usage)
        return Answer(
            content=(message.get("content") or "").strip(),
            reasoning=message.get("reasoning") or "",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            model=data.get("model", self.model),
        )

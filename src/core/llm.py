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

from core.config import load_env

USER_AGENT = "counterparty-checker/0.1"

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
    ) -> Answer:
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
        return Answer(
            content=(message.get("content") or "").strip(),
            reasoning=message.get("reasoning") or "",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            model=data.get("model", self.model),
        )

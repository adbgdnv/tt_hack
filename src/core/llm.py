"""Клиент LLM-провайдера. OpenAI-совместимый, поэтому смена провайдера —
это смена LLM_BASE_URL и ключа, без единой правки кода.

Работаем через `ChatOpenAI` из LangChain, а не через голый HTTP. Причина одна:
трассировка. Наблюдение встроено в клиент LangChain и включается наличием ключа —
ни декораторов, ни ручного перекладывания счётчиков. Своя реализация на httpx
требовала и того, и другого, причём токены приходили нулями, пока их не начали
класть в запись вручную.

Побочная выгода: рассуждение gpt-oss попадает в запись отдельной строкой
(`output_token_details.reasoning`) — при разборе пустых ответов видно, съело ли
его рассуждение.

Подводный камень, проверенный на живом API: без заголовка User-Agent Cloudflare
перед Groq отдаёт 403. curl подставляет свой автоматически, поэтому из терминала
работает, а из Python — нет.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from langchain_openai import ChatOpenAI

from core.config import load_env

USER_AGENT = "counterparty-checker/0.1"

PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-20b"),
    "openrouter": ("https://openrouter.ai/api/v1", "openai/gpt-oss-20b"),
}


def _environment() -> str:
    """Откуда сделан вызов. Отдельной переменной не заводим: различие уже выражено
    префиксом сервиса — на сервере он задан, локально пуст."""
    return "server" if os.environ.get("API_ROOT_PATH") else "local"


@dataclass
class Answer:
    """Ответ модели. Счётчики токенов держим рядом: по ним видно, съело ли бюджет
    рассуждение gpt-oss, из-за которого content приходит пустым."""

    content: str
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

    def _chat(self, max_tokens: int, temperature: float) -> ChatOpenAI:
        return ChatOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=self.timeout,
            max_retries=0,  # повтор решает вызывающий: тихий ретрай съедает время молча
            default_headers={"User-Agent": USER_AGENT},  # без него Cloudflare отдаёт 403
        )

    def ask(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 1200,
        temperature: float = 0.2,
        inn: str | None = None,
    ) -> Answer:
        """Вызов модели. При заданном ключе LangSmith запись создаётся сама.

        `inn` и окружение уходят в запись метаданными: без них записи неразличимы —
        непонятно, о какой компании речь и пришёл ли вызов с сервера или с ноутбука.
        """
        message = self._chat(max_tokens, temperature).invoke(
            messages,
            config={
                "run_name": "counterparty-chat",
                "metadata": {"environment": _environment(), "inn": inn},
            },
        )
        usage = message.usage_metadata or {}
        return Answer(
            content=(message.text or "").strip(),
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            model=message.response_metadata.get("model_name", self.model),
        )

"""Клиент LLM-провайдера. OpenAI-совместимый, поэтому смена провайдера —
это смена адреса и ключа, без единой правки кода.

Работаем через `ChatOpenAI` из LangChain, а не через голый HTTP. Причина одна:
трассировка. Наблюдение встроено в клиент LangChain и включается наличием ключа —
ни декораторов, ни ручного перекладывания счётчиков. Своя реализация на httpx
требовала и того, и другого, причём токены приходили нулями, пока их не начали
класть в запись вручную.

Путей отхода три, и это не дублирование, а страховка. Работаем на OpenRouter
моделями, которые назвал кейсодатель: `deepseek v4 flash` основной,
`glm 5.3 flash` запасной — вторая модель закрывает отказ первой, а не отказ
провайдера. Последним стоит Groq с бесплатным gpt-oss: он слабее и упирается
в 8 000 токенов в минуту, поэтому под него ничего не подгоняется — он нужен
ровно на случай, когда не осталось ничего другого. Отказ не должен доходить
до пользователя ошибкой: он приходит за разбором, а не за отчётом о нашей
инфраструктуре.

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


@dataclass(frozen=True)
class Provider:
    """Куда ходить, чем и на каких условиях."""

    name: str
    base_url: str
    model: str
    key_env: str
    # Глубина рассуждения. Задаётся только там, где параметр понимают: у gpt-oss
    # на Groq рассуждение тратится из того же бюджета выхода, и без ограничения
    # оно съедает ответ целиком. У моделей OpenRouter параметра нет, и посылать
    # его туда нельзя — провайдер отвечает ошибкой на неизвестное поле.
    reasoning: str | None = None


PROVIDERS = {
    "openrouter": Provider(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        model="deepseek/deepseek-v4-flash",
        key_env="OPENROUTER_API_KEY",
    ),
    "groq": Provider(
        name="groq",
        base_url="https://api.groq.com/openai/v1",
        model="openai/gpt-oss-20b",
        key_env="GROQ_API_KEY",
        reasoning="low",
    ),
}

PRIMARY = "openrouter"


@dataclass(frozen=True)
class Route:
    """Куда пойти за ответом. Пара «провайдер и модель», а не один провайдер:
    отказ модели и отказ провайдера — разные события, и первое лечится сменой
    модели у того же провайдера, что дешевле и быстрее."""

    provider: str
    model: str = ""


# Порядок отхода. Обе модели OpenRouter названы кейсодателем; замерено на полной
# сырой записи (29 000 токенов входа): deepseek 4,7 с, glm 7,1 с, $10 хватает
# на ~4 000 прогонов. Groq стоит последним и намеренно: он слабее, и подгонять
# под его минутную квоту продукт больше не нужно.
ОТХОД = (
    Route("openrouter", "deepseek/deepseek-v4-flash"),
    Route("openrouter", "z-ai/glm-5.3-flash"),
    Route("groq"),
)


def environment() -> str:
    """Откуда сделан вызов. Отдельной переменной не заводим: различие уже выражено
    префиксом сервиса — на сервере он задан, локально пуст."""
    return "server" if os.environ.get("API_ROOT_PATH") else "local"


def key_for(name: str) -> str:
    """Ключ провайдера — только именной.

    У каждого провайдера свой: `OPENROUTER_API_KEY`, `GROQ_API_KEY`. Поэтому
    настроены они одновременно, и это условие запасного пути.

    Общий `LLM_API_KEY` больше не принимается, хотя раньше принимался. Он был
    заряженным ружьём: в нём лежал ключ Groq, и стоило пропасть именному ключу
    OpenRouter, как продукт молча переезжал на gpt-oss — без ошибки, без записи
    в логе, с одним лишь падением качества ответов. Теперь пропавший ключ —
    честная ошибка при старте, а не тихая подмена модели.
    """
    load_env()
    провайдер = PROVIDERS.get(name)
    return os.environ.get(провайдер.key_env, "") if провайдер else ""


def chain() -> tuple[Route, ...]:
    """Пути по порядку: основной, затем запасные. Только настроенные.

    Первым идёт провайдер из `LLM_PROVIDER`, чтобы переключение не требовало
    правки кода. Ненастроенный путь выпадает: попытка сходить по нему стоила бы
    времени ответа и всё равно закончилась бы ошибкой.
    """
    load_env()
    основной = os.environ.get("LLM_PROVIDER", PRIMARY)
    порядок = sorted(ОТХОД, key=lambda r: r.provider != основной)
    return tuple(r for r in порядок if r.provider in PROVIDERS and key_for(r.provider))


@dataclass
class Answer:
    """Ответ модели. Счётчики токенов держим рядом: по ним видно, съело ли бюджет
    рассуждение, из-за которого content приходит пустым."""

    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""


@dataclass
class LLMClient:
    """Клиент одного провайдера. Без имени берётся первый настроенный."""

    provider: str = field(default="")
    base_url: str = field(default="")
    model: str = field(default="")
    api_key: str = field(default="")
    timeout: float = 90.0

    def __post_init__(self) -> None:
        load_env()
        доступные = chain()
        первый = доступные[0] if доступные else Route(PRIMARY)
        self.provider = self.provider or первый.provider
        self.model = self.model or (первый.model if self.provider == первый.provider else "")
        провайдер = PROVIDERS.get(self.provider) or PROVIDERS[PRIMARY]
        # Переопределения адреса и модели относятся к провайдеру из настройки:
        # применять их к запасному значит подсунуть ему чужую модель.
        свой = os.environ.get("LLM_PROVIDER", PRIMARY) == self.provider
        self.base_url = self.base_url or (
            (свой and os.environ.get("LLM_BASE_URL")) or провайдер.base_url
        )
        self.model = self.model or ((свой and os.environ.get("LLM_MODEL")) or провайдер.model)
        self.api_key = self.api_key or key_for(self.provider)
        self.reasoning = провайдер.reasoning
        if not self.api_key:
            raise RuntimeError(
                f"Нет ключа для провайдера «{self.provider}» — "
                f"задать {провайдер.key_env} в .env или в окружении"
            )

    def chat(
        self,
        max_tokens: int = 1200,
        temperature: float = 0.2,
        reasoning_effort: str | None = "",
    ) -> ChatOpenAI:
        """Настроенный клиент модели.

        Публичный, потому что вызывающих двое: непотоковый `ask` здесь же
        и сборка агента в приложении.

        Пустая строка в `reasoning_effort` значит «как принято у провайдера»:
        у gpt-oss на Groq — `low`, иначе параметр не посылается вовсе. Явный
        `None` глушит его и там, где он есть.
        """
        глубина = self.reasoning if reasoning_effort == "" else reasoning_effort
        extra = {"reasoning_effort": глубина} if глубина else {}
        return ChatOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=self.timeout,
            max_retries=0,  # повтор решает вызывающий: тихий ретрай съедает время молча
            default_headers={"User-Agent": USER_AGENT},  # без него Cloudflare отдаёт 403
            **extra,
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
        message = self.chat(max_tokens, temperature).invoke(
            messages,
            config={
                "run_name": "counterparty-chat",
                "metadata": {
                    "environment": environment(),
                    "inn": inn,
                    "provider": self.provider,
                },
            },
        )
        usage = message.usage_metadata or {}
        return Answer(
            content=(message.text or "").strip(),
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            model=message.response_metadata.get("model_name", self.model),
        )

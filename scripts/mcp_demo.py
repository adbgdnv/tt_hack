"""Прогон MCP-сервера настоящим клиентом — так, как это делает чужой агент.

`scripts/mcp_probe.sh` отвечает на вопрос «жив ли сервер». Этот скрипт
отвечает на другой: «что увидит агент, который к нему подключился».
Полезен на защите: показывает выхлоп инструментов без клиента и без модели.

    python3 scripts/mcp_demo.py                     сервер на localhost:8001
    python3 scripts/mcp_demo.py http://адрес/mcp    другой адрес
"""

from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

АДРЕС = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001/mcp"

# Опорный пример кейса: обе оценки зелёные при 2,6 млрд ₽ исков, 54 активных
# производствах и открытом конкурсном производстве.
МАКСМАРКЕТ = "5032257375"
ПУЛ = ["9714079997", МАКСМАРКЕТ, "7704310756"]


def разобрать(ответ) -> dict:
    """Тело ответа инструмента. MCP отдаёт его текстом — это часть протокола."""
    return json.loads(ответ.content[0].text)


async def main() -> None:
    async with streamablehttp_client(АДРЕС) as (чтение, запись, _):
        async with ClientSession(чтение, запись) as сессия:
            await сессия.initialize()

            имена = [т.name for т in (await сессия.list_tools()).tools]
            print(f"Инструментов: {len(имена)}")
            for имя in имена:
                print("  •", имя)

            print("\n── Что не сходится ──")
            данные = разобрать(await сессия.call_tool("find_contradictions", {"inn": МАКСМАРКЕТ}))
            print(данные["name"])
            for п in данные["contradictions"]:
                print(f"  • {п['title']}")
                for значение in п["evidence"]:
                    print(f"      {значение}")

            print("\n── С кем осторожнее ──")
            данные = разобрать(await сессия.call_tool("compare_counterparties", {"inns": ПУЛ}))
            print(f"{данные['summary']['headline']}. {данные['summary']['detail']}")
            for в in данные["verdicts"]:
                print(f"  {в['recommendation']:12} {в['name']}")
                for причина in в["reasons"][:2]:
                    print(f"               {причина}")

            print("\n── Проверка чисел ──")
            текст = "У МАКСМАРКЕТ выручка 116 257 852 000 ₽ и 900 судебных дел."
            данные = разобрать(
                await сессия.call_tool("verify_claims", {"text": текст, "inns": [МАКСМАРКЕТ]})
            )
            print(f"«{текст}»")
            print(f"  подтверждено {данные['confirmed']} из {данные['total']}")
            for c in данные["unverified"]:
                print(f"  в отчётах нет: {c['number']}")

            print("\n── Тема, которой нет в отчёте ──")
            данные = разобрать(
                await сессия.call_tool("look_up", {"inn": МАКСМАРКЕТ, "topic": "налоги"})
            )
            print(данные["text"].strip())


if __name__ == "__main__":
    asyncio.run(main())

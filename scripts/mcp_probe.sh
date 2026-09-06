#!/bin/bash
# Проверка живости MCP-сервера: рукопожатие, список инструментов, один вызов.
#
# Вызов обязателен, а не для полноты. Сервер поднимается и без набора данных —
# `repo.load` читается лениво, при первом обращении. Без вызова инструмента
# «сервер отвечает» означало бы только «процесс запущен», а показать он мог бы
# пустоту у всех компаний.
#
# Рукопожатие тоже обязательно: streamable-http требует сессию, и tools/list
# без неё отвечает «Missing session ID» — 400, неотличимый от поломки.
#
# Имена переменных латиницей: bash кириллические не принимает.
#
#   scripts/mcp_probe.sh [адрес]        по умолчанию localhost:8001
set -euo pipefail

BASE="${1:-localhost:8001}/mcp"
HDR=(-H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream')

SESSION=$(curl -fsS -m 5 -D - -o /dev/null -X POST "${BASE}" "${HDR[@]}" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}' \
  | tr -d '\r' | awk -F': ' '/^mcp-session-id/ {print $2}')

if [ -z "${SESSION}" ]; then
  echo "нет сессии — сервер не отвечает по MCP" >&2
  exit 1
fi

curl -fsS -m 5 -o /dev/null -X POST "${BASE}" "${HDR[@]}" \
  -H "mcp-session-id: ${SESSION}" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}'

TOOLS=$(curl -fsS -m 5 -X POST "${BASE}" "${HDR[@]}" \
  -H "mcp-session-id: ${SESSION}" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}')

for name in search_counterparty get_counterparty_report assess_risk find_contradictions \
            compare_counterparties get_financials look_up verify_claims; do
  echo "${TOOLS}" | grep -q "\"${name}\"" || { echo "нет инструмента ${name}" >&2; exit 1; }
done

# Опорный пример: у МАКСМАРКЕТ обе оценки зелёные при тяжёлых открытых данных.
# Без подключённого набора противоречий не найдётся ни одного.
ANSWER=$(curl -fsS -m 10 -X POST "${BASE}" "${HDR[@]}" \
  -H "mcp-session-id: ${SESSION}" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"find_contradictions","arguments":{"inn":"5032257375"}}}')

echo "${ANSWER}" | grep -q "МАКСМАРКЕТ" || {
  echo "инструмент ответил, но набора в нём нет" >&2
  echo "${ANSWER}" | head -c 300 >&2
  exit 1
}

echo "MCP жив: 8 инструментов, набор подключён"

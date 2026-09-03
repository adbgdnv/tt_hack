#!/usr/bin/env bash
# Smoke-check превью: каждая обязательная страница должна отвечать 200 (FR-006).
# Переиспользуется preview_deploy.sh, preview_rollback.sh, CI и запускается руками.
#
#   preview_smoke.sh <base-url> [path ...]
#
# Пути по умолчанию: / /report.html /mcp.html
# Basic Auth — из env PREVIEW_BASIC_AUTH (user:password) или ~/.preview-smoke-auth.
# Полный URL с логином/паролем не печатается (FR-014).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/preview_common.sh
. "${SCRIPT_DIR}/preview_common.sh"

usage() { echo "usage: preview_smoke.sh <base-url> [path ...]" >&2; exit 2; }

[ $# -ge 1 ] || usage
base="${1%/}"; shift

paths=("$@")
if [ "${#paths[@]}" -eq 0 ]; then
  paths=(/ /report.html /mcp.html)
fi

auth=()
if [ -n "${PREVIEW_BASIC_AUTH:-}" ]; then
  auth=(-u "${PREVIEW_BASIC_AUTH}")
else
  warn "PREVIEW_BASIC_AUTH не задан — smoke пойдёт без авторизации"
fi

failed=()
for p in "${paths[@]}"; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 ${auth[@]+"${auth[@]}"} "${base}${p}" || echo 000)"
  printf '%s %s\n' "${code}" "${p}"
  [ "${code}" = "200" ] || failed+=("${p}=${code}")
done

if [ "${#failed[@]}" -ne 0 ]; then
  echo "smoke failed: ${failed[*]}" >&2
  exit 1
fi
echo "smoke ok: ${#paths[@]} путей"

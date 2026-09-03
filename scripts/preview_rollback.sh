#!/usr/bin/env bash
# Быстрый ручной откат превью на предыдущий релиз (US3, FR-011).
#
#   scripts/preview_rollback.sh [--local] [--to <RELEASE_ID>] [--list]
#
# --list         показать релизы и текущий, ничего не менять
# --to <ID>      откатить на конкретный релиз вместо «предыдущего по времени»
# --local        пометка для симметрии с preview_deploy.sh (работа всегда локальная)
#
# Переключение симлинка — атомарное, занимает миллисекунды (цель SC-004: < 2 мин
# от решения до рабочего превью). Автоматически назад НЕ откатывает.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/preview_common.sh
. "${SCRIPT_DIR}/preview_common.sh"

TO_ID=""
DO_LIST=0

while [ $# -gt 0 ]; do
  case "$1" in
    --to)     shift; TO_ID="${1:-}" ;;
    --list)   DO_LIST=1 ;;
    --local)  : ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)        die "неизвестный аргумент: $1" 2 ;;
  esac
  shift
done

cur="$(current_release)"

if [ "${DO_LIST}" -eq 1 ]; then
  echo "релизы (новые сверху), * — текущий:"
  while IFS= read -r d; do
    [ -n "${d}" ] || continue
    name="$(basename "${d}")"
    if [ "${name}" = "${cur}" ]; then echo "  * ${name}"; else echo "    ${name}"; fi
  done < <(ls -1dt "${RELEASES_DIR}"/*/ 2>/dev/null)
  exit 0
fi

acquire_lock

if [ -n "${TO_ID}" ]; then
  target="${RELEASES_DIR}/${TO_ID}"
  [ -d "${target}" ] || die "нет релиза ${TO_ID}" 2
  [ "${TO_ID}" = "${cur}" ] && die "релиз ${TO_ID} и так текущий" 0
else
  target="$(find_previous_release || true)"
  [ -n "${target}" ] || die "откатываться не на что: в ${RELEASES_DIR} нет предыдущего релиза" 3
fi

atomic_switch "${target}"
log "rolled back ${cur:-<none>} → $(basename "${target}")"

if run_smoke; then
  log "откат ок"
else
  warn "предыдущий релиз тоже не отвечает 200 — назад не откатываю, разбирайтесь вручную"
  exit 1
fi

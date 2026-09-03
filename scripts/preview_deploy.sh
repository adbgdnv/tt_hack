#!/usr/bin/env bash
# Выкладка превью на общий сервер.
#
#   scripts/preview_deploy.sh                 # режим CI: собрать → доставить релиз и bin/ на сервер → финализировать по ssh
#   scripts/preview_deploy.sh --local         # на сервере из git-клона: собрать → положить релиз → переключить → smoke → prune
#   scripts/preview_deploy.sh --finalize <ID> # на сервере из PREVIEW_ROOT/bin: переключить на releases/<ID> → smoke → prune (вызывается по ssh из CI)
#
# Флаги: --dry-run (план без изменений), --no-web (пропустить сборку src/web).
#
# env (режим CI): DEPLOY_HOST, DEPLOY_USER (ключ и known_hosts уже в ~/.ssh).
# env (сервер):   PREVIEW_BASIC_AUTH или ~/.preview-smoke-auth.
# Опционально:    PREVIEW_ROOT, PREVIEW_BASE_URL, KEEP_RELEASES, SMOKE_PATHS.
#
# Скрипт оперирует только путями под PREVIEW_ROOT: не перезапускает сервисы, не
# трогает контейнеры приложений и соседний каталог данных ревью (FR-005).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/preview_common.sh
. "${SCRIPT_DIR}/preview_common.sh"

MODE="ci"
DRY_RUN=0
NO_WEB=0
FINALIZE_ID=""

while [ $# -gt 0 ]; do
  case "$1" in
    --local)       MODE="local" ;;
    --finalize)    MODE="finalize"; shift; FINALIZE_ID="${1:-}" ;;
    --dry-run)     DRY_RUN=1 ;;
    --no-web)      NO_WEB=1 ;;
    -h|--help)     grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)             die "неизвестный аргумент: $1" 2 ;;
  esac
  shift
done

# ---------------------------------------------------------------------------
# Сборка staging-каталога: src/web/dist (если есть) + preview/ (preview выигрывает коллизию)
# ---------------------------------------------------------------------------
build_staging() {
  local staging="$1" web="skipped"

  if [ "${NO_WEB}" -eq 0 ] && [ -f "${REPO_DIR}/src/web/package.json" ]; then
    log "src/web: сборка (npm ci && npm run build)"
    ( cd "${REPO_DIR}/src/web" && npm ci --no-audit --no-fund && npm run build )
    [ -d "${REPO_DIR}/src/web/dist" ] || die "src/web: сборка не дала dist/"
    rsync -a "${REPO_DIR}/src/web/dist/" "${staging}/"
    web="built"
  else
    log "src/web: пропуск (нет package.json или --no-web)"
  fi

  # preview/ поверх, без перезаписи уже положенного фронтом
  cp -Rn "${REPO_DIR}/preview/." "${staging}/" 2>/dev/null || cp -R "${REPO_DIR}/preview/." "${staging}/"

  local sha branch
  sha="$(git -C "${REPO_DIR}" rev-parse HEAD 2>/dev/null || echo nogit)"
  branch="$(git -C "${REPO_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
  cat > "${staging}/RELEASE" <<EOF
sha=${sha}
branch=${branch}
built_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
web=${web}
EOF
  echo "${web}"
}

# ---------------------------------------------------------------------------
# Финализация на сервере: переключить симлинк, smoke, при провале — откат (FR-007b)
# ---------------------------------------------------------------------------
finalize() {
  local release_dir="$1"
  assert_safe_path "${release_dir}"
  [ -d "${release_dir}" ] || die "finalize: нет релиза ${release_dir}"

  local previous
  previous="$(find_previous_release || true)"

  log "контур: preview (main); релиз: $(basename "${release_dir}")"
  atomic_switch "${release_dir}"
  log "переключено на $(basename "${release_dir}")"

  if run_smoke; then
    prune_releases "${KEEP_RELEASES}"
    log "deployed $(basename "${release_dir}")"
  else
    if [ -n "${previous}" ]; then
      atomic_switch "${previous}"
      die "smoke провален — откат на $(basename "${previous}"); релиз $(basename "${release_dir}") оставлен в releases/"
    else
      die "smoke провален, откатываться не на что — симлинк указывает на $(basename "${release_dir}")"
    fi
  fi
}

# ---------------------------------------------------------------------------
# Режимы
# ---------------------------------------------------------------------------
case "${MODE}" in
  finalize)
    [ -n "${FINALIZE_ID}" ] || die "--finalize требует ID релиза" 2
    acquire_lock
    finalize "${RELEASES_DIR}/${FINALIZE_ID}"
    ;;

  local)
    command -v flock >/dev/null || die "нет flock (это Linux-сервер?)"
    acquire_lock
    STAGING="$(mktemp -d)"
    trap 'rm -rf "${STAGING}"' EXIT
    WEB="$(build_staging "${STAGING}")"
    RID="$(release_id)"
    if [ "${DRY_RUN}" -eq 1 ]; then
      log "[dry-run] релиз ${RID}, web=${WEB}, цель ${RELEASES_DIR}/${RID}"
      find "${STAGING}" -maxdepth 1 -mindepth 1 -printf '  %f\n'
      exit 0
    fi
    mkdir -p "${RELEASES_DIR}/${RID}"
    rsync -a --delete "${STAGING}/" "${RELEASES_DIR}/${RID}/"
    log "релиз ${RID} доставлен (web=${WEB})"
    finalize "${RELEASES_DIR}/${RID}"
    ;;

  ci)
    : "${DEPLOY_HOST:?нужен DEPLOY_HOST}"
    : "${DEPLOY_USER:?нужен DEPLOY_USER}"
    STAGING="$(mktemp -d)"
    trap 'rm -rf "${STAGING}"' EXIT
    WEB="$(build_staging "${STAGING}")"
    RID="$(release_id)"
    TARGET="${DEPLOY_USER}@${DEPLOY_HOST}"

    if [ "${DRY_RUN}" -eq 1 ]; then
      log "[dry-run] релиз ${RID}, web=${WEB} → ${TARGET}:${RELEASES_DIR}/${RID}"
      exit 0
    fi

    rsync -az --delete \
      --rsync-path="mkdir -p ${RELEASES_DIR}/${RID} && rsync" \
      "${STAGING}/" "${TARGET}:${RELEASES_DIR}/${RID}/"
    log "релиз ${RID} доставлен на ${DEPLOY_HOST} (web=${WEB})"

    # Доставить свежие скрипты в PREVIEW_ROOT/bin — финализация запускается оттуда,
    # никакого git-клона на сервере для автодеплоя не требуется.
    rsync -az \
      --rsync-path="mkdir -p ${BIN_DIR} && rsync" \
      "${SCRIPT_DIR}/preview_common.sh" "${SCRIPT_DIR}/preview_smoke.sh" \
      "${SCRIPT_DIR}/preview_deploy.sh" "${SCRIPT_DIR}/preview_rollback.sh" \
      "${TARGET}:${BIN_DIR}/"

    # shellcheck disable=SC2029
    ssh "${TARGET}" "PREVIEW_ROOT=${PREVIEW_ROOT} KEEP_RELEASES=${KEEP_RELEASES} \
      ${BIN_DIR}/preview_deploy.sh --finalize ${RID}"
    log "deployed ${RID}"
    ;;

  *) die "неизвестный режим ${MODE}" ;;
esac

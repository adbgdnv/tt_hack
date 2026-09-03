#!/usr/bin/env bash
# Общие функции для preview_deploy.sh / preview_rollback.sh / preview_smoke.sh.
#
# Рассчитано на bash 4+ и GNU coreutils (раннер ubuntu-latest, сервер Ubuntu).
# `mv -T`, `ls -t`, `flock` — GNU/Linux; на macOS скрипты не запускаются, цель — Linux.
#
# Этот файл ничего не делает при source — только определения. Соседний каталог
# данных ревью, перезапуск сервисов и контейнеры приложений автодеплой не трогает
# (FR-005) — все операции ограничены путями под PREVIEW_ROOT.

# --- Пути. Всё, что делают скрипты, лежит строго под PREVIEW_ROOT. --------------
: "${PREVIEW_ROOT:=/opt/tt-hack}"
RELEASES_DIR="${PREVIEW_ROOT}/releases"
CURRENT_LINK="${PREVIEW_ROOT}/preview"
LOCK_FILE="${PREVIEW_ROOT}/.deploy.lock"
: "${KEEP_RELEASES:=5}"
: "${PREVIEW_BASE_URL:=https://tt-hack-review.72.56.16.44.sslip.io}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Логин:пароль Basic Auth для smoke-check. В CI не передаётся — живёт на сервере
# в ~/.preview-smoke-auth (chmod 600), рядом с тем же htpasswd, что у Nginx.
if [ -z "${PREVIEW_BASIC_AUTH:-}" ] && [ -r "${HOME}/.preview-smoke-auth" ]; then
  PREVIEW_BASIC_AUTH="$(cat "${HOME}/.preview-smoke-auth")"
fi

# --- Логи (без секретов) ------------------------------------------------------
log()  { printf '%s %s\n' "$(date -u +%H:%M:%S)" "$*"; }
warn() { printf '%s WARN %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
die()  { printf '%s ERROR %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; exit "${2:-1}"; }

# --- Защита от выхода за пределы разрешённых путей (FR-005) --------------------
assert_safe_path() {
  case "$1" in
    "${RELEASES_DIR}"/* | "${CURRENT_LINK}" | "${CURRENT_LINK}.tmp" | "${LOCK_FILE}") : ;;
    *) die "путь вне разрешённой зоны автодеплоя: $1" ;;
  esac
}

# --- Лок: держится до конца жизни процесса (fd 9 закроется на exit) -----------
acquire_lock() {
  mkdir -p "${PREVIEW_ROOT}" 2>/dev/null || true
  exec 9>"${LOCK_FILE}" || die "не открыть lock ${LOCK_FILE}"
  if ! flock -n 9; then
    die "другая выкладка уже идёт (${LOCK_FILE}) — попробуйте позже" 1
  fi
}

# --- Идентификатор релиза: UTC-таймстамп + короткий sha ----------------------
release_id() {
  local sha
  sha="$(git -C "${REPO_DIR}" rev-parse --short=7 HEAD 2>/dev/null || echo nogit)"
  printf '%s-%s' "$(date -u +%Y%m%dT%H%M%SZ)" "${sha}"
}

# --- Имя каталога, на который сейчас указывает симлинк ----------------------
current_release() {
  local t
  t="$(readlink "${CURRENT_LINK}" 2>/dev/null)" || return 0
  basename "${t}"
}

# --- Атомарное переключение симлинка на каталог релиза (FR-007a) -------------
atomic_switch() {
  local target="$1"
  assert_safe_path "${target}"
  [ -d "${target}" ] || die "atomic_switch: нет каталога ${target}"
  ln -sfn "${target}" "${CURRENT_LINK}.tmp"
  mv -T "${CURRENT_LINK}.tmp" "${CURRENT_LINK}"
}

# --- Самый свежий релиз в releases/, не совпадающий с текущим ----------------
find_previous_release() {
  local cur name d
  cur="$(current_release)"
  while IFS= read -r d; do
    [ -n "${d}" ] || continue
    name="$(basename "${d}")"
    [ "${name}" = "${cur}" ] && continue
    printf '%s' "${d%/}"
    return 0
  done < <(ls -1dt "${RELEASES_DIR}"/*/ 2>/dev/null)
  return 1
}

# --- Оставить KEEP_RELEASES новейших релизов (текущий не трогаем никогда) ----
prune_releases() {
  local keep="${1:-${KEEP_RELEASES}}"
  local cur name d i=0
  cur="$(current_release)"
  while IFS= read -r d; do
    [ -n "${d}" ] || continue
    name="$(basename "${d}")"
    [ "${name}" = "${cur}" ] && continue
    i=$((i + 1))
    if [ "${i}" -ge "${keep}" ]; then
      assert_safe_path "${d%/}"
      rm -rf "${d}"
      log "удалён старый релиз ${name}"
    fi
  done < <(ls -1dt "${RELEASES_DIR}"/*/ 2>/dev/null)
}

# --- Прогон smoke-check по опубликованному адресу ---------------------------
run_smoke() {
  "${SCRIPT_DIR}/preview_smoke.sh" "${PREVIEW_BASE_URL}"
}

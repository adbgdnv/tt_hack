# Контракт: bash-скрипты

Все три — POSIX bash, `set -euo pipefail`, `shellcheck`-чистые. Живут в `scripts/`.
Идентично исполняются на раннере (через ssh) и на сервере (напрямую) — это и есть «ручной
запуск = запасной путь» (FR-010).

---

## `scripts/preview_deploy.sh`

**Назначение:** собрать набор превью, доставить в новый релиз, проверить, переключить.

**Вход (env):**

| Переменная | Обяз. | Смысл |
|---|---|---|
| `DEPLOY_HOST` | да (в CI) | сервер; при запуске *на* сервере — `localhost`, тогда rsync локальный |
| `DEPLOY_USER` | да (в CI) | `ttdeploy` |
| `PREVIEW_BASIC_AUTH` | да | `user:password` для smoke-check |
| `PREVIEW_BASE_URL` | нет | по умолчанию `https://tt-hack-review.72.56.16.44.sslip.io` |
| `SMOKE_PATHS` | нет | по умолчанию `/ /report.html /mcp.html` |
| `KEEP_RELEASES` | нет | по умолчанию `5` |

**Флаги:** `--dry-run` (показать план, ничего не менять), `--no-web` (пропустить сборку явно),
`--local` (rsync без ssh, для запуска на сервере).

**Шаги:**
1. `flock` на `/opt/tt-hack/.deploy.lock` (или локальный лок при `--local`).
2. Если `src/web/package.json` есть и не `--no-web`: `cd src/web && npm ci && npm run build`
   → ожидаем `src/web/dist/`. Иначе печатаем `web: skipped`.
3. Собрать staging-каталог: скопировать `preview/`, затем поверх — `src/web/dist/` (при
   коллизии имя из `preview/` выигрывает — `rsync` порядок: web первым, preview вторым без
   `--delete`... **уточнение:** web первым в staging, preview вторым тоже без перезаписи ⇒
   реализовать `cp -rn preview/* staging/` после web). Записать `RELEASE`.
4. `RELEASE_ID=$(date -u +%Y%m%dT%H%M%SZ)-<short-sha>`.
5. rsync staging → `DEPLOY_USER@DEPLOY_HOST:/opt/tt-hack/releases/$RELEASE_ID/` (или локально).
6. `preview_smoke.sh "$PREVIEW_BASE_URL"` — но релиз ещё не текущий ⇒ **по R5-компромиссу:**
   сначала switch, потом smoke; при провале smoke → `preview_rollback.sh` и `exit 1`.
7. switch: `ln -sfn releases/$RELEASE_ID /opt/tt-hack/preview.tmp && mv -T /opt/tt-hack/preview.tmp /opt/tt-hack/preview`.
8. smoke-check. Провал → rollback + exit 1.
9. Чистка старых релизов до `KEEP_RELEASES`.
10. Печать итога (коммит, web-статус, коды smoke, `deployed $RELEASE_ID`).

**Коды выхода:** `0` успех; `1` любой провал (лок не взят / сборка / rsync / smoke → после
отката); `2` неверные аргументы/отсутствует обязательный env.

**Идемпотентность:** повторный запуск на том же коммите создаёт новый `RELEASE_ID`, это ок.

---

## `scripts/preview_rollback.sh`

**Назначение:** вернуть предыдущий релиз.

**Вход (env):** те же хост/юзер, `PREVIEW_BASE_URL`, `PREVIEW_BASIC_AUTH` (для smoke после
отката).

**Флаги:** `--to <RELEASE_ID>` (откатить на конкретный, вместо «предыдущего»), `--list`
(показать релизы и текущий), `--local`.

**Шаги:**
1. `flock`.
2. `CURRENT=$(readlink /opt/tt-hack/preview | xargs basename)`.
3. Цель: `--to` или самый свежий в `releases/`, который не `CURRENT`.
4. Нет цели → `exit 3` с сообщением «откатываться не на что» (edge case «первая выкладка»).
5. Атомарный switch на цель.
6. `preview_smoke.sh` — предупредить, если и предыдущий не отвечает `200` (не откатывать
   обратно автоматически).
7. Печать: `rolled back <CURRENT> → <target>`.

**Коды выхода:** `0` успех; `2` аргументы; `3` нет цели для отката.

**Время:** < 2 c реальной работы (SC-004).

---

## `scripts/preview_smoke.sh`

**Назначение:** проверить доступность (FR-006). Переиспользуется деплоем, откатом, CI, руками.

**Вызов:** `preview_smoke.sh <base-url> [path ...]`. Пути по умолчанию — `/ /report.html /mcp.html`.

**Поведение:** для каждого пути `curl -sS -o /dev/null -w '%{http_code}' -u "$PREVIEW_BASIC_AUTH" "<base><path>"`.
Печатает `200 /report.html` построчно. Любой код ≠ `200` → накопить и в конце `exit 1`,
перечислив провалившиеся пути и коды. Полный URL с кредами не печатать (FR-014).

**Коды выхода:** `0` все `200`; `1` хотя бы один не `200`; `2` аргументы.

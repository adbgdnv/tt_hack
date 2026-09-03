# Research: Автодеплой превью

Phase 0. Разрешение открытых вопросов из Technical Context.

## R1. Триггер выкладки — как дождаться зелёного CI

**Decision**: `deploy.yml` с триггером `workflow_run` на `workflows: ["CI"]`,
`types: [completed]`, `branches: [main]`. В job — гард `if: github.event.workflow_run.conclusion == 'success'`.
Плюс `workflow_dispatch` для ручного запуска из UI.

**Rationale**: FR-003 требует «не публиковать, если CI не зелёный». `workflow_run` — штатный
способ сцепить два workflow и получить `conclusion` предыдущего. Не дублирует шаги CI.

**Alternatives considered**:
- Один workflow `on: push` с job'ами `test` → `deploy needs: test`. Проще, но тогда логика
  тестов размазывается или дублируется между `ci.yml` и деплоем; хотели держать CI отдельно.
- `deployment_status` / Environments — избыточно для одного контура.
- Ждать статус через API-поллинг — велосипед.

**Note**: `workflow_run` не запускается, пока `deploy.yml` не оказался в `main`. Первый прогон —
после мержа PR фичи. Это ожидаемо, отражено в quickstart.

## R2. Атомарное переключение версии

**Decision**: отдельный каталог артефактов `/opt/tt-hack-preview/`, раскладка
`releases/<UTC-timestamp>-<short-sha>/`, текущая версия — симлинк
`/opt/tt-hack-preview/current` → конкретный релиз. Переключение:
`ln -sfn <release> …/current.tmp && mv -T …/current.tmp …/current`.
`mv -T` над симлинком — атомарный `rename(2)`, посетитель Nginx видит либо старый, либо новый
каталог целиком (FR-007a).

**Rationale**: rsync прямо в раздаваемый каталог даёт окно, где часть файлов новая, часть
старая, а при провале — битую смесь (нарушение FR-007). Симлинк-свитч убирает окно и даёт
бесплатный откат (R3).

**Почему отдельный каталог, а не `/opt/tt-hack/preview`** (исправление первоначального
плана): `preview/` — git-tracked каталог в репозитории, а `/opt/tt-hack` на сервере — рабочий
git-клон (его использует `tt-hack-vibe-debug` и ручная выкладка). Превратить
`/opt/tt-hack/preview` в симлинк = сломать `git pull` на сервере (typechange +
«local changes would be overwritten», как только кто-то поправит `preview/*.html`). Разводим:
исходники в `/opt/tt-hack`, артефакты деплоя в `/opt/tt-hack-preview`. Побочный плюс: CI
больше не делает `git pull` на сервере — синкает `scripts/preview_*.sh` в
`/opt/tt-hack-preview/bin/` и запускает `--finalize` оттуда; git-клон автодеплою вообще не
нужен.

**Требование к Nginx**: `root` в `tt-hack-review.conf` → `/opt/tt-hack-preview/current`
(одна строка) + `nginx -t && systemctl reload nginx` один раз при настройке. `disable_symlinks
off` — дефолт.

**Alternatives considered**:
- `rsync --delete` в каталог + резервная копия перед выкладкой — дольше, окно рассинхрона
  остаётся.
- blue/green каталоги + правка `root` в Nginx + `reload` на каждый деплой — reload на каждый
  деплой, лишняя связанность с Nginx.
- `git update-index --skip-worktree preview` в клоне — хрупко, легко потерять при операциях с git.

## R3. Откат

**Decision**: `preview_rollback.sh` — читает, на какой релиз сейчас указывает симлинк, находит
предыдущий по времени в `releases/`, переключает симлинк тем же атомарным `mv -T`. Хранит
последние 5 релизов (`ls -1dt releases/*/ | tail -n +6 | xargs rm -rf`), чистка — в конце
`preview_deploy.sh` после успешного свитча.

**Rationale**: FR-011, SC-004 (< 2 мин). Переключение симлинка — миллисекунды; «2 минуты» —
это «человек зашёл по SSH и набрал команду».

**Alternatives considered**: откат через `git revert` + повторный деплой — это 10 минут и
зелёный CI, не подходит как «кнопка назад».

## R4. Сборка `src/web` когда её ещё нет

**Decision**: шаг в workflow и в `preview_deploy.sh`:
`if [ -f src/web/package.json ]; then (cd src/web && npm ci && npm run build); rsync src/web/dist/ → release root; fi`.
Иначе шаг пишет `src/web: no package.json, skip` и продолжает. Ожидаемый выход сборки —
`src/web/dist/` (дефолт Vite). Файлы `dist/` кладутся в корень релиза рядом с содержимым
`preview/` (FR-002); при коллизии имён верх берёт `preview/` — зафиксировать в contracts.

**Rationale**: FR-002 явно требует «пропускать без ошибки». Проверка по `package.json` —
однозначный признак «фронт завёлся».

**Alternatives considered**: отдельный флаг/переменная — лишняя ручка, забудут переключить.

## R5. Smoke-check

**Decision**: `preview_smoke.sh <base-url>` — `curl -sS -o /dev/null -w '%{http_code}' -u "$PREVIEW_BASIC_AUTH" <base>/<path>`
для путей `/`, `/report.html`, `/mcp.html`. Любой ответ ≠ `200` → exit 1 с указанием пути и кода.

**Порядок:** атомарный switch → `preview_smoke.sh` по боевому URL → при провале `atomic_switch`
на предыдущий релиз и `exit 1` (FR-007b). Окно, в котором «текущей» может быть непроверенная
версия, — только время одного прогона smoke (секунды), отката руками не требуется.

**Почему не «smoke до switch»:** проверка релиза до того, как он стал текущим, требует в Nginx
временного `location` на каталог-кандидат — лишняя связанность с Nginx и sudo на reload ради
экономии нескольких секунд. Для превью-ревью (не прод) секундное окно приемлемо; спека это
допускает явно (FR-007b, последнее предложение). Отдельный staging-адрес остаётся возможной
альтернативой, если позже понадобится нулевое окно.

**Rationale**: FR-006. `PREVIEW_BASIC_AUTH` (`user:password`) — из env или из
`~/.preview-smoke-auth`, передаётся в `curl -u`, полный URL с кредами не печатается.

**Alternatives considered**: `wget --spider`, headless-браузер (Playwright) — избыточно,
smoke-check про доступность, не про рендер (Assumptions).

## R6. Deploy-доступ и права

**Decision**: на сервере — пользователь `ttdeploy`, владелец всего `/opt/tt-hack-preview/`
(`releases/`, симлинк `current`, `bin/`) и читатель `/opt/tt-hack/scripts` для ручной
`--local`. НЕ владелец `/opt/tt-hack-review/` и без `sudo`. SSH — отдельная пара ключей,
приватный в
`DEPLOY_SSH_KEY`, публичный в `~ttdeploy/.ssh/authorized_keys` с
`command="…"`-ограничением необязательно (rsync по ssh нужен интерактивный shell) — вместо
этого ограничиваем правами ФС. `known_hosts` пиновать через `ssh-keyscan` в workflow (записать
в `DEPLOY_KNOWN_HOSTS` секрет ИЛИ `ssh-keyscan -H $DEPLOY_HOST` на лету — на лету проще, но
без пиннинга; берём секрет).

**GitHub Secrets (4)**: `DEPLOY_SSH_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_KNOWN_HOSTS`.
Basic Auth для smoke-check в CI **не хранится** — он на сервере в `~ttdeploy/.preview-smoke-auth`
(chmod 600), рядом с htpasswd Nginx. `preview_common.sh` читает файл, если env `PREVIEW_BASIC_AUTH`
пуст. Так секрет не гоняется по ssh при `--finalize` и живёт там же, где уже используется.

**Rationale**: FR-005, FR-008, FR-009. Ограничение правами ФС надёжнее, чем надежда на
`command=` при rsync.

**Alternatives considered**: деплой под `www-data` — у него доступ к чужому; общий
пользователь-человек — ключ живёт у одного, автодеплой не должен зависеть от личной учётки.

## R7. Сериализация выкладок

**Decision**: `concurrency: { group: preview-deploy, cancel-in-progress: false }` на уровне
job в `deploy.yml`. `cancel-in-progress: false` — не рвать текущую выкладку на середине rsync,
дать завершиться, потом пустить следующую. На сервере дополнительно `flock /opt/tt-hack-preview/.deploy.lock`
в `preview_deploy.sh` — защита от «ручная выкладка + автодеплой одновременно» (edge case).

**Rationale**: FR-013 + edge case «два мержа подряд» / «ручная и авто одновременно».

**Alternatives considered**: `cancel-in-progress: true` — риск оборванного rsync; полагаться
только на GH concurrency — не покрывает ручной запуск с сервера.

## R8. Секреты не в логах

**Decision**: ключ и `DEPLOY_*` — только через `env:`/`~/.ssh` из `secrets`, никаких `echo`.
`PREVIEW_BASIC_AUTH` в CI не фигурирует вовсе (читается на сервере).
`set -x` в bash-скриптах не включать глобально; в местах с секретами — `set +x`. GitHub сам
маскирует зарегистрированные секреты, но `curl -u` может утечь в `%{url_effective}` — в
`preview_smoke.sh` не печатать полный URL с кредами.

**Rationale**: FR-014, SC-006.

## Итог

Все NEEDS CLARIFICATION из Technical Context разрешены. Открытых вопросов к спеке нет
(Q1 закрыт до плана). Готово к Phase 1.

---

description: "Task list — Автодеплой превью"
---

# Tasks: Автодеплой превью

**Input**: Design documents from `specs/001-preview-autodeploy/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: автотестов на bash не заводим (Принцип III). Контроль качества — `shellcheck` в CI
(T022) + прогон `quickstart.md` (T024). Сам smoke-check — исполняемая проверка выкладки.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: можно делать параллельно (разные файлы, нет незакрытых зависимостей)
- **[Story]**: US1 / US2 / US3 — к какой user story относится

## Path Conventions

Фича вне `src/`: `.github/workflows/`, `scripts/`, `deploy/`. Пути — от корня репозитория.

---

## Phase 1: Setup

- [ ] T001 [P] Создать `deploy/PREVIEW-DEPLOY.md` — каркас ранбука с разделами: «Первичная
      настройка сервера», «Секреты репозитория», «Ручная выкладка», «Откат», «Диагностика».
      Разделы пока заглушки, наполняются в T005/T014/T021.
- [ ] T002 [P] Создать `scripts/preview_common.sh` — пустой модуль с `set -euo pipefail`,
      shebang, комментарием назначения; будет источником общих функций (T003).

## Phase 2: Foundational (блокирует все user stories)

- [ ] T003 Наполнить `scripts/preview_common.sh` общими функциями: `log()` (stdout, без
      секретов), `die()` (stderr + exit), `with_lock()` (`flock` по `/opt/tt-hack/.deploy.lock`,
      non-blocking → код 1), `release_id()` (`date -u +%Y%m%dT%H%M%SZ` + short-sha),
      `atomic_switch <release_dir>` (`ln -sfn` + `mv -T` симлинка `/opt/tt-hack/preview`),
      `find_previous_release()` (свежий каталог в `releases/`, не равный текущему),
      `prune_releases <keep>` (удалить старые, кроме текущего). Соответствует
      `contracts/server-layout.md` и `data-model.md`. Все пути строятся от константы
      `PREVIEW_ROOT=/opt/tt-hack` и физически не выходят за `releases/` и симлинк `preview`;
      ни одной команды `systemctl`/`docker`/записи в `/opt/tt-hack-review/` (FR-005).
- [ ] T004 [P] Создать `scripts/preview_smoke.sh` по `contracts/deploy-scripts.md`: аргументы
      `<base-url> [path ...]`, дефолтные пути `/ /report.html /mcp.html`, `curl -sS -o /dev/null
      -w '%{http_code}' -u "$PREVIEW_BASIC_AUTH"`, построчный вывод `КОД ПУТЬ`, накопление
      провалов, `exit 1` со списком не-`200`, `exit 2` на аргументы, полный URL с кредами не
      печатать (FR-014).
- [ ] T005 [P] Раздел «Первичная настройка сервера» в `deploy/PREVIEW-DEPLOY.md`: точные
      команды из `contracts/server-layout.md` (useradd `ttdeploy`, `mkdir releases/`, перенос
      текущего `preview/` в `releases/…-initial`, симлинк + `chown -h`, `authorized_keys`,
      `ssh-keyscan -H` → значение `DEPLOY_KNOWN_HOSTS`, проверка `200` через Nginx).
- [ ] T006 [P] Раздел «Секреты репозитория» в `deploy/PREVIEW-DEPLOY.md`: таблица
      `DEPLOY_SSH_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_KNOWN_HOSTS`, `PREVIEW_BASIC_AUTH`
      — что это и как получить; команды `gh secret set …`. Ключи не коммитить.

**Checkpoint**: `preview_common.sh` и `preview_smoke.sh` готовы, порядок настройки сервера
задокументирован. Дальше US1–US3 можно вести по приоритету.

---

## Phase 3: User Story 1 — авто-публикация по push в main (P1) 🎯 MVP

**Goal**: мерж в `main` при зелёном CI → превью на общем адресе обновляется само за ≤10 мин.

**Independent Test**: смержить коммит, меняющий текст в `preview/index.html`; убедиться, что
публичный адрес отдаёт новый текст без ручных действий; `readlink /opt/tt-hack/preview`
указывает на свежий релиз; `/opt/tt-hack-review/` и `tt-hack-vibe-debug` не затронуты.

- [ ] T007 [US1] Создать `scripts/preview_deploy.sh`: shebang + `source preview_common.sh`,
      разбор флагов `--dry-run` / `--local` / `--no-web`, валидация обязательного env
      (`PREVIEW_BASIC_AUTH`; `DEPLOY_HOST`/`DEPLOY_USER` кроме `--local`), коды выхода `0/1/2`
      по `contracts/deploy-scripts.md`. Целевые пути на сервере — только под `PREVIEW_ROOT`;
      скрипт не содержит `systemctl`, `docker`, `tt-hack-review` (FR-005).
- [ ] T008 [US1] В `scripts/preview_deploy.sh` — условная сборка фронта: если
      `src/web/package.json` существует и не `--no-web` → `(cd src/web && npm ci && npm run
      build)`, ожидать `src/web/dist/`; иначе `log "web: skipped (no package.json)"` (FR-002,
      research R4).
- [ ] T009 [US1] В `scripts/preview_deploy.sh` — сборка staging-каталога во временной
      директории: сначала `src/web/dist/` (если есть), затем `cp -rn preview/. staging/` (при
      коллизии имя из `preview/` не перезаписывается), записать файл `RELEASE` (sha, branch,
      built_at, `web=built|skipped`).
- [ ] T010 [US1] В `scripts/preview_deploy.sh` — доставка: `RELEASE_ID=$(release_id)`, `rsync
      -a --delete staging/ <target>:/opt/tt-hack/releases/$RELEASE_ID/`; `<target>` — по ssh
      (`$DEPLOY_USER@$DEPLOY_HOST`) или локально при `--local`. `--dry-run` печатает план и
      выходит.
- [ ] T011 [US1] В `scripts/preview_deploy.sh` — финализация: `atomic_switch releases/$RELEASE_ID`
      (атомарно, FR-007a), затем `prune_releases "${KEEP_RELEASES:-5}"`, печать итога (коммит,
      web-статус, `deployed $RELEASE_ID`). (Smoke сразу после switch и авто-откат добавляются
      в T015 — FR-007b.)
- [ ] T012 [US1] Создать `.github/workflows/deploy.yml` по `contracts/deploy-workflow.md`:
      `on.workflow_run` (workflows `["CI"]`, types `[completed]`, branches `[main]`) +
      `workflow_dispatch`; `concurrency: {group: preview-deploy, cancel-in-progress: false}`;
      job-гард `conclusion == 'success' || event_name == 'workflow_dispatch'`; `checkout` по
      `github.event.workflow_run.head_sha` (для dispatch — `main`).
- [ ] T013 [US1] В `.github/workflows/deploy.yml` — шаги: `setup-node@v4` (условно по
      `src/web/package.json`), запись `DEPLOY_SSH_KEY`→`~/.ssh/id_ed25519` (chmod 600) и
      `DEPLOY_KNOWN_HOSTS`→`~/.ssh/known_hosts`, запуск `scripts/preview_deploy.sh` с `env`
      из секретов, вывод итога в `$GITHUB_STEP_SUMMARY`.
- [ ] T014 [US1] Раздел «Ручная выкладка» в `deploy/PREVIEW-DEPLOY.md`: `ssh ttdeploy@<host>`,
      `cd /opt/tt-hack && git pull && scripts/preview_deploy.sh --local`; отметить, что это
      тот же скрипт, что в CI (FR-010). Плюс однострочная проверка, что Nginx раздаёт через
      симлинк.

**Checkpoint**: US1 самодостаточна — автодеплой публикует статику по push в main.

---

## Phase 4: User Story 2 — провал выкладки виден и безопасен (P2)

**Goal**: любой провал (CI красный, сборка, rsync, smoke) не оставляет превью битым и виден
красным статусом.

**Independent Test**: искусственно провалить smoke (испортить `PREVIEW_BASIC_AUTH`) →
`workflow_dispatch` → job красный, публичный адрес отдаёт прежнюю версию.

- [ ] T015 [US2] В `scripts/preview_deploy.sh` сразу после `atomic_switch`, до `prune_releases`
      (FR-007b): `preview_smoke.sh "$PREVIEW_BASE_URL"`; при ненулевом коде — `atomic_switch` на
      `find_previous_release`, `log` причину (`smoke failed: <код> <путь>; rolled back to
      <previous>`), `exit 1`. Prune при провале не выполняется. Окно непроверенной текущей
      версии = время одного `preview_smoke.sh`.
- [ ] T016 [US2] В `scripts/preview_deploy.sh` — fail-closed до switch: `npm`/`rsync`/сборка
      staging падают → `die` без изменения симлинка; `with_lock` не взят → `exit 1` с понятным
      сообщением (edge case «ручная и авто одновременно»).
- [ ] T017 [US2] В `.github/workflows/deploy.yml` — убедиться, что при `conclusion != success`
      job именно `skipped` (через `if:` на job), а не `failure`; `workflow_dispatch` гард
      обходит. Проверить, что провал любого шага делает job `failure`.
- [ ] T018 [US2] В шаге summary `deploy.yml` — вывести по каждому пути smoke его код и, при
      провале, строку «rolled back to <previous>»; секреты в summary не попадают.

**Checkpoint**: US2 — сломанная выкладка безопасна и заметна.

---

## Phase 5: User Story 3 — быстрый ручной откат (P3)

**Goal**: вернуть предыдущую опубликованную версию одной командой за < 2 мин.

**Independent Test**: опубликовать B поверх A, `preview_rollback.sh --local` → адрес снова
отдаёт A за секунды; повторный откат без предыдущего → `exit 3`, симлинк цел.

- [ ] T019 [US3] Создать `scripts/preview_rollback.sh` по `contracts/deploy-scripts.md`:
      `source preview_common.sh`, `with_lock`, определить `CURRENT` (`readlink`), цель —
      `--to <ID>` или `find_previous_release`; нет цели → `exit 3` «откатываться не на что»;
      `atomic_switch`; флаги `--list` (релизы + пометка текущего), `--local`; коды `0/2/3`.
- [ ] T020 [US3] В `scripts/preview_rollback.sh` — после переключения `preview_smoke.sh`;
      если и предыдущий релиз не отвечает `200` — предупредить в выводе, но НЕ переключать
      обратно автоматически (research R3). Печать `rolled back <CURRENT> → <target>`.
- [ ] T021 [US3] Раздел «Откат» в `deploy/PREVIEW-DEPLOY.md`: примеры `preview_rollback.sh
      --list` / `--local` / `--to <ID>`, заметка про целевое время < 2 мин (SC-004), что
      после отката следующий автодеплой публикует штатно поверх.

**Checkpoint**: US3 — «кнопка назад» работает независимо.

---

## Phase 6: Polish & Cross-Cutting

- [ ] T022 [P] Добавить в `.github/workflows/ci.yml` шаг проверки деплой-скриптов:
      `shellcheck scripts/preview_*.sh scripts/preview_common.sh` + guard
      `! grep -REn 'tt-hack-review|systemctl|docker ' scripts/preview_*.sh scripts/preview_common.sh`
      (падает, если скрипты трогают запретное — FR-005). Отдельный workflow не создаём.
- [ ] T023 [P] В `docs/architecture.md` (раздел «Ограничения, влияющие на архитектуру» /
      «Сроки») — строка: превью общего сервера обновляется автодеплоем по push в main, ручной
      путь и откат — в `deploy/PREVIEW-DEPLOY.md`. Не противоречит «прод продукта не нужен».
- [ ] T024 [P] Прогнать `specs/001-preview-autodeploy/quickstart.md` (сценарии 1–6), отметить
      чек-лист приёмки. Расхождения → новые задачи (вход в `/speckit-converge`).
- [ ] T025 [P] Просмотреть лог реального прогона `deploy.yml`: убедиться, что ни ключ, ни
      `PREVIEW_BASIC_AUTH`, ни пароль не видны (SC-006).
- [ ] T026 [P] Раздел «Диагностика» в `deploy/PREVIEW-DEPLOY.md`: частые сбои — протухший
      `DEPLOY_KNOWN_HOSTS`, нет прав у `ttdeploy`, `dist/` пуст, `workflow_run` не стартует до
      попадания `deploy.yml` в `main`.

---

## Dependencies

```
Setup (T001-T002)
  └─▶ Foundational (T003-T006)
        ├─ T003 preview_common.sh  ─── нужен для T007-T011, T015-T020
        └─ T004 preview_smoke.sh   ─── нужен для T015, T020, T024
              └─▶ US1 (T007-T014)          ← MVP, публикует
                    └─▶ US2 (T015-T018)    ← добавляет smoke-gate + откат при провале
                          └─▶ US3 (T019-T021)  ← отдельный CLI отката
                                └─▶ Polish (T022-T026)
```

- **US2 → US1**: T015–T018 правят `preview_deploy.sh` и `deploy.yml`, созданные в US1.
- **US3 частично параллелен US2**: `preview_rollback.sh` (T019) зависит только от T003
  (`atomic_switch`, `find_previous_release`), не от US2. Можно делать сразу после Foundational,
  если нужен раньше. T015 (US2) вызывает `find_previous_release` из T003, а не сам скрипт
  T019 — жёсткой зависимости US2→US3 нет.
- Внутри US1: T007→T008→T009→T010→T011 последовательны (один файл). T012 ∥ T007–T011. T013
  после T012. T014 [P].

## Parallel opportunities

- Setup: T001 ∥ T002.
- Foundational: T004 ∥ T005 ∥ T006 (T003 отдельно, он критический путь).
- US1: T012 (workflow) параллелен written-in-`preview_deploy.sh` задачам T007–T011.
- Polish: T022–T026 все [P].

## Implementation strategy

**MVP = Phase 1 + 2 + 3 (US1).** После него автодеплой работает: push в main → превью
обновляется. US2 и US3 — усиление надёжности, добавляются инкрементально, каждая проверяется
своим Independent Test.

Порядок поставки: `Setup → Foundational → US1 (демо: авто-публикация) → US2 (демо: провал
безопасен) → US3 (демо: откат) → Polish`.

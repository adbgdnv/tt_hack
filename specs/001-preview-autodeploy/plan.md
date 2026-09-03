# Implementation Plan: Автодеплой превью

**Branch**: `001-preview-autodeploy` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-preview-autodeploy/spec.md`

## Summary

По push в `main` GitHub Actions после зелёного CI выкладывает превью-статику (`preview/` +
сборка `src/web`, если она есть) на общий сервер: `rsync` по SSH deploy-ключу в новый
каталог-релиз, smoke-check `200` по обязательным страницам, атомарное переключение симлинка
`/opt/tt-hack/preview` на релиз. Предыдущий релиз сохраняется, откат — bash-скрипт на сервере.
Ручная выкладка — тот же скрипт. Kubernetes и docker registry не используются осознанно.

## Technical Context

**Language/Version**: Bash (POSIX + rsync/ssh), GitHub Actions YAML. Проектный Python 3.12 не
задействован — фича вне `src/`.

**Primary Dependencies**: `rsync`, `openssh` (на раннере и сервере — есть по умолчанию);
`curl` для smoke-check; Node.js LTS + `npm` на раннере для сборки `src/web` (только когда
появится `src/web/package.json`). Actions: `actions/checkout@v4`, `actions/setup-node@v4`.

**Storage**: файловая система сервера. Релизы — `/opt/tt-hack/releases/<timestamp>-<sha>/`,
текущий — симлинк `/opt/tt-hack/preview` → последний успешный релиз. Хранить последние N=5
релизов, старые удалять.

**Testing**: `bats` не тянем. Проверка деплой-скриптов — `shellcheck` в CI (добавить шаг) +
ручной прогон `deploy.sh --dry-run` на сервере. Smoke-check — сам по себе тест выкладки.
Существующий `pytest`/`ruff` фичу не покрывают (нет Python-кода).

**Target Platform**: Linux-сервер Timeweb (Ubuntu, Nginx), раннер `ubuntu-latest`.

**Project Type**: CI/CD + инфраструктурные скрипты. Не library/service — отдельный слой
`deploy/` + `scripts/` + `.github/workflows/`.

**Performance Goals**: от мержа до обновлённого превью ≤ 10 мин (SC-001); откат < 2 мин
(SC-004). rsync инкрементальный — типовая выкладка секунды.

**Constraints**: не трогать `/opt/tt-hack-review/`, сервис `tt-hack-vibe-debug`, контейнеры
`api`/`mcp` (FR-005) — скрипты оперируют только путями под `/opt/tt-hack/{releases,preview}` и
не вызывают `systemctl`/`docker`. Секреты только в GitHub Secrets, не в логах (FR-008/014).
Deploy-ключ — минимальные права (FR-009). Одновременно пишет один запуск (FR-013). Переключение
атомарно, само-откат при провале smoke (FR-007a/007b).

**Scale/Scope**: один сервер, один контур (`main` → общий превью). ~1 workflow, ~2 bash-скрипта,
~1 конфиг systemd/sudoers не нужен (деплой-юзер владеет `/opt/tt-hack/`).

## Constitution Check

*GATE: пройден.*

| Принцип | Применимость | Статус |
|---|---|---|
| I. Спека — первична | фича заведена через `/speckit-specify`, спека + план + задачи | ✅ соответствует |
| II. Ядро не знает про протоколы | фича не трогает `src/core` вовсе — только `deploy/`, `scripts/`, `.github/` | ✅ не нарушает |
| III. Минимальная реализация | rsync + симлинк вместо registry/k8s; N релизов, не полноценный релиз-менеджер | ✅ соответствует |
| IV. Требования кейсодателя | «демонстрация локальная, деплой не нужен» — но общий превью для ревью команды уже есть и используется; фича автоматизирует существующее, не добавляет прод | ✅ в рамках |
| V. Отбор полей | не относится | n/a |
| Рабочий процесс: CI зелёный перед merge | фича усиливает — деплой только после зелёного CI | ✅ соответствует |
| Секреты не в репозитории | deploy-ключ и Basic Auth — в GitHub Secrets и на сервере | ✅ соответствует |

Нарушений нет. Complexity Tracking не заполняется.

**Замечание для протокола:** `docs/architecture.md` фиксирует «деплой не нужен, docker-compose
достаточно». Это про **прод продукта**. Общий превью-сервер `tt-hack-review…sslip.io` —
инструмент ревью команды (`docs/VIBE-DEBUG-RUNBOOK.md`), он уже развёрнут и обновляется руками.
Фича заменяет ручное обновление автоматическим. Прод-контур продукта не создаётся.

## Project Structure

### Documentation (this feature)

```text
specs/001-preview-autodeploy/
├── plan.md              # этот файл
├── research.md          # Phase 0 — решения по транспорту, атомарности, сборке
├── data-model.md        # Phase 1 — релиз, deploy-доступ, отчёт о запуске
├── quickstart.md        # Phase 1 — как проверить выкладку и откат
├── contracts/
│   ├── deploy-workflow.md     # контракт GitHub Actions workflow (триггеры, входы, шаги, secrets)
│   ├── server-layout.md       # контракт раскладки на сервере (releases/, симлинк, права)
│   └── deploy-scripts.md      # CLI-контракт scripts/preview_deploy.sh и preview_rollback.sh
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
.github/
└── workflows/
    ├── ci.yml            # существует — без изменений (workflow_run слушает его)
    └── deploy.yml        # НОВЫЙ — триггер workflow_run(CI, main) + workflow_dispatch

scripts/
├── preview_deploy.sh     # НОВЫЙ — сборка src/web (опц.), rsync в релиз, smoke-check, switch
├── preview_rollback.sh   # НОВЫЙ — переключить симлинк на предыдущий релиз
└── preview_smoke.sh      # НОВЫЙ — curl 200 по списку путей через Basic Auth (общий для CI и ручного)

deploy/
├── nginx/
│   └── tt-hack-review.conf   # существует — БЕЗ изменений: root уже /opt/tt-hack/preview, он станет симлинком (research R2)
├── systemd/                  # существует — без изменений
└── PREVIEW-DEPLOY.md         # НОВЫЙ — runbook: первичная настройка сервера, deploy-юзер, ключ, ручная выкладка, откат

src/web/                      # источник фронта; сборка подхватывается когда появится package.json
preview/                      # источник статики — без изменений
```

**Structure Decision**: отдельный слой автодеплоя. Никакого кода в `src/` — Принцип II не
затрагивается. `deploy.yml` не расширяет `ci.yml`, а слушает его через `workflow_run`: CI
остаётся единственным местом про тесты/линт, деплой — отдельная ответственность. Скрипты в
`scripts/` (там уже живут `vibe_debug_server.py` и пр.), исполняются и на раннере, и на сервере
идентично — ручная выкладка = запуск того же `preview_deploy.sh` с сервера (FR-010).

## Complexity Tracking

Нарушений Constitution Check нет — таблица не заполняется.

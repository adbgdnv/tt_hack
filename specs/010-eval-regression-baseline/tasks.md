---

description: "Task list for 010-eval-regression-baseline"
---

# Tasks: Живой eval-набор для агента проверки контрагентов

**Input**: Design documents from `/specs/010-eval-regression-baseline/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Source package** (уже реализован и автономно протестирован — переносим, а не
пишем заново): `/Users/dara_bondarenko/Downloads/eval-current-agent-v1/`

**Tests**: юнит-тесты уже существуют в исходном пакете и переносятся вместе с кодом
(не TDD «сначала упавший тест» — перенос уже рабочей и проверенной пары код+тест).

**Organization**: задачи сгруппированы по user story из `spec.md` для независимой
проверки каждой.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: можно выполнять параллельно (разные файлы, нет незавершённых зависимостей)
- **[Story]**: US1 / US2 / US3 — соответствие user story из `spec.md`
- Пути указаны от корня репозитория `/Users/dara_bondarenko/repositories/alfa`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: подготовить каркас пакета и общую инфраструктуру, прежде чем переносить
код.

- [X] T001 Создать каркас пакета `evals/`: каталоги `evals/`, `evals/graders/`,
  `evals/runners/`, `evals/datasets/`, `evals/results/`; пустые `evals/__init__.py`,
  `evals/graders/__init__.py`, `evals/runners/__init__.py` (скопировать содержимое из
  `/Users/dara_bondarenko/Downloads/eval-current-agent-v1/evals/__init__.py` и
  `evals/graders/__init__.py`); `evals/datasets/.gitkeep` и `evals/results/.gitkeep`
  (пустые файлы-плейсхолдеры)
- [X] T002 [P] Добавить в `.gitignore` строки, игнорирующие `evals/datasets/*` и
  `evals/results/*` кроме `.gitkeep` (см. `research.md`, раздел 3) — по образцу уже
  существующих правил для `data` и `dataset/`
- [X] T003 [P] Добавить в `Makefile` таргеты `eval-build`, `eval-regression`,
  `eval-risk`, `eval-baseline`, вызывающие `python3.13 -m evals....` (не `python3`/без
  версии — см. `research.md`, раздел 2), в стиле существующих таргетов (комментарий
  `## описание` после двух пробелов, добавить имена в `.PHONY`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: перенести детерминированное ядро пакета (без обращения к сети) и
подтвердить, что оно работает в этом репозитории, прежде чем переходить к
живым/сюжетным задачам.

**⚠️ CRITICAL**: ни одна user story не начинается, пока эта фаза не пройдена.

- [X] T004 Перенести `evals/schema.py` (дословно) из
  `/Users/dara_bondarenko/Downloads/eval-current-agent-v1/evals/schema.py` в
  `evals/schema.py` — `Turn`, `ToolExpectation`, `Expectations`, `EvalCase`,
  `ToolCall`, `EvalTrace`, `GradeResult`, `CaseResult` (см. `data-model.md`)
- [X] T005 [P] Перенести `evals/graders/numbers.py` из исходного пакета
- [X] T006 [P] Перенести `evals/graders/policy.py` из исходного пакета
- [X] T007 [P] Перенести `evals/graders/tools.py` из исходного пакета
- [X] T008 [P] Перенести `evals/graders/aggregate.py` из исходного пакета
- [X] T009 Перенести `evals/runners/current_agent.py`
  (`CurrentAgentRunner`) из исходного пакета — зависит от T004; сигнатуры
  `core.repo.by_inn`, `core.report.build`, `api.agent.tools.build`,
  `api.agent.loop.Session`/`loop.run` уже сверены и совпадают (см. `research.md`,
  раздел 4), адаптация не требуется
- [X] T010 Перенести `evals/build_cases.py` (`CORE_DISTRIBUTION`,
  `build_core_suite`, `write_jsonl`, `main`) из исходного пакета — зависит от T004
- [X] T011 [P] Перенести `tests/test_eval_schema.py` из
  `/Users/dara_bondarenko/Downloads/eval-current-agent-v1/tests/test_eval_schema.py`
  в `tests/test_eval_schema.py` репозитория
- [X] T012 [P] Перенести `tests/test_eval_graders.py` в `tests/test_eval_graders.py`
  репозитория
- [X] T013 [P] Перенести `tests/test_eval_runner.py` в `tests/test_eval_runner.py`
  репозитория
- [X] T014 [P] Перенести `tests/test_eval_build_cases.py` в
  `tests/test_eval_build_cases.py` репозитория
- [X] T015 Прогнать `python3.13 -m pytest tests/test_eval_schema.py
  tests/test_eval_graders.py tests/test_eval_runner.py
  tests/test_eval_build_cases.py -q` и убедиться, что все тесты проходят и ни один не
  обращается к сети (FR-007) — зависит от T004–T014

**Checkpoint**: детерминированное ядро пакета перенесено и покрыто тестами — можно
переходить к user stories.

---

## Phase 3: User Story 1 - Регресс-гейт перед изменением агента (Priority: P1) 🎯 MVP

**Goal**: `make eval-baseline`/`eval-regression`/`eval-risk` реально прогоняют
фиксированный набор на живом агенте и разделяют пройденные/провальные/
инфраструктурные исходы.

**Independent Test**: прогнать `make eval-build`, затем `make eval-baseline` на
неизменённом агенте и получить `pass_rate` с отдельными списками `failed` и
`infra_errors` (без обращения к User Story 2/3).

### Implementation for User Story 1

- [X] T016 [US1] Перенести `evals/run.py` (`load_cases`, `evaluate_case`,
  `evaluate`, `summarize`, CLI `main`) из
  `/Users/dara_bondarenko/Downloads/eval-current-agent-v1/evals/run.py` в
  `evals/run.py` — зависит от T004, T009
- [X] T017 [P] [US1] Перенести `tests/test_eval_run.py` в `tests/test_eval_run.py`
  репозитория
- [X] T018 [US1] Прогнать `python3.13 -m pytest tests/test_eval_run.py -q` и
  убедиться, что тесты проходят — зависит от T016, T017
- [X] T019 [US1] Прогнать `make eval-build` на актуальном
  `dataset/counterparties.json` и убедиться, что собрано ровно 30 кейсов (16
  regression + 14 risk) с распределением из `evals/README.md` — зависит от T003,
  T010, T015
- [X] T020 [US1] Прогнать `make eval-baseline` на живом агенте (`.env` уже содержит
  `DATASET_PATH`/`LLM_API_KEY`), сохранить результат в `evals/results/baseline.json`,
  убедиться, что итог укладывается в 10 минут (SC-002) и явно разделяет
  `passed`/`failed`/`infra_errors` — зависит от T019
- [ ] T021 [US1] **ОТЛОЖЕНО** (2026-09-05, решение пользователя) — Проверить
  Acceptance Scenario 2 из спеки: временно вернуть в поведение агента одну из уже
  известных ошибок (например, трактовку `UNKNOWN` как низкого риска, точечной правкой
  промпта без коммита), прогнать `make eval-regression`/`eval-risk` и убедиться, что
  провалился именно соответствующий кейс с понятной причиной в `details`, затем
  откатить правку и подтвердить, что кейс снова проходит — зависит от T020; изменение
  в шаге не коммитить. **Блокер**: нужен ещё один живой вызов модели, дневная квота
  Groq (200 000 токенов/сутки) на 2026-09-05 подтверждённо исчерпана тремя отдельными
  проверками (см. `evals/README.md`, «Лимиты Groq и ретрай»). Разблокируется сбросом
  суточной квоты или переключением на резервный провайдер (`OpenRouter` в `.env`).

**Checkpoint**: User Story 1 функционально работает — механика MVP (сборка датасета,
живой прогон, разделение качества и инфра-ошибок, ретрай на временный rate limit)
подтверждена реальным прогоном (T019, T020); финальная демонстрация «регресс
ловится и лечится» (T021) отложена до появления живой квоты.

---

## Phase 4: User Story 2 - Пересборка датасета из актуальных данных (Priority: P2)

**Goal**: подтвердить, что сборка датасета детерминирована, падает явно при нехватке
покрытия и не утекает в git — независимо от того, запускался ли живой агент.

**Independent Test**: прогнать `make eval-build` и проверить детерминированность и
гарантию покрытия без обращения к живому агенту (не зависит от Phase 3).

### Implementation for User Story 2

- [X] T022 [P] [US2] Прогнать `make eval-build` дважды подряд и убедиться, что
  `evals/datasets/generated.jsonl` побайтово одинаков между прогонами (тот же состав
  и порядок 30 кейсов) — реализует edge case «повторный запуск сборки без изменения
  данных» из спеки
- [X] T023 [US2] Временно указать `DATASET_PATH` на копию датасета без одной из
  обязательных категорий (например, без единой компании с `riskLevel=UNKNOWN`) и
  убедиться, что `make eval-build` завершается явной ошибкой с названием недостающей
  категории, а не уменьшенным набором (FR-002, Acceptance Scenario 2 User Story 2);
  временную копию датасета не оставлять в рабочей копии после проверки
- [X] T024 [US2] Прогнать `git status --short evals/datasets/ evals/results/` после
  сборки датасета (T019) и живого прогона (T020) и убедиться, что вывод пуст — ни
  один файл с реальными ИНН не попадает в отслеживаемые изменения (FR-003,
  Acceptance Scenario 3 User Story 2)

**Checkpoint**: путь пересборки датасета проверен независимо — можно менять
`dataset/counterparties.json` или логику отчёта/графиков, не боясь разойтись с
ручной разметкой (которой здесь просто нет).

---

## Phase 5: User Story 3 - Чтение и интерпретация baseline (Priority: P3)

**Goal**: документация по эталону понятна человеку, не участвовавшему в разработке
набора.

**Independent Test**: дать `evals/README.md` вместе с зафиксированным результатом
человеку без контекста этой фичи и убедиться, что он может объяснить, что означает
`pass_rate`, чем `failed` отличается от `infra_error`, и на какой версии модели снят
текущий эталон.

### Implementation for User Story 3

- [X] T025 [US3] Перенести `evals/README.md` из исходного пакета в `evals/README.md`
  репозитория и обновить раздел «Live baseline» реальными цифрами `pass_rate`/
  `mean_score` и версией модели/промпта из результата T020 (per `quickstart.md`,
  шаг 5) — зависит от T020
- [X] T026 [P] [US3] Добавить в корневой `README.md` короткую ссылку-абзац на
  `evals/README.md` (одна-две строки: что это и какой командой запускается), чтобы
  набор был обнаружим без знания точного пути

**Checkpoint**: все три user story работают независимо друг от друга.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: финальная проверка перед PR, затрагивающая все три story сразу.

- [X] T027 [P] Прогнать `ruff check evals/ tests/test_eval_build_cases.py
  tests/test_eval_graders.py tests/test_eval_run.py tests/test_eval_runner.py
  tests/test_eval_schema.py` и исправить нарушения стиля (конституция: CI должен
  быть зелёным перед merge)
- [ ] T028 **ОТЛОЖЕНО** (2026-09-05, решение пользователя, тот же блокер, что у T021)
  — Пройти `quickstart.md` целиком ещё раз от начала до конца после того, как все
  задачи выполнены, и убедиться, что каждый шаг даёт ожидаемый результат — сквозная
  проверка всех трёх user story вместе. Шаги 1–2 (юниты, сборка датасета) уже
  пройдены отдельно; шаг 3 (живой прогон) требует доступной квоты провайдера.
- [X] T029 Обновить `specs/010-eval-regression-baseline/spec.md` (раздел
  Assumptions) фактическими цифрами, если что-то разошлось с предположениями во время
  переноса (реальное распределение кейсов, реальное время прогона, версия модели) —
  спека остаётся живым артефактом (Constitution I)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: без зависимостей — начинать сразу
- **Foundational (Phase 2)**: зависит от Setup — блокирует все user stories
- **User Story 1 (Phase 3)**: зависит от Foundational; независим от US2/US3 —
  можно останавливаться здесь как на MVP
- **User Story 2 (Phase 4)**: зависит от Foundational; T024 читает артефакты,
  созданные в T019/T020 (Phase 3), но сама механика сборки (T022, T023)
  проверяется без живого агента и без Phase 3
- **User Story 3 (Phase 5)**: зависит от Foundational; T025 использует результат
  T020 (Phase 3) как источник реальных цифр — по сути, документирующая надстройка
  над уже готовым MVP
- **Polish (Phase 6)**: зависит от завершения всех трёх user story

### Within Each User Story

- Перенос кода → перенос тестов → прогон тестов → перенос от исходного пакета
  → живая проверка на реальных данных → проверка edge cases из спеки

### Parallel Opportunities

- T005–T008 (грейдеры) — разные файлы, можно параллельно после T004
- T011–T014 (перенос тестов) — разные файлы, можно параллельно после T004/T009/T010
- T002 и T003 (Setup) — разные файлы, можно параллельно с T001
- T022 и T023 (User Story 2) не трогают одни и те же файлы одновременно — можно
  параллельно
- T026 (User Story 3) не зависит от T025 по файлам — можно параллельно

---

## Parallel Example: Foundational (Phase 2)

```bash
# После T004 (schema.py) — грейдеры переносятся параллельно:
Task: "Перенести evals/graders/numbers.py"
Task: "Перенести evals/graders/policy.py"
Task: "Перенести evals/graders/tools.py"
Task: "Перенести evals/graders/aggregate.py"

# После T004/T009/T010 — тесты переносятся параллельно:
Task: "Перенести tests/test_eval_schema.py"
Task: "Перенести tests/test_eval_graders.py"
Task: "Перенести tests/test_eval_runner.py"
Task: "Перенести tests/test_eval_build_cases.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup
2. Phase 2: Foundational (блокирует всё остальное)
3. Phase 3: User Story 1 → `make eval-baseline` работает на живом агенте
4. **Остановиться и проверить**: `pass_rate` получен, `failed`/`infra_errors`
   разделены (quickstart.md, шаги 1–3)
5. Это уже пригодно как регресс-гейт перед мерджем изменений агента

### Incremental Delivery

1. Setup + Foundational → детерминированное ядро готово и покрыто тестами
2. User Story 1 → живой baseline снят → можно гейтить изменения агента (MVP)
3. User Story 2 → подтверждены детерминированность сборки, гарантия покрытия и
   git-гигиена
4. User Story 3 → документация читаема без контекста, эталон зафиксирован с версией
   модели
5. Polish → `ruff` зелёный, `quickstart.md` пройден целиком, спека обновлена
   фактическими цифрами

# Implementation Plan: Живой eval-набор для агента проверки контрагентов

**Branch**: `010-eval-regression-baseline` | **Date**: 2026-09-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-eval-regression-baseline/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Перенести уже реализованный и автономно протестированный пакет `evals/` (30
детерминированно собираемых live-кейсов, три грейдера, тонкий раннер поверх
`api.agent.loop.run`) из `~/Downloads/eval-current-agent-v1/` в репозиторий, сверить
его со здешними конвенциями (два интерпретатора Python, существующий `Makefile`,
`.gitignore`, layout `tests/`), убедиться, что генератор строит ровно 30 кейсов на
`dataset/counterparties.json` без ошибок покрытия, и зафиксировать первый живой
baseline через настроенный в `.env` провайдер LLM.

## Technical Context

**Language/Version**: Python 3.12 (проект), фактически запускается интерпретатором
3.13, куда установлены зависимости (`python3.13 -m pytest` — см. известную развилку
интерпретаторов на машине разработки; `pytest`/`python3` в `PATH` — 3.14 без зависимостей).

**Primary Dependencies**: только уже имеющиеся в `pyproject.toml` (`langchain`,
`langgraph`, `langchain-openai`, `pytest`, `pytest-asyncio`, `ruff`) — новый пакет
не добавляет зависимостей, использует только стандартную библиотеку плюс то, что уже
тянет `api.agent`.

**Storage**: файловая — вход `dataset/counterparties.json` (уже существует, в
`.gitignore`), выход `evals/datasets/generated.jsonl` и `evals/results/*.json`
(новые, тоже должны быть в `.gitignore` — содержат реальные ИНН и полные ответы
агента).

**Testing**: `pytest` (юниты нового пакета — без сети, чистые функции/фейки) +
`python -m evals.run` (живой прогон через реальный `api.agent.loop.run`, отдельно от
`pytest`, требует `DATASET_PATH` и `LLM_API_KEY`).

**Target Platform**: то же окружение, что и у продукта — macOS/Linux, тот же способ
запуска (`python3.13`), без Docker/CI-специфики в рамках этой фичи.

**Project Type**: single project — существующий Python-монорепозиторий
(`src/core`, `src/api`), новый top-level каталог `evals/` того же уровня, что `src/`
и `tests/`.

**Performance Goals**: полный живой прогон 30 кейсов укладывается в 10 минут при
доступном провайдере (SC-002); отдельных требований к пропускной способности нет —
это инструмент разработки, а не продуктовый путь.

**Constraints**: юниты `evals` никогда не обращаются к живому провайдеру (FR-007);
сгенерированный датасет и результаты прогонов с реальными ИНН не попадают в git
(FR-003); инфраструктурные ошибки провайдера считаются отдельно от ошибок качества
агента (FR-006); не добавляется LLM-as-a-Judge и не меняется сам агент
(`src/api`, `src/core`).

**Scale/Scope**: фиксированные 30 кейсов (16 regression + 14 risk), один прогон —
одна live-оценка; масштабирование числа кейсов вне скоупа этой фичи.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Спека — первична** — соблюдено: фича идёт через
  `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`.
- **II. Ядро не знает про протоколы** — соблюдено: `evals/` — это инструмент разработки
  (по статусу как `tests/`), а не продуктовое приложение. Он читает `core.*` и вызывает
  `api.agent.loop.run` так же, как уже делают `tests/test_agent.py`,
  `tests/test_tools.py` и другие — прецедент внутри репозитория есть. `src/core`
  и `src/api` этой фичей не меняются.
- **III. Минимальная реализация** — соблюдено: пакет уже реализован и автономно
  протестирован (16/16 юнит-тестов), задача — перенос и подгонка под конвенции
  репозитория, а не проектирование заново. Найденная смежная проблема (текущий
  `Makefile`-таргет `test` не учитывает разницу интерпретаторов) в эту фичу не
  затягивается — только новые `eval-*`-таргеты явно используют `python3.13`, чтобы не
  наследовать ту же ловушку.
- **IV. Требования кейсодателя — закон** — соблюдено и усилено: policy-грейдер уже
  запрещает агенту формулировки вида «не работайте»/«можно работать» (кейс
  `risk_conflict`) — то есть сам набор проверяет, что агент рекомендует, а не выносит
  вердикт, и что отсутствие данных не превращается в «рисков нет» (кейсы `empty`,
  `not_applicable`, `bank_unknown`).
- **V. Отбор полей** — не затрагивается: живой прогон идёт через тот же
  `core.report.build`/`core.charts.build_charts`, что и продукт, без обхода лимитов
  токенов.

Нарушений нет, Complexity Tracking не заполняется.

## Project Structure

### Documentation (this feature)

```text
specs/010-eval-regression-baseline/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

Отдельный `contracts/` не создаётся: у фичи нет внешнего API/эндпоинта — контракт
между сборкой датасета и раннером (схема `EvalCase`/`EvalTrace`/`CaseResult`)
документирован в `data-model.md`.

### Source Code (repository root)

```text
evals/                       # новый top-level пакет — инструмент разработки, не продукт
├── __init__.py
├── README.md                 # что проверяем, как собрать датасет, как читать baseline
├── schema.py                  # EvalCase, Expectations, EvalTrace, CaseResult, GradeResult
├── build_cases.py             # build_core_suite(...) — детерминированная сборка 30 кейсов
├── run.py                     # CLI: load_cases/evaluate/summarize, живой прогон
├── runners/
│   └── current_agent.py       # CurrentAgentRunner — тонкий адаптер над api.agent.loop.run
├── graders/
│   ├── numbers.py              # извлечение чисел + допуск на округление
│   ├── policy.py                # required/forbidden regex, critical-провал
│   ├── tools.py                  # точное сравнение вызовов инструментов и параметров
│   └── aggregate.py              # aggregate_case(...) -> CaseResult
├── datasets/
│   └── .gitkeep                  # generated.jsonl сюда пишется, но в git не попадает
└── results/
    └── .gitkeep                  # baseline.json и прочие прогоны, тоже вне git

tests/
├── test_eval_schema.py
├── test_eval_build_cases.py
├── test_eval_runner.py
├── test_eval_graders.py
└── test_eval_run.py

Makefile                     # + eval-build/eval-regression/eval-risk/eval-baseline
.gitignore                   # + evals/datasets/, evals/results/ (кроме .gitkeep)
```

**Structure Decision**: используется существующий single-project layout репозитория.
`evals/` добавляется как отдельный top-level пакет рядом с `src/` и `tests/` — по
статусу это инструмент разработки (как `tests/`), поэтому ему разрешено импортировать
`core.*` и `api.agent.*` напрямую, не нарушая границу ядра (граница — про то, что
`src/core` не импортирует приложения, а не про то, кто импортирует `core`). Юнит-тесты
пакета переносятся в существующий `tests/`, чтобы `pytest`/CI подхватывали их без
дополнительной конфигурации `testpaths`.

## Complexity Tracking

*Нарушений Constitution Check нет — таблица не заполняется.*

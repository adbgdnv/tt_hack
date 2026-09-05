# Quickstart: проверка живого eval-набора

Проверяет, что перенесённый пакет реально работает в этом репозитории — от юнитов
без сети до живого прогона на 30 кейсах.

## Предпосылки

- `dataset/counterparties.json` уже существует в рабочей копии (собран заранее
  `scripts/build_dataset.py`; при отсутствии — см. `make data` и
  `python3.13 scripts/build_dataset.py`).
- `.env` содержит `DATASET_PATH` и `LLM_API_KEY`/`LLM_BASE_URL` — те же, что нужны
  продукту для живого ответа агента.
- Зависимости стоят в Python 3.13 (`pip install -e ".[dev]"`), команды ниже
  **обязательно** через `python3.13`, а не `pytest`/`python3` без версии — см.
  [research.md, раздел 2](./research.md#2-разница-интерпретаторов-python-на-машине-разработки).

## 1. Юниты пакета — без сети

```bash
python3.13 -m pytest tests/test_eval_schema.py tests/test_eval_build_cases.py \
  tests/test_eval_runner.py tests/test_eval_graders.py tests/test_eval_run.py -q
```

**Ожидаемо**: 16 пройденных тестов, ни одного обращения к сети (FR-007, SC-004).

## 2. Сборка фиксированного датасета из актуальных данных

```bash
make eval-build
# эквивалент: python3.13 -m evals.build_cases
```

**Ожидаемо**: сообщение `generated 30 eval cases -> evals/datasets/generated.jsonl`.
Если в `dataset/counterparties.json` не хватает покрытия одной из девяти категорий —
команда завершается ошибкой с названием категории и требуемым/найденным числом
(FR-002), а не тихо уменьшенным набором.

**Проверка, что файл не уйдёт в git**:

```bash
git status --short evals/datasets/
```

Ожидаемо: пусто (файл проигнорирован).

## 3. Живой прогон на реальном агенте

```bash
make eval-regression   # 16 кейсов
make eval-risk         # 14 кейсов
make eval-baseline     # все 30 + JSON в evals/results/baseline.json
```

**Ожидаемо** (SC-002, SC-003): полный `eval-baseline` укладывается в 10 минут;
в stdout — сводка вида:

```json
{
  "cases": 30,
  "evaluated": 30,
  "passed": <N>,
  "failed": <M>,
  "infra_errors": 0,
  "pass_rate": <0..1>,
  "mean_score": <0..1>
}
```

Если у части кейсов `infra_errors > 0` (таймаут/429 провайдера) — это не считается
падением качества агента (FR-006): смотреть на `pass_rate` относительно `evaluated`,
а не относительно всех 30.

## 4. Разбор конкретного провала

Открыть `evals/results/baseline.json`, найти `case_id` в `results`, посмотреть
`grades[].details` — там `missing:`/`forbidden:`/`wrong_params:` указывает, какое
именно ожидание не выполнено (см. `data-model.md`, `GradeResult`).

## 5. Baseline как точка сравнения

После первого успешного `make eval-baseline` — зафиксировать в `evals/README.md`
(или соседнем файле результатов), на какой версии модели/промпта он снят
(`docs/architecture.md`/`.env` → `LLM_BASE_URL`, имя модели). Любой следующий прогон
после изменения промпта/модели/логики агента сравнивается с этим `pass_rate`, а не
запускается «с нуля» без контекста (SC-003, User Story 3).

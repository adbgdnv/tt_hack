# История спецификаций

## Миграция OpenSpec → GitHub Spec Kit (2026-09-03)

Проект вёлся в OpenSpec (ручной Markdown в `openspec/`). Перешли на GitHub Spec Kit
`v1.0.4` — CLI `specify`, шаблоны в `.specify/`, скилы `/speckit-*` в
`.claude/skills/`.

Что куда переехало:

| OpenSpec | Spec Kit |
|---|---|
| `openspec/project.md` + `openspec/AGENTS.md` | `.specify/memory/constitution.md` |
| `openspec/changes/add-monorepo-skeleton/` | `docs/history/add-monorepo-skeleton/` (поставлен, архив) |
| `openspec validate --strict` | `/speckit-analyze` |
| ручной жизненный цикл change | ветка на фичу + `/speckit-converge` |

`add-monorepo-skeleton` был закрыт к моменту миграции (каркас `src/`, ядро,
приложения, инфраструктура, CI). Открытыми оставались задачи, вынесенные в
отдельные фичи: реализация `scoring`/`financials`/`compare`/`charts`, фронтенд,
прогон `pytest`/`make up` в окружении с зависимостями.

## Как продолжать

```
/speckit-specify   <описание фичи>   # спека + ветка NNN-<slug>
/speckit-plan                        # план файлов и зависимостей
/speckit-tasks                       # 10-20 атомарных задач
/speckit-implement                   # код по задачам
/speckit-converge                    # сверка кода со спекой
```

Опционально: `/speckit-clarify` (до plan), `/speckit-analyze` (после tasks),
`/speckit-checklist`.

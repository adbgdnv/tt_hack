# Контракт: `.github/workflows/deploy.yml`

## Триггеры

```yaml
on:
  workflow_run:
    workflows: ["CI"]
    types: [completed]
    branches: [main]
  workflow_dispatch: {}
```

## Гард

Job выполняется только если:
- `github.event_name == 'workflow_dispatch'` **или**
- `github.event.workflow_run.conclusion == 'success'`

Иначе job — `skipped` (не `failed`): красный статус бережём для реальных провалов деплоя.

## Concurrency

```yaml
concurrency:
  group: preview-deploy
  cancel-in-progress: false
```

## Шаги (в порядке)

| # | Шаг | Провал → |
|---|---|---|
| 1 | `actions/checkout@v4` (ref = SHA из `workflow_run`, для dispatch — `main`) | fail |
| 2 | `actions/setup-node@v4` (LTS) — только если есть `src/web/package.json` | fail |
| 3 | Установить SSH: записать `DEPLOY_SSH_KEY` в `~/.ssh/id_ed25519` (chmod 600), `DEPLOY_KNOWN_HOSTS` в `~/.ssh/known_hosts` | fail |
| 4 | Запустить `scripts/preview_deploy.sh` (режим CI) с `DEPLOY_HOST`/`DEPLOY_USER` в env | fail, симлинк на сервере не тронут |
| 5 | Вывести summary в `$GITHUB_STEP_SUMMARY`: коммит, статус сборки web, итог job, ссылку на лог шага 4 (в нём — коды smoke) | — |

Шаг 4 собирает staging и rsync-ит релиз на сервер, затем по ssh запускает
`preview_deploy.sh --finalize <id>` на сервере — switch, smoke, prune. Логика в скрипте, не в
YAML, чтобы ручной запуск (`--local`) был идентичен (FR-010).

## Передача секретов в шаг

```yaml
env:
  DEPLOY_HOST: ${{ secrets.DEPLOY_HOST }}
  DEPLOY_USER: ${{ secrets.DEPLOY_USER }}
```

Ключ и known_hosts — уже в `~/.ssh/` после шага 3. Basic Auth для smoke-check в CI **не
передаётся** — `preview_deploy.sh --finalize` на сервере читает его из
`~ttdeploy/.preview-smoke-auth`. Ничего не `echo`-ится.

## Наблюдаемое поведение (для приёмки)

- CI красный на коммите → `deploy.yml` job `skipped`, на сервере ничего не поменялось.
- CI зелёный → в течение 10 мин симлинк `/opt/tt-hack/preview` указывает на новый релиз.
- Любой шаг упал → job красный, `readlink /opt/tt-hack/preview` не изменился (кроме случая
  R5-компромисса: smoke упал после switch → скрипт сам откатил, job красный).
- Два `workflow_run` подряд → второй ждёт первого (concurrency), не отменяя.

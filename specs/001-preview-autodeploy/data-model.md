# Data Model: Автодеплой превью

Фича не работает с БД. «Сущности» здесь — состояние на файловой системе сервера и в GitHub.

## Release (релиз превью)

Снимок каталога превью, соответствующий одному коммиту `main`.

| Поле | Где живёт | Значение |
|---|---|---|
| `id` | имя каталога | `<UTC timestamp YYYYMMDDTHHMMSSZ>-<short-sha>` |
| `path` | ФС сервера | `/opt/tt-hack/releases/<id>/` |
| `commit` | часть `id` + файл `RELEASE` внутри | полный SHA, ветка, время сборки |
| `contents` | ФС | содержимое `preview/` + (опц.) содержимое `src/web/dist/` |
| `is_current` | вычисляется | `readlink /opt/tt-hack/preview` указывает на этот `path` |

**Правила:**
- Хранится максимум 5 релизов. Лишние (самые старые, не `current`) удаляются в конце успешного
  деплоя.
- Релиз, на который указывает симлинк, не удаляется никогда.
- Предыдущий по времени относительно `current` — цель отката.

**Переходы состояния:**

```
(нет)
  │  preview_deploy.sh: rsync содержимого
  ▼
staged ──── smoke-check провален ────▶ остаётся staged, симлинк не тронут, deploy exit 1
  │
  │  smoke-check 200 по всем путям → mv -T симлинка
  ▼
current ──── следующий деплой ────▶ previous
  │
  │  preview_rollback.sh (если это был current)
  ▼
previous снова становится current
```

## CurrentPointer (указатель текущей версии)

Симлинк `/opt/tt-hack/preview` → `releases/<id>/`. Nginx (`root /opt/tt-hack/preview;`) раздаёт
то, на что он указывает. Переключается только атомарным `mv -T`. Единственный «источник
истины» о том, что сейчас на превью.

## DeployAccess (доступ для выкладки)

| Элемент | Хранилище | Назначение |
|---|---|---|
| `DEPLOY_SSH_KEY` | GitHub Secret | приватный ключ пары деплоя |
| `DEPLOY_HOST` | GitHub Secret | адрес сервера |
| `DEPLOY_USER` | GitHub Secret | `ttdeploy` |
| `DEPLOY_KNOWN_HOSTS` | GitHub Secret | строка `ssh-keyscan` для пиннинга хоста |
| `PREVIEW_BASIC_AUTH` | GitHub Secret | `user:password` для smoke-check через Nginx Basic Auth |
| публичный ключ | `~ttdeploy/.ssh/authorized_keys` на сервере | приём деплой-соединения |

**Правила:** `ttdeploy` владеет `/opt/tt-hack/releases/` и симлинком, не имеет `sudo`, не имеет
доступа на запись в `/opt/tt-hack-review/`. Ни один элемент не хранится в репозитории и не
печатается в логах.

## RunReport (отчёт о запуске)

Не файл — лог GitHub Actions job + строки, которые печатают скрипты. Обязательный минимум
(FR-012):

- контур: `preview (main)`;
- опубликованный коммит: SHA + ветка;
- сборка `src/web`: `built` / `skipped (no package.json)`;
- smoke-check: по каждому пути (`/`, `/report.html`, `/mcp.html`) — код ответа;
- итог: `deployed <release-id>` / `failed at <шаг>`.

Хранится столько, сколько GitHub держит логи Actions. Отдельного персистентного журнала на
сервере не заводим (Принцип III) — кроме файла `RELEASE` внутри каждого релиза.

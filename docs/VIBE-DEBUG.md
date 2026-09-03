# vibe-debug — запуск и деплой

Каркас визуального ревью через коммент-превью. Портирован из проекта `lapki`,
здесь пока в состоянии заглушки: сервер и API рабочие, оверлей минимальный —
только пины и статусы; режимов dev/art, рисования и вложений нет.

## Состав

| Путь | Что это |
|------|---------|
| `scripts/vibe_debug_server.py` | Статический сервер + review API. Python 3.10+, только stdlib. |
| `schemas/vibe-debug-comment.schema.json` | Единственная схема DBG-записи. |
| `preview/` | Корень статики, который отдаёт сервер (заглушка + оверлей). |
| `preview/assets/vibe-debug.{js,css}` | Минимальный клиент ревью. |
| `.claude/skills/vibe-debug/` | Скилл `/vibe-debug` для Claude Code. |

## Локальный запуск

```bash
python3 scripts/vibe_debug_server.py
```

Откроется на `http://127.0.0.1:8788/index.html`. Комментарии пишутся в
`.vibe-debug/comments.json` (в git не коммитится).

Переменные окружения:

| Переменная | По умолчанию | Назначение |
|-----------|--------------|------------|
| `VIBE_DEBUG_HOST` | `127.0.0.1` | адрес прослушивания |
| `VIBE_DEBUG_PORT` | `8788` | порт |
| `VIBE_DEBUG_ROOT` | `preview/` | корень статики |
| `VIBE_DEBUG_DATA` | `.vibe-debug/comments.json` | файл комментариев |

## API

| Метод и путь | Назначение |
|--------------|-----------|
| `GET /__review__/session` | автор из заголовка `X-Review-User` (его проставляет Nginx) |
| `GET /__review__/comments?route=/path` | список комментариев маршрута |
| `POST /__review__/comments` | создать комментарий (тело валидирует `normalize_comment`) |
| `POST /__review__/comments/status` | сменить статус: `{ "id", "status" }` |
| `POST /__review__/comments/delete` | удалить: `{ "id" }` |

## Общий превью-сервер (основной режим, как в lapki)

Локальный запуск — только для отладки самого оверлея. Ревью команда ведёт на
одном общем сервере: комментарии переживают перезапуск и видны всем
авторизованным участникам. Превью закрыто Nginx Basic Auth; `.htpasswd`,
пароли и хэши в репозиторий не коммитятся.

Готовые шаблоны:

- `deploy/systemd/tt-hack-vibe-debug.service`
- `deploy/nginx/tt-hack-vibe-debug.location.conf`

Развёртывание:

```bash
# на сервере
sudo mkdir -p /opt/tt-hack /opt/tt-hack-review
sudo git clone https://github.com/adbgdnv/tt_hack.git /opt/tt-hack
sudo chown -R www-data:www-data /opt/tt-hack /opt/tt-hack-review

# сервис
sudo cp /opt/tt-hack/deploy/systemd/tt-hack-vibe-debug.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now tt-hack-vibe-debug
systemctl status tt-hack-vibe-debug

# доступ (пример; логины согласуйте с командой)
sudo mkdir -p /etc/nginx/htpasswd
sudo htpasswd -c /etc/nginx/htpasswd/tt-hack reviewer1
sudo htpasswd    /etc/nginx/htpasswd/tt-hack reviewer2

# nginx: вставить location-файл в server-блок домена превью
sudo nginx -t && sudo systemctl reload nginx
```

Обновление превью — `git pull` в `/opt/tt-hack` и
`sudo systemctl restart tt-hack-vibe-debug`. Данные ревью лежат в
`/opt/tt-hack-review/` и деплоем не затрагиваются.

Логин из Basic Auth уходит в `X-Review-User` и становится `author` комментария —
поле формой не подменяется.

> Дай доступ к серверу и домен превью — допишу location под ваш конфиг Nginx и
> подниму сервис.

## Когда появится фронтенд

Положить его в `preview/` (или указать `VIBE_DEBUG_ROOT` на его сборку) и
подключить на каждой странице:

```html
<link rel="stylesheet" href="/assets/vibe-debug.css" />
<script src="/assets/vibe-debug.js" defer></script>
```

Для осмысленного `target` в комментариях желательно проставлять на блоках
стабильные `id` или `data-*`-атрибуты.

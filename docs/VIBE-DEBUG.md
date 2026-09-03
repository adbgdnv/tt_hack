# vibe-debug — запуск и деплой

Каркас визуального ревью через коммент-превью, портирован из проекта `lapki`
целиком: режимы `view` / `dev` / `vibe`, пины, карандаш и рамка, скриншоты,
общая очередь. Операционка — `docs/VIBE-DEBUG-RUNBOOK.md`, конвейер
комментарий→задача — `docs/REVIEW-TO-TASK.md`, скилл — `.claude/skills/vibe-debug/`.

Продуктового фронтенда ещё нет — под ревью стоит каркас-заглушка «Проверка
контрагента» в `preview/*.html` (index, report, mcp).

## Состав

| Путь | Что это |
|------|---------|
| `scripts/vibe_debug_server.py` | Статика + review API. Python 3.10+, только stdlib. |
| `scripts/review_schema.py` | Валидатор схемы (подмножество JSON Schema, без зависимостей). |
| `scripts/audit_vibe_debug_data.py` | Read-only аудит очереди и вложений. |
| `scripts/review_triage.py` | Карточки разбора из очереди. |
| `schemas/vibe-debug-comment.schema.json` | Единственная схема DBG-записи. |
| `tests/test_vibe_debug_server.py` | Регрессия схемы и хранилищ. |
| `preview/` | Корень статики: каркас-заглушка + оверлей. |
| `preview/assets/vibe-debug.{js,css}` | Клиент ревью (verbatim из lapki). |
| `preview/assets/wire.css` | Стили каркаса превью. |
| `deploy/` | systemd-юнит и конфиг nginx. |

## Локальный запуск

```bash
python3 scripts/vibe_debug_server.py
```

`http://127.0.0.1:8788/`. Данные — `.vibe-debug/` (в git не коммитится).
Тесты: `python3 -m unittest discover -s tests`.

Переменные окружения:

| Переменная | По умолчанию | Назначение |
|-----------|--------------|------------|
| `VIBE_DEBUG_HOST` | `127.0.0.1` | адрес прослушивания |
| `VIBE_DEBUG_PORT` | `8788` | порт |
| `VIBE_DEBUG_ROOT` | `preview/` | корень статики |
| `VIBE_DEBUG_DATA` | `.vibe-debug/comments.json` | файл комментариев |
| `VIBE_DEBUG_MARKS` | рядом с DATA | файл графических пометок |
| `VIBE_DEBUG_ATTACHMENTS` | рядом с DATA | каталог скриншотов |

API (GET — чтение, POST — запись) перечислён в `docs/VIBE-DEBUG-RUNBOOK.md`.

## Общий превью-сервер (основной режим, как в lapki)

Локальный запуск — только для отладки самого оверлея. Ревью команда ведёт на
одном общем сервере: комментарии переживают перезапуск и видны всем
авторизованным участникам. Превью закрыто Nginx Basic Auth; `.htpasswd`,
пароли и хэши в репозиторий не коммитятся.

Готовые шаблоны:

- `deploy/systemd/tt-hack-vibe-debug.service`
- `deploy/nginx/tt-hack-review.conf`

### Текущий инстанс

| | |
|---|---|
| Сервер | `72.56.16.44`, Ubuntu 24.04 |
| Домен | `tt-hack-review.72.56.16.44.sslip.io` (sslip.io → wildcard DNS на IP, домен не покупался) |
| URL | `https://tt-hack-review.72.56.16.44.sslip.io/` |
| Код | `/opt/tt-hack` (`git pull` для обновления) |
| Данные ревью | `/opt/tt-hack-review/` (вне репозитория, деплой не трогает) |
| Сервис | `systemctl {status,restart} tt-hack-vibe-debug` |
| Логины | `dbndrnk`, `poulyak`, `adbgdnv` (пароли — в `/etc/nginx/htpasswd/tt-hack` на сервере) |

### Развёртывание с нуля

```bash
sudo apt update && sudo apt install -y nginx apache2-utils certbot python3-certbot-nginx

sudo mkdir -p /opt/tt-hack-review
sudo git clone https://github.com/adbgdnv/tt_hack.git /opt/tt-hack
sudo chown -R www-data:www-data /opt/tt-hack /opt/tt-hack-review

# сервис
sudo cp /opt/tt-hack/deploy/systemd/tt-hack-vibe-debug.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now tt-hack-vibe-debug

# доступ
sudo mkdir -p /etc/nginx/htpasswd
sudo htpasswd -bc /etc/nginx/htpasswd/tt-hack dbndrnk 'ПАРОЛЬ'
sudo htpasswd -b  /etc/nginx/htpasswd/tt-hack poulyak 'ПАРОЛЬ'
sudo htpasswd -b  /etc/nginx/htpasswd/tt-hack adbgdnv 'ПАРОЛЬ'

# nginx
sudo cp /opt/tt-hack/deploy/nginx/tt-hack-review.conf /etc/nginx/sites-available/
sudo ln -sf /etc/nginx/sites-available/tt-hack-review.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# HTTPS (Let's Encrypt через sslip.io-домен)
sudo certbot --nginx -d tt-hack-review.72.56.16.44.sslip.io --non-interactive --agree-tos -m dbndrnk@example.com --redirect
```

Обновление превью — `cd /opt/tt-hack && sudo git pull && sudo systemctl restart tt-hack-vibe-debug`.

Логин из Basic Auth уходит в `X-Review-User` и становится `author` комментария —
поле формой не подменяется.

## Когда появится продуктовый фронтенд

Положить сборку в `preview/` (или указать `VIBE_DEBUG_ROOT` на неё) и подключить
на каждой странице:

```html
<script src="/assets/vibe-debug.js?v=20260828-vibe21" defer></script>
```

`vibe-debug.js` сам подтянет `/assets/vibe-debug.css`. Для осмысленного `target`
блоки желательно оборачивать в `<section>` с `<span class="section__id">` либо
давать стабильные `id` / `data-*` — по ним `dev`-инспектор строит `data-debug-id`
и человекочитаемые подписи.

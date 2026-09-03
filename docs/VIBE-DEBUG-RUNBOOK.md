# Vibe Debug — ранбук

`vibe-debug` поднимает каркасы превью с общей панелью комментариев. Записи
сохраняются между перезапусками и видны всем авторизованным участникам.
Портирован из проекта `lapki`; развёртывание этого инстанса — `docs/VIBE-DEBUG.md`.

## Контуры

- `local` — обычная разработка, без общих данных;
- `test` / `debug` — общий сервер `https://tt-hack-review.72.56.16.44.sslip.io/`
  за Nginx Basic Auth; используется для всех проверок до появления прод-контура;
- `production` — только после явного подтверждения в текущем запросе.

Пользователи ревью: `dbndrnk`, `poulyak`, `adbgdnv`. Пароли и хэши хранятся
только на сервере (`/etc/nginx/htpasswd/tt-hack`); `.htpasswd`, пароли и токены
коммитить запрещено.

## Запуск

Локально из корня проекта:

```bash
python3 scripts/vibe_debug_server.py
```

Адрес: `http://127.0.0.1:8788/`. Данные — `.vibe-debug/comments.json`,
`.vibe-debug/marks.json`, `.vibe-debug/attachments/` (каталог в `.gitignore`).

Общий сервер: код в `/opt/tt-hack`, сервис `tt-hack-vibe-debug`, данные в
`/opt/tt-hack-review/` — этот каталог не перезаписывать при выкладке.

Вызов `/vibe-debug` означает:

1. если превью не запущено — запустить и дать URL;
2. если запущено — дать роут на нужную страницу/блок;
3. если передан комментарий — сохранить с автором, страницей, селектором,
   описанием ближайшего блока, viewport и временем.

Оверлей подключается на каждой странице `preview/` напрямую:

```html
<link rel="stylesheet" href="/assets/wire.css">
<script src="/assets/vibe-debug.js?v=20260828-vibe21" defer></script>
```

`vibe-debug.js` сам подтягивает `/assets/vibe-debug.css`. Общего загрузчика
(как `wire.js` в lapki) здесь нет.

## Режимы интерфейса

- `view` — стартовый режим при каждой загрузке: обычный просмотр без inspector,
  cursor-comment, пинов и пометок. Иконка списка открывает read-only очередь
  комментариев со всех маршрутов превью; счётчик — все активные записи. Карточка
  ведёт на `ROUTE?vibe-comment=DBG-ID`, прокручивает к сохранённому selector и
  временно обводит объект. Если selector устарел — карточка открывается и
  сообщает, что блок не найден. Ссылка нативная: работает история, Cmd/Ctrl-клик,
  новая вкладка.
- `dev` — инспектор структуры сразу, без отдельной кнопки: точный вложенный
  DOM-элемент, переход родитель/потомок, breadcrumb, устойчивый CSS-селектор,
  список и статусы. `data-debug-id` проставляется автоматически по `.section__id`,
  заголовку или `id` блока.
- `vibe` — визуальное ревью: комментарии остаются пинами в сохранённой точке
  объекта и открываются карточкой рядом. Инструмент комментария использует синий
  cursor-comment: клик фиксирует точку и DOM-объект без dev-подсветки.
- Карандаш и рамка доступны в `vibe`. Карандаш рисует на едином canvas всей
  страницы (`selector: :root`) и пересекает границы блоков; рамка привязана к
  выбранному DOM-объекту. Цвет и толщина — в панели.
- Штрих и рамку можно выбрать, перетащить, сдвинуть стрелками и удалить кнопкой
  или `Delete`; каждое перемещение обновляет `geometry` и `history` в JSON.
- `Cmd+Z` / `Ctrl+Z` вне полей ввода отменяет последнее создание, удаление или
  перемещение пометки. В `input`, `textarea`, `select`, `contenteditable` —
  нативная отмена набора.
- Панель по умолчанию справа, перетаскивается за grip, фон и края. Позиция,
  псевдоним, цвет и толщина — в `localStorage` браузера; режим при загрузке
  всегда `view`. Общие — комментарии и пометки.
- У карточек списка в `dev` и `vibe` есть крестик удаления: он безвозвратно
  удаляет комментарий через review API вместе с пином. Очередь `view` —
  read-only, без удаления и смены статуса.
- В формах `dev` и `vibe` скриншот выбирается файлом или вставляется из буфера
  прямо в поле. В позицию курсора добавляется `[скриншот#ID]`; PNG, JPEG, WebP
  до 8 МБ, максимум шесть на комментарий. Подсказка вставки — по `userAgent`:
  `⌘V` на Apple, `Ctrl+V` иначе.

## Комментарий

Схема одна: `schemas/vibe-debug-comment.schema.json`. Её пишет
`normalize_comment()` в `scripts/vibe_debug_server.py`, проверяет
`scripts/review_schema.py`, гоняют `scripts/audit_vibe_debug_data.py` и тест
`test_stored_comment_matches_published_schema`. Ни этот документ, ни SKILL
своего перечня полей не держат — менять схему значит менять сервер, схему и
тест одним коммитом.

Пример полной записи:

```json
{
  "id": "DBG-001",
  "status": "new",
  "createdAt": "2026-09-03T12:00:00Z",
  "updatedAt": "2026-09-03T12:00:00Z",
  "author": "dbndrnk",
  "displayAuthor": "Даша",
  "text": "Плашку риска сделать заметнее [скриншот#A1B2C3D4E5]",
  "mode": "vibe",
  "route": "/report.html",
  "selector": "main > section:nth-of-type(2)",
  "page": {
    "route": "/report.html",
    "title": "Отчёт по контрагенту",
    "url": "https://tt-hack-review.72.56.16.44.sslip.io/report.html"
  },
  "target": {
    "selector": "main > section:nth-of-type(2)",
    "element": "section",
    "sectionId": "s-risks",
    "heading": "Что нашёл агент",
    "label": "Что нашёл агент",
    "excerpt": "Массовый адрес регистрации…"
  },
  "anchor": {
    "x": 0.45, "y": 0.3, "offsetX": 120, "offsetY": 48,
    "targetWidth": 640, "targetHeight": 160
  },
  "viewport": { "width": 1440, "height": 900 },
  "attachments": [
    {
      "id": "A1B2C3D4E5",
      "token": "[скриншот#A1B2C3D4E5]",
      "filename": "report.png",
      "mimeType": "image/png",
      "size": 183204,
      "width": 1440,
      "height": 900,
      "url": "/__review__/attachments/A1B2C3D4E5.png"
    }
  ],
  "history": [
    { "at": "2026-09-03T12:00:00Z", "by": "dbndrnk", "action": "created", "status": "new" }
  ]
}
```

На общем сервере автор берётся из Nginx Basic Auth (`X-Review-User`), пишется
в `author` и формой не подменяется. Видимое имя (`displayAuthor`) хранится
локально в браузере и меняется перед комментарием.

Скриншоты — отдельными файлами в `attachments/`, в `comments.json` остаётся
AI-ready словарь (ID, token, URL, тип, размер, размеры изображения). Удаление
комментария удаляет и связанные файлы.

Графические пометки — в `marks.json`: `kind` (`stroke` / `rectangle`), `page`,
полный `target`, `style.color`, `style.thickness`, `geometry` в системе
`target-relative` (массив точек для карандаша, `bounds` для рамки). Есть
`updatedAt` и `history`; перемещение добавляет `geometry_changed`.

Статусы: `new` → `approved` → `in_progress` → `resolved`; `wont_fix` — для
сознательно отклонённых. `resolved` — только после проверки результата.

Записи до текущей схемы не содержат `mode`, `displayAuthor`, `anchor`,
`attachments`, `updatedAt`. Аудит помечает их предупреждением и не переписывает.

Как комментарий превращается в задачу — `docs/REVIEW-TO-TASK.md`. Сам по себе
комментарий правку не запускает.

## Карта реализации и API

```text
preview/assets/vibe-debug.js       режимы, комментарии, deep links, marks
preview/assets/vibe-debug.css      изолированный интерфейс review
preview/assets/wire.css            стили каркаса превью
preview/*.html                     страницы-заглушки под ревью
scripts/vibe_debug_server.py       HTTP API, атомарные JSON stores
scripts/review_schema.py           подмножество JSON Schema без зависимостей
scripts/audit_vibe_debug_data.py   read-only аудит JSON и attachments
scripts/review_triage.py           карточки разбора из очереди
tests/test_vibe_debug_server.py    регрессия схемы и store operations
.vibe-debug/                       локальные данные, вне Git
/opt/tt-hack-review/               общие данные сервера, не перезаписывать
```

Чтение не меняет данные:

```text
GET /__review__/session
GET /__review__/comments
GET /__review__/comments?route=/report.html
GET /__review__/marks?route=/report.html
GET /__review__/attachments/FILE
```

Запись — только из интерфейса или по явному запросу пользователя:

```text
POST /__review__/comments
POST /__review__/comments/status
POST /__review__/comments/delete
POST /__review__/attachments
POST /__review__/attachments/delete
POST /__review__/marks
POST /__review__/marks/update
POST /__review__/marks/delete
```

Для обновления UI меняются `vibe-debug.js` / `vibe-debug.css`, затем
повышается `?v=` в тегах `<script>` страниц `preview/`. Выкладка `preview/`
не должна затрагивать `/opt/tt-hack-review/`.

## Read-only аудит очереди

Локально:

```bash
python3 scripts/audit_vibe_debug_data.py \
  --comments .vibe-debug/comments.json \
  --attachments .vibe-debug/attachments
```

На сервере — тот же скрипт с путями `/opt/tt-hack-review/comments.json` и
`/opt/tt-hack-review/attachments`.

Скрипт только читает. Проверяет уникальность ID, обязательный AI-ready контекст,
допустимые статусы, screenshot token, наличие и размер каждого файла, сообщает
orphan attachments. Код `0` — ошибок нет; legacy-записи без `anchor` или с
`attachments: null` — предупреждение, не переписываются.

## Обработка

Полный конвейер и формат карточки — `docs/REVIEW-TO-TASK.md`. Коротко:

1. Разработчик или заказчик выбирает страницу/блок и оставляет комментарий.
2. Разбор: комментарий классифицируется и попадает карточкой в
   `docs/review/<дата>-<область>.md`. Правку это не запускает.
3. Человек пишет в карточке строку `Решение:`. До неё исполнитель не работает.
4. Исполнитель берёт промпт из карточки, переводит комментарий в `in_progress`,
   создаёт ветку и правит.
5. Исправление показывается на localhost или на общем сервере.
6. После проверки — `resolved`; ссылка и smoke-check фиксируются в PR.
7. Закрытие комментария не даёт права на production deploy.

## Минимальная проверка

- нужный URL открывается без ошибок в консоли;
- комментарии доступны авторизованному пользователю и не видны гостю;
- JSON комментария содержит `page`, `target`, `anchor`, `viewport`, `history`,
  `author`, `displayAuthor`, режим, текст, `attachments`; token каждого
  изображения присутствует в тексте;
- JSON пометки содержит `page`, `target`, `style`, `geometry`, `author`,
  `displayAuthor`;
- два разных пользователя видят общий список, автор определяется корректно;
- `view` показывает записи со всех маршрутов, active badge совпадает с JSON,
  ссылка карточки открывает нужную страницу и блок;
- проверены mobile, tablet, desktop;
- `python3 -m unittest discover -s tests` зелёный, если трогали сервер/схему;
- при test/prod проверены SSL, логи и rollback.

## Отчёт

Каждый запуск заканчивается коротким отчётом: контур, URL, обработанные ID,
изменённые файлы, smoke-check, известные проблемы, следующий шаг.

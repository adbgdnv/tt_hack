# Quickstart: проверка автодеплоя превью

Прогоняется после реализации. Доказывает US1–US3 и ключевые FR.

## Предусловия

- Первичная настройка сервера выполнена (см. `deploy/PREVIEW-DEPLOY.md`): пользователь
  `ttdeploy`, `releases/`, симлинк `current`, `bin/`, публичный ключ в `authorized_keys`.
- Секреты в репозитории: `DEPLOY_SSH_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_KNOWN_HOSTS`,
  `PREVIEW_BASIC_AUTH`.
- PR фичи смержен в `main` (иначе `workflow_run` для `deploy.yml` не существует).

## Сценарий 1 — авто-публикация по push в main (US1)

1. В ветке от `main` изменить видимый текст в `preview/index.html`, открыть PR, дождаться
   зелёного CI, смержить.
2. Открыть вкладку **Actions** → workflow **Deploy preview** запустился по завершении **CI**.
3. Дождаться завершения (ожидаемо < 10 мин от мержа — SC-001).
4. Открыть `https://tt-hack-review.72.56.16.44.sslip.io/` под Basic Auth → виден новый текст.
5. На сервере: `readlink /opt/tt-hack-preview/current` → каталог `releases/<свежий timestamp>-<sha>`.
6. `ls /opt/tt-hack-review/` — mtime не изменился; `systemctl status tt-hack-vibe-debug` —
   `active (running)`, без рестарта (FR-005).

**Ожидание:** шаги 4–6 проходят. Job summary содержит коммит, `web: skipped (no package.json)`,
`200 /`, `200 /report.html`, `200 /mcp.html`, `deployed <id>`.

## Сценарий 2 — сборка src/web (US1, FR-002)

1. Добавить в `src/web/` минимальный Vite-проект (`package.json`, `index.html`, `src/main.ts`),
   смержить в `main`.
2. Job **Deploy preview** → шаг setup-node + `npm ci && npm run build` отработал.
3. `https://…sslip.io/` отдаёт собранный фронт; `curl -u … https://…/report.html` → всё ещё
   `200` (каркасы `preview/` на месте).
4. Job summary: `web: built`.

## Сценарий 3 — провал безопасен (US2)

**3a. Красный CI:**
1. Смержить коммит, ломающий `ruff` (например, неиспользуемый импорт в `scripts/`).
2. CI красный → **Deploy preview** job `skipped`. `readlink /opt/tt-hack-preview/current` не изменился.

**3b. Провал smoke-check:**
1. Временно испортить пароль в `~ttdeploy/.preview-smoke-auth` на сервере, запустить **Deploy preview**
   вручную (`workflow_dispatch`).
2. rsync прошёл, switch произошёл, smoke `401` → скрипт откатил симлинк на предыдущий релиз,
   job красный, в логе `smoke failed: 401 /`.
3. `https://…sslip.io/` отдаёт прежнюю рабочую версию (FR-007, SC-003).
4. Вернуть пароль в секрете.

## Сценарий 4 — ручной откат (US3)

1. На сервере под `ttdeploy`: `PREVIEW_ROOT=/opt/tt-hack-preview /opt/tt-hack-preview/bin/preview_rollback.sh --list` — показывает релизы и
   текущий.
2. `PREVIEW_ROOT=/opt/tt-hack-preview /opt/tt-hack-preview/bin/preview_rollback.sh --local` — переключает на предыдущий.
3. Засечь время: от команды до рабочего превью < 2 мин (SC-004), фактически секунды.
4. `PREVIEW_ROOT=/opt/tt-hack-preview /opt/tt-hack-preview/bin/preview_rollback.sh --local` ещё раз без предыдущего → `exit 3`,
   «откатываться не на что», симлинк цел.
5. Смержить новый валидный коммит → автодеплой публикует поверх отката (FR-011).

## Сценарий 5 — ручная выкладка как запасной путь (FR-010, SC-007)

1. Участник, не настраивавший автодеплой, по инструкции из `deploy/PREVIEW-DEPLOY.md`:
   `ssh ttdeploy@<host>`, `cd /opt/tt-hack && git pull --ff-only && PREVIEW_ROOT=/opt/tt-hack-preview scripts/preview_deploy.sh --local`.
2. Превью обновилось, smoke зелёный.

## Сценарий 6 — два мержа подряд (edge case)

1. Смержить два PR в `main` в течение минуты.
2. **Actions**: два прогона **Deploy preview**, второй ждёт первого (concurrency
   `preview-deploy`), не отменяя.
3. Итог: `readlink /opt/tt-hack-preview/current` → релиз второго (последнего) коммита. Файлы не перемешаны.

## Чек-лист приёмки

- [ ] Сценарий 1: авто-публикация < 10 мин, чужое не тронуто
- [ ] Сценарий 2: `src/web` собирается, каркасы остаются
- [ ] Сценарий 3a: красный CI не публикует
- [ ] Сценарий 3b: провал smoke → откат, старая версия жива
- [ ] Сценарий 4: откат < 2 мин, «не на что» обрабатывается
- [ ] Сценарий 5: ручная выкладка по инструкции работает
- [ ] Сценарий 6: параллельные выкладки сериализованы
- [ ] Секретов нет в логах job (просмотреть вывод)

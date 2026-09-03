# Автодеплой превью — ранбук

Как превью общего сервера обновляется по push в `main`, как выложить руками и как
откатиться. Спека и решения — `specs/001-preview-autodeploy/`.

## Раскладка на сервере

```
/opt/tt-hack/            git-клон репозитория, как сейчас (нужен vibe-debug и ручной выкладке)
/opt/tt-hack-review/     данные ревью — автодеплой НЕ трогает
/opt/tt-hack-preview/    артефакты автодеплоя (создаётся при настройке)
├── current   → symlink → releases/<UTC>-<sha>      ← Nginx root смотрит сюда
├── releases/<UTC>-<sha>/                            ← максимум 5
└── bin/       preview_*.sh, CI синкает сюда перед финализацией
```

Источник (`/opt/tt-hack`) и артефакты (`/opt/tt-hack-preview`) разведены: `git pull`
на сервере автодеплою не нужен, а git-tracked `preview/` не конфликтует с симлинком.

## Что происходит

```
push → main
  └─ CI (ruff + pytest + shellcheck)  ──✅──▶  workflow "Deploy preview"
        ├─ [если есть src/web/package.json] npm ci && npm run build
        ├─ staging = src/web/dist/ + preview/   (при коллизии имя из preview/ выигрывает)
        ├─ rsync staging ──ssh ttdeploy──▶ /opt/tt-hack-preview/releases/<UTC>-<sha>/
        ├─ rsync scripts/preview_*.sh ──▶ /opt/tt-hack-preview/bin/
        └─ ssh: bin/preview_deploy.sh --finalize <id>
              ├─ mv -T симлинка /opt/tt-hack-preview/current → релиз   (атомарно)
              ├─ smoke: curl 200  /  /report.html  /mcp.html
              │     └─ ✗ → откат симлинка на предыдущий релиз, job красный
              └─ оставить 5 релизов, старые удалить
```

Красный CI → job `Deploy preview` пропускается, на сервере ничего не меняется.
Автодеплой **не трогает** `/opt/tt-hack-review/`, сервис `tt-hack-vibe-debug`,
контейнеры `api`/`mcp`, git-клон `/opt/tt-hack`.

---

## Первичная настройка сервера (один раз, root)

```bash
# 1. Пользователь автодеплоя — без sudo
useradd -m -s /bin/bash ttdeploy

# 2. Каталог артефактов
mkdir -p /opt/tt-hack-preview/releases /opt/tt-hack-preview/bin
chown -R ttdeploy:ttdeploy /opt/tt-hack-preview

# 3. Первый релиз из текущей статики + симлинк current
cp -a /opt/tt-hack/preview/. /opt/tt-hack-preview/releases/00000000T000000Z-initial/
ln -sfn /opt/tt-hack-preview/releases/00000000T000000Z-initial /opt/tt-hack-preview/current
chown -R ttdeploy:ttdeploy /opt/tt-hack-preview/releases
chown -h ttdeploy:ttdeploy /opt/tt-hack-preview/current

# 4. Nginx: root → симлинк current (одна строка в tt-hack-review.conf), затем reload
#    было:  root /opt/tt-hack/preview;
#    стало: root /opt/tt-hack-preview/current;
sed -i 's#root /opt/tt-hack/preview;#root /opt/tt-hack-preview/current;#' \
  /etc/nginx/sites-available/tt-hack-review
nginx -t && systemctl reload nginx

# 5. Логин:пароль Basic Auth для smoke-check — только на сервере, не в GitHub.
#    Любой валидный из /etc/nginx/htpasswd/tt-hack (например свой).
printf 'REVIEW_USER:REVIEW_PASSWORD' > /home/ttdeploy/.preview-smoke-auth
chown ttdeploy:ttdeploy /home/ttdeploy/.preview-smoke-auth
chmod 600 /home/ttdeploy/.preview-smoke-auth

# 6. Публичный деплой-ключ (см. ниже) → authorized_keys
install -d -m 700 -o ttdeploy -g ttdeploy /home/ttdeploy/.ssh
printf 'ssh-ed25519 AAAA... ttdeploy@tt-hack-autodeploy\n' > /home/ttdeploy/.ssh/authorized_keys
chown ttdeploy:ttdeploy /home/ttdeploy/.ssh/authorized_keys
chmod 600 /home/ttdeploy/.ssh/authorized_keys

# 7. Для ручной выкладки (--local): ttdeploy должен читать git-клон и его собирать
chown -R ttdeploy:ttdeploy /opt/tt-hack/scripts
# (полный git pull под ttdeploy не нужен — это делает тот, кто обычно тянет репозиторий)

# 8. Проверка
sudo -u ttdeploy curl -sS -o /dev/null -w '%{http_code}\n' \
  -u "$(cat /home/ttdeploy/.preview-smoke-auth)" \
  https://tt-hack-review.72.56.16.44.sslip.io/
```

Сгенерировать пару ключей (на своей машине):

```bash
ssh-keygen -t ed25519 -N '' -C ttdeploy@tt-hack-autodeploy -f ./tt-hack-deploy
#   tt-hack-deploy      → секрет DEPLOY_SSH_KEY
#   tt-hack-deploy.pub  → шаг 6 выше
ssh-keyscan -H -t rsa,ecdsa,ed25519 72.56.16.44 | grep -v '^#'   # → секрет DEPLOY_KNOWN_HOSTS
```

---

## Секреты репозитория

`Settings → Secrets and variables → Actions`:

| Секрет | Что | Как получить |
|---|---|---|
| `DEPLOY_SSH_KEY` | приватный ключ пары деплоя | `ssh-keygen` выше, файл `tt-hack-deploy` целиком |
| `DEPLOY_HOST` | адрес сервера | `72.56.16.44` |
| `DEPLOY_USER` | пользователь деплоя | `ttdeploy` |
| `DEPLOY_KNOWN_HOSTS` | отпечаток хоста | вывод `ssh-keyscan` выше |

```bash
gh secret set DEPLOY_SSH_KEY     < tt-hack-deploy
gh secret set DEPLOY_HOST        --body '72.56.16.44'
gh secret set DEPLOY_USER        --body 'ttdeploy'
gh secret set DEPLOY_KNOWN_HOSTS < <(ssh-keyscan -H -t rsa,ecdsa,ed25519 72.56.16.44 | grep -v '^#')
```

Basic Auth для smoke-check в GitHub **не хранится** — он на сервере в
`~ttdeploy/.preview-smoke-auth` (шаг 5). Так секрет ближе к месту использования и
не передаётся по ssh.

Приватные ключи и пароли в репозиторий не коммитить.

---

## Ручная выкладка (запасной путь)

С сервера под `ttdeploy`, из git-клона:

```bash
ssh ttdeploy@72.56.16.44
cd /opt/tt-hack && git pull --ff-only          # обновить исходники
PREVIEW_ROOT=/opt/tt-hack-preview scripts/preview_deploy.sh --local
```

`--local` = собрать (если есть `src/web/package.json` — нужен `npm` на сервере) →
положить релиз в `/opt/tt-hack-preview/releases/` → атомарно переключить `current`
→ smoke → почистить старые.

Предпросмотр без изменений: `... scripts/preview_deploy.sh --local --dry-run`.

---

## Откат

С сервера под `ttdeploy`:

```bash
export PREVIEW_ROOT=/opt/tt-hack-preview
BIN=/opt/tt-hack-preview/bin        # или /opt/tt-hack/scripts из клона
$BIN/preview_rollback.sh --list                     # релизы и текущий
$BIN/preview_rollback.sh --local                    # на предыдущий по времени
$BIN/preview_rollback.sh --to 20260903T140502Z-1a2b3c4   # на конкретный
```

Переключение симлинка — миллисекунды; цель — рабочее превью меньше чем за 2 минуты
от решения. После отката следующий push в `main` публикуется штатно поверх.

Если предыдущего релиза нет (первая выкладка) — `preview_rollback.sh` выйдет с
кодом 3 и ничего не тронет.

---

## Диагностика

| Симптом | Причина / что делать |
|---|---|
| `Deploy preview` не запускается после мержа | `deploy.yml` должен быть в `main`. Первый прогон — только после мержа PR с фичей |
| job `skipped` | CI на этом коммите красный (это by design) или `if`-гард не прошёл |
| `Host key verification failed` | протух `DEPLOY_KNOWN_HOSTS` — перегенерировать `ssh-keyscan` |
| `Permission denied (publickey)` | публичный ключ не в `~ttdeploy/.ssh/authorized_keys` или права не `600`/`700` |
| `rsync: mkdir ... failed: Permission denied` | `ttdeploy` не владелец `/opt/tt-hack-preview` — см. шаги 2–3 |
| Nginx отдаёт `404` после настройки | `root` не поменяли на `/opt/tt-hack-preview/current` или не сделали `reload` (шаг 4) |
| `smoke провален — откат` | новый релиз отдал не `200`. Проверить сборку, `~ttdeploy/.preview-smoke-auth`, htpasswd Nginx, доступность своего же публичного URL с сервера |
| `src/web: сборка не дала dist/` | Vite пишет не в `dist/` — поправить `build.outDir` или скрипт |
| `npm ci` падает `lock file ... not found` | в `src/web` нет `package-lock.json` — закоммитить его вместе с `package.json` (после этого в `deploy.yml` можно вернуть `cache: npm`) |
| `mv: invalid option -- 'T'` при `--local` на своей машине | скрипты рассчитаны на Linux (GNU coreutils); запускать на сервере/раннере |

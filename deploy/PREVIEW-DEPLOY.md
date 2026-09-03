# Автодеплой превью — ранбук

Как превью общего сервера обновляется по push в `main`, как выложить руками и как
откатиться. Спека и решения — `specs/001-preview-autodeploy/`.

## Что происходит

```
push → main
  └─ CI (ruff + pytest + shellcheck)  ──✅──▶  workflow "Deploy preview"
        ├─ [если есть src/web/package.json] npm ci && npm run build
        ├─ собрать staging = src/web/dist/ + preview/  (при коллизии имя из preview/ выигрывает)
        ├─ rsync staging ──ssh ttdeploy──▶ /opt/tt-hack/releases/<UTC>-<sha>/
        └─ ssh: git pull && preview_deploy.sh --finalize <id>
              ├─ mv -T симлинка /opt/tt-hack/preview → новый релиз   (атомарно)
              ├─ smoke: curl 200  /  /report.html  /mcp.html
              │     └─ ✗ → откат симлинка на предыдущий релиз, job красный
              └─ оставить 5 релизов, старые удалить
```

Красный CI → job `Deploy preview` пропускается, на сервере ничего не меняется.

Автодеплой **не трогает** `/opt/tt-hack-review/` (данные ревью), сервис
`tt-hack-vibe-debug` и контейнеры `api`/`mcp`.

---

## Первичная настройка сервера (один раз, root)

```bash
# 1. Пользователь автодеплоя — без sudo
useradd -m -s /bin/bash ttdeploy

# 2. Каталог релизов
mkdir -p /opt/tt-hack/releases
chown -R ttdeploy:ttdeploy /opt/tt-hack/releases

# 3. Текущую статику превратить в первый релиз
mv /opt/tt-hack/preview /opt/tt-hack/releases/00000000T000000Z-initial
ln -sfn /opt/tt-hack/releases/00000000T000000Z-initial /opt/tt-hack/preview
chown -h ttdeploy:ttdeploy /opt/tt-hack/preview

# 4. Дать ttdeploy обновлять git-клон (для ssh --finalize и ручной выкладки)
chown -R ttdeploy:ttdeploy /opt/tt-hack/.git /opt/tt-hack/scripts

# 5. Логин:пароль Basic Auth для smoke-check — только на сервере, не в GitHub
printf 'REVIEW_USER:REVIEW_PASSWORD' > /home/ttdeploy/.preview-smoke-auth
chown ttdeploy:ttdeploy /home/ttdeploy/.preview-smoke-auth
chmod 600 /home/ttdeploy/.preview-smoke-auth

# 6. Публичный деплой-ключ (см. ниже) → authorized_keys
install -d -m 700 -o ttdeploy -g ttdeploy /home/ttdeploy/.ssh
printf 'ssh-ed25519 AAAA... deploy@tt-hack\n' > /home/ttdeploy/.ssh/authorized_keys
chown ttdeploy:ttdeploy /home/ttdeploy/.ssh/authorized_keys
chmod 600 /home/ttdeploy/.ssh/authorized_keys

# 7. Проверить, что Nginx отдаёт через симлинк (disable_symlinks off — дефолт)
curl -sS -o /dev/null -w '%{http_code}\n' -u REVIEW_USER:REVIEW_PASSWORD \
  https://tt-hack-review.72.56.16.44.sslip.io/
```

`deploy/nginx/tt-hack-review.conf` менять **не нужно** — `root /opt/tt-hack/preview;`
уже указывает на путь, который теперь стал симлинком.

Сгенерировать пару ключей (на своей машине):

```bash
ssh-keygen -t ed25519 -N '' -C deploy@tt-hack -f ./tt-hack-deploy
#   tt-hack-deploy      → секрет DEPLOY_SSH_KEY
#   tt-hack-deploy.pub  → шаг 6 выше
ssh-keyscan -H 72.56.16.44   # → секрет DEPLOY_KNOWN_HOSTS
```

---

## Секреты репозитория

`Settings → Secrets and variables → Actions`:

| Секрет | Что | Как получить |
|---|---|---|
| `DEPLOY_SSH_KEY` | приватный ключ пары деплоя | `ssh-keygen` выше, файл `tt-hack-deploy` целиком |
| `DEPLOY_HOST` | адрес сервера | `72.56.16.44` |
| `DEPLOY_USER` | пользователь деплоя | `ttdeploy` |
| `DEPLOY_KNOWN_HOSTS` | отпечаток хоста | вывод `ssh-keyscan -H 72.56.16.44` |

```bash
gh secret set DEPLOY_SSH_KEY     < tt-hack-deploy
gh secret set DEPLOY_HOST        --body '72.56.16.44'
gh secret set DEPLOY_USER        --body 'ttdeploy'
gh secret set DEPLOY_KNOWN_HOSTS < <(ssh-keyscan -H 72.56.16.44)
```

Basic Auth для smoke-check в GitHub **не хранится** — он на сервере в
`~ttdeploy/.preview-smoke-auth` (шаг 5). Так секрет ближе к месту использования и
не передаётся по ssh.

Приватные ключи и пароли в репозиторий не коммитить.

---

## Ручная выкладка (запасной путь)

Тот же скрипт, что в CI. С сервера под `ttdeploy`:

```bash
ssh ttdeploy@72.56.16.44
cd /opt/tt-hack
git pull --ff-only
scripts/preview_deploy.sh --local
```

`--local` = собрать (если есть `src/web/package.json` — нужен `npm` на сервере) →
положить релиз → атомарно переключить → smoke → почистить старые.

Предпросмотр без изменений: `scripts/preview_deploy.sh --local --dry-run`.

---

## Откат

С сервера под `ttdeploy`:

```bash
cd /opt/tt-hack
scripts/preview_rollback.sh --list          # какие релизы есть, какой текущий
scripts/preview_rollback.sh --local         # на предыдущий по времени
scripts/preview_rollback.sh --to 20260903T140502Z-1a2b3c4   # на конкретный
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
| `Host key verification failed` | протух `DEPLOY_KNOWN_HOSTS` — перегенерировать `ssh-keyscan -H` |
| `Permission denied (publickey)` | публичный ключ не в `~ttdeploy/.ssh/authorized_keys` или права не `600`/`700` |
| `rsync: mkdir ... failed: Permission denied` | `ttdeploy` не владелец `/opt/tt-hack/releases` — см. шаг 2 |
| `smoke провален — откат` | новый релиз отдал не `200`. Проверить сборку, `~ttdeploy/.preview-smoke-auth`, htpasswd Nginx |
| `src/web: сборка не дала dist/` | Vite пишет не в `dist/` — поправить `build.outDir` или скрипт |
| `npm ci` падает `lock file ... not found` | в `src/web` нет `package-lock.json` — закоммитить его вместе с `package.json` (после этого в `deploy.yml` можно вернуть `cache: npm`) |
| `mv: invalid option -- 'T'` при `--local` на своей машине | скрипты рассчитаны на Linux (GNU coreutils); запускать на сервере/раннере |

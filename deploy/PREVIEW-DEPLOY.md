# Автодеплой превью — ранбук

Как превью общего сервера обновляется по push в `main`, как выложить руками и как
откатиться. Спека и решения — `specs/001-preview-autodeploy/`.

## Раскладка на сервере

```
/opt/tt-hack/            git-клон репозитория; из него собираются образы cc-api и cc-web
/opt/tt-hack-review/     данные ревью — автодеплой НЕ трогает
/opt/tt-hack-preview/    артефакты автодеплоя (создаётся при настройке)
├── current   → symlink → releases/<UTC>-<sha>      ← отсюда Nginx берёт оверлей ревью
├── releases/<UTC>-<sha>/                            ← максимум 5
└── bin/       preview_*.sh, CI синкает сюда перед финализацией
```

Источник (`/opt/tt-hack`) и артефакты (`/opt/tt-hack-preview`) разведены: `git pull`
на сервере автодеплою не нужен, а git-tracked `preview/` не конфликтует с симлинком.

**Сам фронтенд статикой здесь больше не лежит** — он в образе `cc-web`, Nginx
проксирует `/` в контейнер. Под симлинком остался только оверлей коммент-ревью
(`/assets/vibe-debug.*`): он не часть приложения, живёт в `preview/` и обновляется
без пересборки образа.

## Что происходит

```
push → main
  └─ CI (ruff + pytest + shellcheck)  ──✅──▶  workflow "Deploy preview"
        ├─ ssh: .env ──▶ /opt/tt-hack/.env
        ├─ ssh: sudo tt-hack-api-deploy   → docker compose build+up api,  ждёт /health
        ├─ ssh: sudo tt-hack-web-deploy   → docker compose build+up web,  ждёт / и /api/health
        │     └─ ✗ → откат на образ cc-web:previous, job красный
        └─ scripts/preview_deploy.sh --no-web   (оверлей ревью, без сборки фронта)
              ├─ staging = preview/
              ├─ rsync staging ──ssh ttdeploy──▶ /opt/tt-hack-preview/releases/<UTC>-<sha>/
              ├─ rsync scripts/preview_*.sh ──▶ /opt/tt-hack-preview/bin/
              └─ ssh: bin/preview_deploy.sh --finalize <id>
                    ├─ mv -T симлинка /opt/tt-hack-preview/current → релиз   (атомарно)
                    ├─ smoke: curl 200  /   (уже опубликованный фронт из образа)
                    │     └─ ✗ → откат симлинка на предыдущий релиз, job красный
                    └─ оставить 5 релизов, старые удалить
```

Красный CI → job `Deploy preview` пропускается, на сервере ничего не меняется.

Автодеплой выкатывает **и бэкенд, и фронт, оба контейнерами**: порядок шагов —
окружение → `api` → `web` → статика оверлея. Он по-прежнему **не трогает**
`/opt/tt-hack-review/`, сервис `tt-hack-vibe-debug` и контейнер `mcp`.

Сборка фронта переехала с раннера GitHub на сервер: артефакт выкладки — образ,
а не каталог со статикой, и собирается он там же, где запускается. Побочный
эффект: ошибка компиляции фронта теперь видна не в CI, а на шаге выкатки —
наружу она не выходит, потому что образ собирается до подмены контейнера.

---

## Бэкенд на сервере

Развёрнут 04.09.2026, **выкатывается автодеплоем** вместе с фронтом.

**Порядок в workflow важен: окружение → бэкенд → фронт.** Новый бэкенд шлёт поля,
которых старый фронт не знает, — тот их просто игнорирует. Обратный порядок уже
ронял страницу в белый экран: фронт с графиками уехал вперёд, сервер поля `charts`
не отдавал, и `.map` упал на `undefined`.

Выкатку делает `/usr/local/bin/tt-hack-api-deploy` — копия для истории лежит
в [deploy/bin/](bin/tt-hack-api-deploy). Рабочий экземпляр принадлежит root
и лежит вне git-клона: иначе право стало бы не узким, а полным root.

Разрешение выдано одной строкой в `/etc/sudoers.d/tt-hack-api`:

```
ttdeploy ALL=(root) NOPASSWD: /usr/local/bin/tt-hack-api-deploy
```

Скрипт ждёт ответа от `/health` до 40 секунд и валит деплой, если сервис
не поднялся: молча упавший бэкенд хуже старого работающего.

Устройство: контейнер `cc-api` слушает `127.0.0.1:8000`, наружу его отдаёт nginx
по префиксу `/api/` за той же basic-авторизацией, что и превью. Фронт собирается
с `VITE_API_BASE=/api` и ходит на тот же адрес: CORS не нужен, браузер переиспользует
уже введённые креды.

**Порт публикуется только на localhost.** На сервере `ufw` выключен, поэтому всё,
что забиндится на `0.0.0.0`, немедленно доступно из интернета — а в данных ФИО
и личные ИНН учредителей. Проверка после любого изменения:

```bash
ss -ltn | grep 8000                     # ожидается 127.0.0.1:8000, НЕ 0.0.0.0
curl -m 5 http://<IP>:8000/health       # ожидается отказ в соединении
```

### Первичная установка (один раз, root)

```bash
curl -fsSL https://get.docker.com | sh          # docker + compose plugin
git -C /opt/tt-hack pull --ff-only
chown -R www-data:www-data /opt/tt-hack         # в клоне были смешанные права
install -d -o www-data -g www-data -m 750 /opt/tt-hack/dataset
```

`docker-compose.yml` объявляет `env_file: .env`, а `.env` в репозиторий не коммитится —
**без него compose не стартует**.

Этот файл **пишет автодеплой** — шаг «Прокинуть окружение бэкенда» в
[.github/workflows/deploy.yml](../.github/workflows/deploy.yml) кладёт туда
`API_ROOT_PATH`, `LLM_PROVIDER` (repository variable) и `LLM_API_KEY`
(repository secret). Ключ уходит через stdin, а не аргументом команды: аргументы
видны в `ps` на сервере.

Поэтому файл принадлежит `ttdeploy` с правами `600` — это единственное, что деплой-пользователь
может писать за пределами `/opt/tt-hack-preview`. Каталог `/opt/tt-hack` остаётся
за `www-data`:

```bash
touch /opt/tt-hack/.env && chown ttdeploy:ttdeploy /opt/tt-hack/.env && chmod 600 /opt/tt-hack/.env
```

**Править `.env` руками бесполезно — следующий деплой затрёт.** Менять значения
надо в настройках репозитория на GitHub.

### Трассировка вызовов модели

Включается наличием секрета `LANGSMITH_API_KEY`: если он задан, деплой добавляет
в `.env` строку `LANGSMITH_TRACING=true`, и каждый вызов модели попадает в LangSmith
с промптом, ответом, токенами и длительностью. Название проекта — переменная
репозитория `LANGSMITH_PROJECT`, по умолчанию `counterparty-checker`.

Чтобы выключить — убрать секрет: без него строка не пишется и трассировка молчит.
Отдельного тумблера в коде нет и не нужно.

Записи различаются по признаку окружения: `server` на сервере, `local` на ноутбуке.
Берётся из `API_ROOT_PATH` — на сервере он задан, локально пуст, и заводить ещё одну
переменную ради того же различия незачем.

**В трассировку уходит промпт целиком**, включая ФИО руководителей и ИНН из отчёта.
Решение принято осознанно: разбор поведения модели признан важнее.

Записи создаёт сам `ChatOpenAI` — наблюдение встроено в клиент LangChain, своего
кода для него нет. Ради этого мы и ушли с голого HTTP: на httpx приходилось
навешивать декоратор и вручную перекладывать счётчик токенов, иначе записи
приходили с нулями.

Особенность библиотеки: состояние трассировки захватывается один раз при старте
процесса. Включить или выключить её на лету нельзя — нужен рестарт контейнера,
который деплой и так делает. По той же причине прогон тестов выключает
трассировку принудительно (`tests/conftest.py`): иначе личный `.env` разработчика
слал бы записи на каждом прогоне.

Новое значение подхватывается на том же прогоне: шаг записи `.env` идёт перед
выкаткой контейнера, поэтому тот стартует уже с ним. Отдельного рестарта не нужно.

Блок `location ^~ /api/` — в [deploy/nginx/tt-hack-review.conf](nginx/tt-hack-review.conf).
На сервере правится **вручную**: certbot дописал туда 443-блок и редирект с 80,
поэтому копировать файл из репозитория поверх нельзя — потеряется настройка TLS.

### Данные контрагентов

Подготовленный набор переносится отдельно и намеренно: он не входит в репозиторий,
потому что репозиторий открыт.

```bash
# локально
python3 scripts/build_dataset.py                 # → dataset/counterparties.json, ~3,3 МБ
scp dataset/counterparties.json <сервер>:/opt/tt-hack/dataset/counterparties.json.new

# на сервере, под root
cd /opt/tt-hack/dataset
mv counterparties.json.new counterparties.json   # атомарно: оборванный scp не оставит полуфайл
chown www-data:www-data counterparties.json && chmod 640 counterparties.json
docker compose -f /opt/tt-hack/docker-compose.yml restart api
```

Рестарт обязателен: набор читается один раз при старте и кэшируется. Без набора
сервис не поднимается вовсе — это сделано намеренно, работа с пустым набором
выглядит как «у всех компаний ничего нет» и неотличима от честного результата.

### Обновление кода бэкенда

Обычный путь — push в main: CI зелёный → Deploy preview выкатит бэкенд, затем фронт.

Вручную, если нужно быстрее или мимо CI:

```bash
ssh root@<сервер> /usr/local/bin/tt-hack-api-deploy
```

### Диагностика

```bash
docker ps                     # cc-api должен быть healthy
docker logs cc-api --tail 50
curl -s localhost:8000/health
```

MCP на сервере намеренно не поднят: `mcp.run()` использует stdio-транспорт и ничего
не слушает по сети, а три тула из пяти пока заглушки. Секция `mcp` в compose-файле
оставлена, но не запускается — поднимать только `api`.

---

## Фронтенд на сервере

Контейнер `cc-web`: multi-stage образ, где node собирает `src/web`, а nginx отдаёт
результат. Node в финальный слой не едет — в рантайме фронт это набор файлов.

Устройство симметрично бэкенду: контейнер слушает `127.0.0.1:5173`, наружу его
отдаёт nginx сервера за той же basic-авторизацией. `VITE_API_BASE=/api` вшивается
build-аргументом на этапе сборки — поменять его в рантайме нельзя, нужна пересборка.

Выкатку делает `/usr/local/bin/tt-hack-web-deploy` — копия для истории лежит
в [deploy/bin/](bin/tt-hack-web-deploy). Разрешение — вторая строка в том же
`/etc/sudoers.d/tt-hack-api`:

```
ttdeploy ALL=(root) NOPASSWD: /usr/local/bin/tt-hack-web-deploy
```

Две ступени защиты, обе нужны:

1. **Сборка идёт до подмены контейнера.** Пока `docker compose build web` работает,
   наружу отвечает старый контейнер; упавший `tsc` не роняет превью вовсе.
2. **Не поднявшийся контейнер откатывается на предыдущий образ.** Перед сборкой
   рабочий образ помечается как `cc-web:previous`; если новый за 40 секунд не отдал
   `/` и `/api/health`, тег `latest` возвращается на старый образ и контейнер
   пересоздаётся с ним.

Проверяются оба адреса, а не один: контейнер, отдающий `index.html` без живого
`/api`, снаружи выглядит рабочим фронтом, а показывает пустую страницу.

**Порт, как и у бэкенда, только на localhost** — `ufw` на сервере выключен:

```bash
ss -ltn | grep 5173                     # ожидается 127.0.0.1:5173, НЕ 0.0.0.0
curl -m 5 http://<IP>:5173/             # ожидается отказ в соединении
```

### Nginx: два источника под одним адресом

`location /` проксирует в контейнер, а `location ^~ /assets/vibe-debug` идёт мимо
него — в `/opt/tt-hack-preview/current`. Так оверлей коммент-ревью обновляется
статической выкладкой и не требует пересборки образа, а всё остальное приходит
из образа одним куском.

Порядок в конфиге важен: блок оверлея должен стоять **выше** `location /` и иметь
`^~`, иначе запрос уйдёт в контейнер, где этого файла нет.

Следствие: произвольные статические файлы, положенные в релиз, больше не отдаются —
кроме `/assets/vibe-debug*`. Всё, что должно быть на странице, идёт через сборку фронта.

### Первичная установка (один раз, root)

```bash
install -m 750 -o root -g root /opt/tt-hack/deploy/bin/tt-hack-web-deploy /usr/local/bin/
printf 'ttdeploy ALL=(root) NOPASSWD: /usr/local/bin/tt-hack-web-deploy\n' \
  >> /etc/sudoers.d/tt-hack-api
visudo -c                                        # синтаксис sudoers до первого деплоя

# Nginx: было root-обслуживание релиза, стало проксирование в контейнер.
# Правится вручную и точечно: certbot дописал в файл 443-блок и редирект с 80,
# копировать версию из репозитория поверх нельзя — потеряется TLS.
# Образец блоков — deploy/nginx/tt-hack-review.conf.
nginx -t && systemctl reload nginx

sudo /usr/local/bin/tt-hack-web-deploy           # первая сборка: несколько минут
curl -sS -o /dev/null -w '%{http_code}\n' localhost:5173/
```

### Обновление кода фронтенда

Обычный путь — push в main. Вручную:

```bash
ssh root@<сервер> /usr/local/bin/tt-hack-web-deploy
```

### Диагностика

```bash
docker ps                     # cc-web должен быть healthy
docker logs cc-web --tail 50
curl -s -o /dev/null -w '%{http_code}\n' localhost:5173/            # статика
curl -s -o /dev/null -w '%{http_code}\n' localhost:5173/api/health  # проксирование в api
```

`502` на `/api/` изнутри контейнера означает, что лежит `cc-api`, а не фронт:
адрес бэкенда резолвится на каждом запросе, поэтому упавший бэкенд даёт 502,
а не мёртвый контейнер фронта. Когда `cc-api` возвращается, `/api/` начинает
отвечать сам, без рестарта `cc-web`.

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

# 4. Nginx: location / проксирует в контейнер cc-web, а оверлей ревью берётся
#    из симлинка current. Образец обоих блоков — deploy/nginx/tt-hack-review.conf;
#    правится вручную, копировать файл поверх нельзя (в нём TLS от certbot).
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

Фронт и бэкенд — двумя командами под root:

```bash
ssh root@72.56.16.44
/usr/local/bin/tt-hack-api-deploy
/usr/local/bin/tt-hack-web-deploy
```

Статика оверлея — с сервера под `ttdeploy`, из git-клона:

```bash
ssh ttdeploy@72.56.16.44
cd /opt/tt-hack && git pull --ff-only          # обновить исходники
PREVIEW_ROOT=/opt/tt-hack-preview scripts/preview_deploy.sh --local --no-web
```

`--local --no-web` = положить релиз с содержимым `preview/` в
`/opt/tt-hack-preview/releases/` → атомарно переключить `current` → smoke →
почистить старые. Без `--no-web` скрипт ещё и соберёт `src/web` на сервере, но
эта статика теперь никуда не отдаётся — фронт приходит из образа.

Предпросмотр без изменений: `... scripts/preview_deploy.sh --local --no-web --dry-run`.

---

## Откат

**Фронт и бэкенд откатываются образом, а не симлинком.** Предыдущий образ фронта
хранится под тегом `cc-web:previous` — его кладёт `tt-hack-web-deploy` перед каждой
сборкой. Под root:

```bash
cd /opt/tt-hack
docker image tag cc-web:previous cc-web:latest
docker compose up -d --force-recreate --no-build web   # --no-build: иначе пересоберёт сломанное
```

Глубже одного шага назад тегов нет: `git -C /opt/tt-hack reset --hard <sha>` на нужный
коммит, затем `tt-hack-web-deploy` (он делает `fetch`/`reset` на `origin/main` —
для выкатки не из main образ надо собрать руками: `docker compose build web`).

Откат ниже — про **статику оверлея ревью**, не про приложение. С сервера под `ttdeploy`:

```bash
export PREVIEW_ROOT=/opt/tt-hack-preview
BIN=/opt/tt-hack-preview/bin        # или /opt/tt-hack/scripts из клона
$BIN/preview_rollback.sh --list                     # релизы и текущий
$BIN/preview_rollback.sh --local                    # на предыдущий по времени
$BIN/preview_rollback.sh --to 20260903T140502Z-1a2b3c4   # на конкретный
```

Переключение симлинка — миллисекунды. После отката следующий push в `main`
публикуется штатно поверх. Цель «рабочее превью меньше чем за 2 минуты от решения»
теперь держится на откате образа: он тоже секунды, но пересборка после — минуты.

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
| `smoke провален — откат` | новый релиз отдал не `200`. Проверить `docker ps` (жив ли `cc-web`), `~ttdeploy/.preview-smoke-auth`, htpasswd Nginx, доступность своего же публичного URL с сервера |
| Nginx отдаёт `502` на `/` | лежит контейнер `cc-web`: `docker ps`, `docker logs cc-web --tail 50` |
| `[web-deploy] ОШИБКА: фронт не ответил` | контейнер поднялся, но не отвечает. Деплой уже откатился на `cc-web:previous` — смотреть `docker logs cc-web` в логах шага |
| `sudo: a password is required` на шаге выкатки фронта | в `/etc/sudoers.d/tt-hack-api` нет строки для `tt-hack-web-deploy` |
| Оверлей ревью не грузится (`/assets/vibe-debug.js` → 404) | блок `^~ /assets/vibe-debug` в Nginx стоит ниже `location /` или его нет вовсе — запрос ушёл в контейнер |
| Фронт собрался, но ходит не туда | `VITE_API_BASE` вшивается при сборке. Менять — в `docker-compose.yml` (`args`), затем пересобрать образ |
| `npm ci` падает при сборке образа | `package-lock.json` разъехался с `package.json` — пересобрать локально и закоммитить |
| `mv: invalid option -- 'T'` при `--local` на своей машине | скрипты рассчитаны на Linux (GNU coreutils); запускать на сервере/раннере |

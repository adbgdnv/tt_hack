# Контракт: раскладка на сервере

```text
/opt/tt-hack/           git-клон репозитория — как сейчас. Автодеплой НЕ трогает.
│                       (нужен tt-hack-vibe-debug и ручной выкладке `--local`)
│
/opt/tt-hack-review/    данные ревью. Автодеплой НЕ трогает ни при каких условиях.
│
/opt/tt-hack-preview/   артефакты автодеплоя (создаётся ранбуком, вне репозитория)
├── current            → символическая ссылка на releases/<текущий>   ← Nginx root
├── releases/
│   ├── 20260903T140502Z-1a2b3c4/
│   │   ├── index.html            (из preview/)
│   │   ├── report.html
│   │   ├── mcp.html
│   │   ├── assets/…
│   │   ├── <файлы src/web/dist/> (если сборка была)
│   │   └── RELEASE               (sha, branch, built_at, web=built|skipped)
│   └── … (максимум 5)
├── bin/               preview_common.sh, preview_smoke.sh, preview_deploy.sh, preview_rollback.sh
│                      CI синкает сюда перед `--finalize`; git-клон автодеплою не нужен
└── .deploy.lock       flock — защита от параллельного запуска на сервере
```

## Инварианты

1. `Nginx root` = `/opt/tt-hack-preview/current` (правка одной строки в
   `deploy/nginx/tt-hack-review.conf` + `systemctl reload nginx` при первичной настройке).
2. `current` всегда указывает на существующий каталог в `releases/`. Никогда не «в никуда».
3. Переключение — только `ln -sfn <target> current.tmp && mv -T current.tmp current`.
4. Владелец всего `/opt/tt-hack-preview/` — `ttdeploy` (без `sudo`). `/opt/tt-hack-review/` и
   `/opt/tt-hack/.git` — чужие, `ttdeploy` туда не пишет.
5. Чистка: после успешного switch оставить 5 новейших каталогов в `releases/`, прочие — `rm -rf`,
   но никогда не текущий.
6. `git pull` на сервере автодеплоем **не выполняется**. `tt-hack-vibe-debug` и контейнеры
   `api`/`mcp` не перезапускаются.
7. `preview/` в репозитории остаётся обычным git-tracked каталогом (источник), симлинком не
   становится.

## Первичная настройка (один раз, root, — полностью в `deploy/PREVIEW-DEPLOY.md`)

1. `useradd -m -s /bin/bash ttdeploy`
2. `mkdir -p /opt/tt-hack-preview/{releases,bin} && chown -R ttdeploy:ttdeploy /opt/tt-hack-preview`
3. Первый релиз: `cp -a /opt/tt-hack/preview/. /opt/tt-hack-preview/releases/00000000T000000Z-initial/`
4. `ln -sfn …/releases/00000000T000000Z-initial /opt/tt-hack-preview/current` + `chown -h`
5. Nginx: `root` → `/opt/tt-hack-preview/current`, `nginx -t && systemctl reload nginx`
6. `~ttdeploy/.preview-smoke-auth` (chmod 600) — `user:password` из htpasswd Nginx
7. Публичный деплой-ключ → `~ttdeploy/.ssh/authorized_keys`
8. `chown -R ttdeploy:ttdeploy /opt/tt-hack/scripts` — для ручной `--local`
9. `ssh-keyscan -H -t rsa,ecdsa,ed25519 <host> | grep -v '^#'` → секрет `DEPLOY_KNOWN_HOSTS`

# Контракт: раскладка на сервере

```text
/opt/tt-hack/
├── preview            → символическая ссылка на releases/<текущий>   ← Nginx root смотрит сюда
├── releases/
│   ├── 20260903T140502Z-1a2b3c4/
│   │   ├── index.html            (из preview/)
│   │   ├── report.html
│   │   ├── mcp.html
│   │   ├── assets/…
│   │   ├── <файлы src/web/dist/> (если сборка была)
│   │   └── RELEASE               (метаданные: sha, branch, built_at, web=built|skipped)
│   └── … (максимум 5)
├── .deploy.lock       (flock, защита от параллельного запуска на сервере)
└── (git-клон репозитория — как сейчас, для ручных операций; автодеплой его не использует)

/opt/tt-hack-review/   ← НЕ ТРОГАЕТСЯ автодеплоем ни при каких условиях
```

## Инварианты

1. `Nginx root` = `/opt/tt-hack/preview` (уже так в `deploy/nginx/tt-hack-review.conf`). Путь
   не меняется — при первичной настройке каталог `preview/` превращается в симлинк.
2. `preview` всегда указывает на существующий каталог в `releases/`. Никогда не «в никуда».
3. Переключение симлинка — только `ln -sfn <target> preview.tmp && mv -T preview.tmp preview`.
4. Владелец `releases/`, `preview`, `.deploy.lock` — `ttdeploy`. `/opt/tt-hack-review/` — чужой
   владелец, `ttdeploy` туда писать не может.
5. Чистка: после успешного switch оставить 5 новейших каталогов в `releases/`, прочие — `rm -rf`,
   но никогда не текущий.
6. `tt-hack-vibe-debug` (systemd) и контейнеры `api`/`mcp` не перезапускаются и не
   останавливаются.

## Первичная настройка (один раз, root, — в `deploy/PREVIEW-DEPLOY.md`)

1. `useradd -m -s /bin/bash ttdeploy`
2. `mkdir -p /opt/tt-hack/releases && chown -R ttdeploy:ttdeploy /opt/tt-hack/releases`
3. Перенести текущий контент: `mv /opt/tt-hack/preview /opt/tt-hack/releases/00000000T000000Z-initial`
4. `ln -sfn /opt/tt-hack/releases/00000000T000000Z-initial /opt/tt-hack/preview && chown -h ttdeploy:ttdeploy /opt/tt-hack/preview`
5. Публичный деплой-ключ → `~ttdeploy/.ssh/authorized_keys` (chmod 700 `.ssh`, 600 файл)
6. Проверить, что Nginx отдаёт `200` (симлинк прозрачен, `disable_symlinks off` — дефолт)
7. `ssh-keyscan -H <host>` → значение секрета `DEPLOY_KNOWN_HOSTS`

# Задачи

## 1. Раскладка

- [x] 1.1 Собрать продуктовый код под `src/`: `core`, `api`, `mcp_server`, `web`
- [x] 1.2 Назвать каталог `mcp_server`, а не `mcp` — иначе пакет перекроет
      одноимённую библиотеку и `from mcp.server.fastmcp import FastMCP` сломается
- [x] 1.3 `pyproject.toml`: `where = ["src"]`, `pythonpath = ["src"]`, ruff и pytest
- [x] 1.4 Проверить границу: `grep` по `src/core` не находит импортов приложений

## 2. Ядро

- [x] 2.1 `core/config.py` — поиск путей и чтение `.env`, только стандартная библиотека
- [x] 2.2 `core/slim.py` — отбор полей, распаковка `$numberLong`, определение ИП
- [x] 2.3 `core/mocks.py` — фейковая база: JSON + плоский CSV, поиск по ИНН и строке
- [x] 2.4 `core/llm.py` — клиент с обязательным `User-Agent`, отдельным `reasoning`
- [x] 2.5 Сигнатуры `scoring`, `financials`, `compare`, `charts` с требованиями
      кейсодателя в docstring
- [ ] 2.6 Реализовать `scoring.assess` — отдельным change

## 3. Приложения

- [x] 3.1 `src/api` — FastAPI, ручки `/health`, поиск, отчёт по ИНН; CORS для фронта
- [x] 3.2 `src/api/agent/prompt.py` — системный промпт из требований кейсодателя
- [x] 3.3 `src/mcp_server/server.py` — объявления тулов, ресурс `counterparty://{inn}`
- [x] 3.4 `src/web/README.md` — решения по фронту зафиксированы, кода нет

## 4. Инфраструктура

- [x] 4.1 Dockerfile для `api` и `mcp_server`, multi-stage
- [x] 4.2 `docker-compose.yml`; `data` монтируется томом, в образ не копируется
- [x] 4.3 `Makefile`: `install`, `test`, `lint`, `up`, `down`, `data`, `probe`
- [x] 4.4 CI на GitHub Actions: `ruff check` + `pytest`
- [x] 4.5 `.gitignore`: `data` под игнором

## 5. Проверка

- [x] 5.1 Ядро импортируется без установленного `httpx`
- [x] 5.2 Фейковая база отдаёт 200 компаний
- [x] 5.3 Опорный кейс МАКСМАРКЕТ: сжатие 74×, суммы развёрнуты в числа
- [x] 5.4 `git status` не показывает `.env`, `temp/`, `data/`, `__pycache__`
- [ ] 5.5 `pytest -q` — зелёный (нужен `make install`, pytest не установлен)
- [ ] 5.6 `make up` — оба сервиса поднимаются, `/health` отвечает 200

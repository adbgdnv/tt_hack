.DEFAULT_GOAL := help
.PHONY: help install test lint up down logs probe check-llm data \
	eval-build eval-regression eval-risk eval-baseline

help:  ## Список команд
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Поставить зависимости в текущее окружение
	pip install -e ".[dev]"

test:  ## Прогнать тесты
	pytest -q

lint:  ## Проверить стиль
	ruff check .

up:  ## Поднять api и mcp
	docker compose up --build -d
	@echo "api  → http://localhost:8000/health"
	@echo "mcp  → http://localhost:8001"

down:  ## Остановить всё
	docker compose down

logs:  ## Логи сервисов
	docker compose logs -f

data:  ## Связать выгрузку кейсодателя (docs_alpha лежит вне репозитория)
	@test -e data || ln -s ../docs_alpha data
	@echo "data → $$(readlink data 2>/dev/null || echo 'уже каталог')"

probe:  ## Прогнать пробник на живой модели
	python3 temp/probe_llm.py

check-llm:  ## Проверить доступность провайдеров с текущей сети
	bash temp/check_llm.sh

eval-build:  ## Собрать фиксированный eval-датасет из текущих данных (30 кейсов)
	python3.13 -m evals.build_cases

eval-regression:  ## Прогнать live regression-suite агента (16 кейсов)
	python3.13 -m evals.run --suite regression

eval-risk:  ## Прогнать live risk-suite агента (14 кейсов)
	python3.13 -m evals.run --suite risk

eval-baseline:  ## Прогнать все 30 live eval-кейсов и сохранить baseline JSON
	python3.13 -m evals.run --output evals/results/baseline.json

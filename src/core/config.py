"""Пути и переменные окружения. Только стандартная библиотека.

Вынесено отдельно от llm.py намеренно: загрузка данных не должна тянуть за собой
HTTP-клиент. Иначе `import core.mocks` падает там, где httpx не нужен и не установлен —
например в тестах и в CI.
"""

from __future__ import annotations

import os
from pathlib import Path


def find_up(relative: str, start: Path | None = None) -> Path | None:
    """Ищет файл вверх по дереву — чтобы путь запуска не имел значения."""
    start = start or Path(__file__).resolve().parent
    for d in [start, *start.parents]:
        candidate = d / relative
        if candidate.exists():
            return candidate
    return None


DATASET_DEFAULT = "dataset/counterparties.json"


def repo_root() -> Path:
    """Корень проекта. Опознаётся по pyproject.toml — он есть только там."""
    marker = find_up("pyproject.toml")
    return marker.parent if marker else Path(__file__).resolve().parents[2]


def dataset_path() -> Path:
    """Путь к подготовленному набору контрагентов.

    Набор собирается скриптом и в репозиторий не попадает, поэтому путь к нему —
    переменная окружения: локально одно место, на сервере другое. Когда файла ещё
    нет, возвращается ожидаемое место, чтобы ошибка могла назвать конкретный путь,
    а не «файл не найден».
    """
    load_env()
    raw = os.environ.get("DATASET_PATH")
    if raw:
        return Path(raw).expanduser()
    return repo_root() / DATASET_DEFAULT


def load_env(path: Path | None = None) -> None:
    """Читает .env без внешних зависимостей. Переменные окружения приоритетнее файла."""
    path = path or find_up(".env")
    if not path or not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

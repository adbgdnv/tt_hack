"""Инструменты агента.

Их два, и список закрыт не из скромности: схема каждого инструмента уходит
в модель **на каждом вызове**, а лимит провайдера — 8 000 токенов в минуту.

Запись о контрагенте инструменты читают из контекста выполнения, а не получают
параметром: в промпт она не попадает (31 000 токенов на типовой компании), и модель
о ней не знает — она знает только про инструменты.

Контракт — `specs/006-chat-agent-tools/contracts/tools.md`.
"""

from __future__ import annotations

from langchain_core.tools import tool
from langgraph.runtime import get_runtime

from api.agent.graph import Context
from core.charts import build_charts

# Русское название рядом с ключом — часть контракта, а не украшение. Без него
# модель выбирает по латинскому ключу и промахивается: на пробе дважды выбрала
# «В какой роли судится» в ответ на просьбу показать суммы исков по годам.
CHART_KINDS = """
- plaintiff_defendant — «В какой роли судится»
- balance — «Чем обеспечены активы»
- revenue_assets — «Выручка и активы»
- proceedings — «Исполнительные производства»
- arbitration_years — «Суммы исков по годам»
"""


def _values(spec) -> str:
    """Числа графика строкой — для модели.

    Обязательны. С голым подтверждением «график показан» модель дописывает ответ
    выдуманной таблицей: на пробе нарисовала 2019–2022 годы, которых в отчёте нет,
    и приписала «данные основаны на публичных реестрах». Пустота заполняется
    правдоподобным, поэтому пустоты быть не должно.
    """
    return "; ".join(
        f"{series.name}: "
        + ", ".join(
            f"{label} {value}"
            for label, value in zip(spec.labels, series.values, strict=False)
            if value is not None
        )
        for series in spec.series
    )


def chart_result(record: dict, inn: str, kind: str) -> tuple[str, dict]:
    """Что вернуть на просьбу показать график. Вынесено из инструмента, чтобы
    проверялось без цикла агента и его контекста выполнения."""
    charts = {c.key: c for c in build_charts(record)}
    spec = charts.get(kind)
    if spec is None:
        available = ", ".join(charts) or "ни одного"
        return (
            f"У этой компании нет данных для графика «{kind}». Доступны: {available}. "
            "Пустой график не показан.",
            {},
        )
    return (
        f"График «{spec.title}» показан пользователю. Его данные: {_values(spec)}",
        {"chart": {"chart": spec.key, "inn": inn}},
    )


@tool(response_format="content_and_artifact")
def show_chart(kind: str) -> tuple[str, dict]:
    """Показать пользователю график по компании из отчёта.

    Виды графиков:
    {kinds}
    Другие виды построить нельзя. Если у компании нет данных для выбранного вида,
    инструмент так и скажет и перечислит доступные.
    """
    runtime = get_runtime(Context)
    return chart_result(runtime.context.record, runtime.context.report.inn, kind)


# Описание достаётся модели как есть, поэтому список видов подставляем в него,
# а не держим отдельной строкой, которую модель не увидит.
show_chart.description = (show_chart.description or "").replace("{kinds}", CHART_KINDS.strip())


def build(record: dict, inn: str) -> list:
    """Инструменты для одного запроса.

    Набор зависит от окружения: инструмент, который не может работать, модели
    не предлагается вовсе. Заглушка, отвечающая «поиск недоступен», стоила бы
    токенов на каждом вызове и ничего бы не давала.
    """
    from api.agent import search  # локально: без ключа модуль поиска не нужен

    return [show_chart, *search.tools()]

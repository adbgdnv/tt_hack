# Specification Quality Checklist: Графики в отчёте о контрагенте

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-04
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

Границы закрыты сессией уточнений 2026-09-04: берутся **все пять** графиков,
рисует **компонент `chart` дизайн-системы**. Проверенное покрытие на 200 контрагентах:

| Что можно построить | Данные есть у |
|---|---:|
| Выручка и активы по годам (≥2 года) | 133 (66%) |
| Структура баланса: капитал против обязательств | 133 (66%) |
| Истец против ответчика | 129 (64%) |
| Исполнительные производства: активные против завершённых | 143 (72%) |
| Судебная нагрузка по годам (≥2 года) | 61 (30%) |
| Прибыль по годам (≥2 года) | 68 (34%) |
| Производства по годам (≥2 года) | 67 (33%) |
| Готовые коэффициенты | 47 (23%) |
| Госзакупки по годам | 8 (4%) |

Отброшены: коэффициенты и госзакупки — покрытие ниже четверти набора, график
на таких данных чаще отсутствует, чем присутствует.

Прибыль вынесена отдельно: она заполнена вдвое реже выручки, поэтому пара
«выручка и прибыль» на одном графике по умолчанию не строится.

**Что уже есть в коде.** `core/charts.py` содержит структуру `ChartSpec` и четыре
заглушки `NotImplementedError`. `FinancialChart.tsx` — самодельный SVG, принимающий
данные, которых в собранном отчёте нет: поле `financials` не заполняется.
Ни то ни другое сейчас не работает.

**Про инструмент рисования.** `@alfalab/core-components-chart` существует (версия
5.0.10) и внутри использует recharts. То есть выбор даёт и стиль дизайн-системы,
и полноценную библиотеку — эти варианты не конкурируют, как казалось при постановке
вопроса. Поддерживаются столбцы, линии и области; круговых диаграмм нет,
и ни одному из пяти графиков они не нужны.

Самодельный `FinancialChart.tsx` после этого заменяется, а не дорабатывается.

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`

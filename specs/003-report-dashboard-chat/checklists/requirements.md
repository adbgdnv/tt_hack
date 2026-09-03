# Specification Quality Checklist: Дашборд отчёта и диалог о контрагенте

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

Оба ранее открытых пункта закрыты сессией уточнений 2026-09-04.

**Границы.** `docs/product.md` описывает боли, гипотезы и метрики, но состава первичного
отчёта не содержит — там принципы, а не перечень полей. Состав выведен из этих принципов
и из фактического наполнения данных, подтверждён пользователем.

**Разделы.** Их восемь: к шести имеющимся добавлены «Руководство» и «Связанные
организации». Данные по ним есть — руководитель у 150 контрагентов из 200, связанные
организации у 126, — а показать их до сих пор было негде.

**Расхождение с исходной постановкой, зафиксировано отдельно.** Диалогового агента
в репозитории нет: `POST /chat` и цикл агента — заглушки `NotImplementedError`,
существующий диалог полностью постановочный, ответы берутся из заготовок, а видимость
работы создаётся таймерами. Клиент модели написан и проверен на живом провайдере,
поэтому агента предстоит собрать, а не подключить. На объём это влияет заметно.

**Прочитанное расширительно.** Решение «сделать кнопки рабочими» отнесено к «Ссылке»
и «PDF» — они названы в выбранном варианте. Кнопка «Сравнить» убирается: сделать её
рабочей значит реализовать сравнение целиком, а оно в эту поставку не входит.

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`

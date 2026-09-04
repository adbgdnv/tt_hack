# Specification Quality Checklist: Сборка уезжает с боевого сервера

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-04
**Feature**: [spec.md](../spec.md)

## Content Quality

- [X] No implementation details (languages, frameworks, APIs)
- [X] Focused on user value and business needs
- [X] Written for non-technical stakeholders
- [X] All mandatory sections completed

## Requirement Completeness

- [X] No [NEEDS CLARIFICATION] markers remain
- [X] Requirements are testable and unambiguous
- [X] Success criteria are measurable
- [X] Success criteria are technology-agnostic (no implementation details)
- [X] All acceptance scenarios are defined
- [X] Edge cases are identified
- [X] Scope is clearly bounded
- [X] Dependencies and assumptions identified

## Feature Readiness

- [X] All functional requirements have clear acceptance criteria
- [X] User scenarios cover primary flows
- [X] Feature meets measurable outcomes defined in Success Criteria
- [X] No implementation details leak into specification

## Notes

Спека инфраструктурная, и соблазн написать её командами был сильный. Названия
инструментов оставлены плану: в требованиях «сборка происходит на машине
поставщика, не на сервере продукта» вместо «job build на ubuntu-latest»,
«метка, однозначно связывающая образ с коммитом» вместо `$GITHUB_SHA`.
Это переживёт смену площадки, а команда — нет.

Единственное место, где назван конкретный поставщик, — Assumptions: хранилище
образов берём у GitHub. Это допущение, ни одно FR на него не ссылается, и смена
хранилища спеку не меняет.

Числа в спеке — замеры с сегодняшнего дня, а не оценки: 894 МБ памяти на сервере,
нагрузка 27 во время сборки, SSH без ответа, контейнер «создан, но не запущен»
после отмены выкатки. Они стоят в тексте намеренно: без них требование выглядит
вкусовщиной, а с ними — разбором уже случившегося отказа.

Раздел «Как это устроено в рабочем примере» описывает форму из `zorox-editor`
без переноса инструмента: там кластер и свой реестр, у нас один сервер. Взяты
четыре вещи — отдельный этап сборки, две метки на образ, опора на предыдущий
образ, проверка после выкатки.

FR-007 переписывалось **дважды**, и оба раза — из-за выдуманного обоснования.
Сначала было «в образах лежит набор с ФИО учредителей» — неправда, набор
подключается томом. Затем «код продукта наружу не выкладываем» — тоже неправда,
репозиторий публичный. В итоге требование осталось, но с честным основанием:
секретного в образах нет, а публикация артефактов просто должна быть осознанным
действием.

Урок для остальных требований в этой спеке: обоснование проверяется так же,
как само требование. Правдоподобная причина, взятая по памяти, — это тот же
класс ошибки, что выдуманное число.

Отдельно проверено, что US1 действительно самая приоритетная: она про то, из-за
чего сегодня лежал сервис, а US2 — фундамент под неё. Разнесены они потому,
что проверяются по-разному: US1 — поведением сервиса во время выкатки,
US2 — содержимым хранилища.

# Specification Quality Checklist: Триггеры из данных и словарь полей

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-05
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

Ни одного `[NEEDS CLARIFICATION]` не осталось — все развилки закрыты замерами
на данных, а не догадками:

- «сколько триггеров бывает у компании» → замерено: максимум 5, ни одного у 124
  из 200, три и более у 11;
- «какой порог не превращает признак в фон» → замерено по каждому кандидату,
  правило FR-004 (не более трети набора) выведено из этих замеров;
- «есть ли готовые описания полей» → есть, 103 из 114 в официальной
  спецификации кейсодателя;
- «независимы ли триггеры между собой» → замерено, ни одной пары с пересечением
  выше 0,5 по Жаккару.

Единственное решение, принятое **не** по данным, а по продуктовому суждению, —
вопрос пользователя меняет порядок, а не состав (FR-009). Оно записано в
допущениях с последствиями на случай, если решение окажется неверным.

Отдельно зафиксировано расхождение официальной спецификации с данными
(`status.reasonName`) — оно попадает в требование FR-015, а не разрешается молча.

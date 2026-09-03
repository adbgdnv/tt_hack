# Specification Quality Checklist: Автодеплой превью

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-03
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

- Q1 закрыт: откат ручной как основной (вариант A). Маркеров [NEEDS CLARIFICATION] не осталось.
- `/speckit-analyze` (2026-09-03): устранены F1 (FR-007a переформулирован + добавлен FR-007b:
  switch атомарно, smoke сразу после, авто-откат при провале, окно = секунды), F2
  (`DEPLOY_KNOWN_HOSTS` внесён в FR-008 и Key Entities), F3 (guard про запретные пути в
  T003/T007/T022), F5 (формулировка про Nginx в plan.md). F6 — информационная, правок не
  требует. Critical/High после правок — 0.
- `/speckit-converge` → `/speckit-implement` (2026-09-03): T028 закрыт — Basic Auth хранится
  на сервере (`~ttdeploy/.preview-smoke-auth`), не в GitHub Secrets; FR-008, Key Entities,
  `data-model.md`, оба контракта и `research.md` R5/R6/R8 приведены к этому. GitHub Secrets — 4.
  Также T030 (контур в логе), T031 (`SMOKE_PATHS` проброшен), T032 (снят npm-кэш до lockfile).
  Осталось T027/T029 — только живой прогон.
- Названия инфраструктуры (Nginx, сервер, каталоги) в спеке — это фиксированные факты
  окружения из `deploy/` и `docs/`, а не выбор реализации. Выбор транспорта, CI-механики и
  структуры скриптов оставлен для `/speckit-plan`.

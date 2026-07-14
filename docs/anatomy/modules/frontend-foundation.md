# Module: Frontend Foundation

**Path:** `frontend`
**Role:** Contains TypeScript contract artifacts, evidence helper code, control room application, setup center web components, and Playwright accessibility tests.

## Public interface

- `pnpm --dir frontend test` — runs Vitest unit tests.
- `pnpm --dir frontend typecheck` — validates TypeScript.
- `pnpm --dir frontend build:setup` — builds setup center static assets.
- `pnpm --dir frontend check:setup-assets` — checks setup asset integrity.
- `pnpm --dir frontend test:a11y` — runs Playwright accessibility tests.
- `pnpm --dir frontend test:control-room` — runs control room unit tests.
- `pnpm --dir frontend test:product` — runs product-level Playwright tests.
- `pnpm --dir frontend test:setup` — runs setup integration tests via Node test runner.
- `pnpm --dir frontend test:final` — runs setup tests, vitest unit tests, then Playwright product and accessibility tests.
- `pnpm --dir frontend build` — builds the Vite-based frontend.
- `buildEvidenceRecord(...)` — builds a frontend evidence-shaped object; currently not schema-equivalent to the canonical backend model.
- `validateEvidenceRecordSemantic(...)` — two-layer validation pipeline: structural validation via generated Zod schema, then semantic validation.

## Internal structure

- `src/contracts/` — generated Zod validators for DecisionRecord, EvidenceRecord, and Setup contracts.
- `src/control-room/` — React application with shell, builder, coordinator, executive-operator, copilot-panel, and operator views.
- `src/setup/` — Setup Center custom elements: setup-center-element.js (Web Component), setup-center.tsx (React wrapper), setup-api.js, setup-model.js, setup-center.css.
- `lib/evidence-collector.ts` — manually maintained evidence helper.
- `tests/control-room/` — unit tests for builder, coordinator, executive-operator, and onboarding.
- `tests/setup/` — integration tests for setup-api, setup-model, setup-render, and control-room integration, all run via the built-in Node test runner (`node --test`).
- `tests/accessibility/` — Playwright accessibility tests (keyboard nav, WCAG audit, drag alternatives, focus appearance).
- `tests/product/` — Playwright control-room and final verification specs.

## Depends on

- **`contract-generation`** — consumes generated Zod schemas for DecisionRecord, EvidenceRecord, and Setup contracts (`frontend/src/contracts/decision-record.generated.ts:3`)
- external: `typescript` — type-checks frontend code (`frontend/package.json:12`)
- external: `vitest` — runs frontend unit tests (`frontend/package.json:12`)
- external: `zod` — validates generated contract values at runtime (`frontend/src/contracts/decision-record.generated.ts:3`)
- external: `react` — UI framework for control room (`frontend/src/control-room/app.tsx:1`)
- external: `@tanstack/react-query` — data fetching for control room shell (`frontend/src/control-room/shell.tsx:1`)
- external: `@playwright/test` — accessibility and product-level integration tests (`frontend/tests/accessibility/keyboard-nav.spec.ts:1`)
- external: `@axe-core/playwright` — automated WCAG audit (`frontend/tests/accessibility/wcag-audit.spec.ts:1`)
- external: `node:test` — built-in Node test runner for setup integration tests (`frontend/tests/setup/setup-api.test.mjs:1`)

## Used by

- **`delivery-ci`** — runs frontend quality checks (`.github/workflows/ci.yml:52`)

## Data & side effects

- No deployed network behavior; tests and generated-artifact validation only. Playwright tests may open local dev pages.

## Notes / discrepancies vs existing docs

- `lib/evidence-collector.ts` does not include all canonical `EvidenceRecord` fields such as `run_id`, `subject_sha`, canonical environment and stream references.
- The Zod generator requests v3 output while the frontend declares Zod 4.x.
- The control room now has a working React application with builder, coordinator, executive-operator, and operator views.
- The Setup Center provides Web Component and React integration points.
- Playwright tests were simplified to go directly to control-room views instead of stepping through the onboarding flow.
- Setup integration tests use the built-in Node test runner (`node:test`) rather than Vitest or Playwright.

---

_Traced from source on 2026-07-14 (incremental refresh). Files examined in depth: all 53 files._

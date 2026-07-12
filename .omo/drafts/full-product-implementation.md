---
slug: full-product-implementation
status: conditionally-approved-preflight-blocked
intent: clear
pending-action: write .omo/plans/full-product-implementation.md
approach: Build a standalone Python/TypeScript modular monolith through dependency-ordered tracer bullets, with TDD and harness evidence at every slice.
---

# Draft: full-product-implementation

## Components (topology ledger)
<!-- Lock the SHAPE before depth. One row per top-level component that can succeed or fail independently. -->
| id | outcome | status | evidence path |
| bootstrap | Standalone repo, toolchains, CI, containers, schema generation | active | `.omo/evidence/bootstrap/` |
| core | Pure deterministic graph/policy/decision engine | active | `.omo/evidence/core/` |
| platform | PostgreSQL persistence, audit, queue, tenancy, identity | active | `.omo/evidence/platform/` |
| github | Certified GitHub adapter, durable inbox, normalization, reconciliation | active | `.omo/evidence/github/` |
| workflow | Gates/evidence, projections, approvals, leases, attention | active | `.omo/evidence/workflow/` |
| interfaces | Web/API, worker, scheduler, CLI, OpenAPI | active | `.omo/evidence/interfaces/` |
| control-room | Accessible four-view React Control Room | active | `.omo/evidence/control-room/` |
| production | Copilot boundary, security, observability, certification, cutover | active | `.omo/evidence/production/` |

## Open assumptions (announced defaults)
<!-- Record any default you adopt instead of asking, so the user can veto it at the gate. -->
| assumption | adopted default | rationale | reversible? |
| Backend | Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2 async, Alembic, asyncpg | Matches canonical API/harness contracts | Yes, costly |
| Frontend | React + TypeScript strict + Vite, Zod, TanStack Query, CSS tokens | Standalone SPA; no framework SSR requirement | Yes |
| Schema source | Pydantic/OpenAPI canonical; generated Zod/types checked into build artifacts, not hand-maintained | Prevents cross-language drift | Yes |
| Infrastructure | PostgreSQL 16 queue/current state; MinIO/S3 evidence; no mandatory Redis | Matches architecture truth | Yes |
| Authentication | OIDC/OAuth for hosted; local credential + TOTP/WebAuthn for self-host; opaque server sessions | Supports revocation and break-glass better than role-bearing JWTs | Yes |
| Copilot | Provider-neutral port, disabled by default, deterministic fake for tests | AI has no authority and must be optional | Yes |
| Testing | TDD for every tracer bullet; all QA agent-executable | User requested production-ready/testable | No |
| Release | Standard envelope and full 72-hour soak block GA; Large/Tenant Aggregate only when declared | Preserve production spec, no MVP weakening | Yes |

## Findings (cited - path:lines)

- `docs/decisions/ADR-006-foundation-contracts.md` fixes the 13-module taxonomy, Application-owned port contracts, reproducible decisions, forced RLS, audit integrity, and atomic consistency protocol.
- `docs/architecture/ARCHITECTURE.md:46-187` fixes the 13-module deep modular-monolith boundary and places `audit` in Platform.
- `docs/architecture/ARCHITECTURE.md:230-275` requires three runtime processes sharing one codebase.
- `docs/architecture/ARCHITECTURE.md:279-400` fixes PostgreSQL current state, append-only audit, S3 evidence, and durable queue semantics.
- `docs/integrations/GITHUB.md:148-244` requires signed durable webhook inbox, refetch, dedup, solve, append decision, and projection.
- `docs/security/authorization.md:43-224` defines scoped role grants, SoD, credential controls, and break-glass.
- `docs/quality/harness-catalog.md:10-16,765-785` defines 67 executable harness contracts and the 64 Standard-release gates.
- Stale harness paths referring to `packages/`, `services/`, `apps/`, or old `AGENTS.md` rules are intent-only and must be mapped to the standalone layout created by this plan.

## Decisions (with rationale)

- Follow ADR-006: `audit` is Platform; Application owns ports in `application.ports`, which Platform/Adapters may import only to implement.
- Use `backend/src/work_frontier/{domain,platform,application,adapters,interfaces}` plus `frontend/src`; never recreate the oh-my-class tree.
- Use monorepo-level `Makefile` as the stable harness command surface; implementation tools may evolve behind it.
- Freeze #539 source data as versioned fixtures; live GitHub is reserved for sandbox certification.
- Store source revisions as opaque tracker revision strings plus monotonic local version; stale-write fencing compares local versions and source equality, never timestamp ordering.
- No SSE requirement is invented; initial UI uses polling/query invalidation. Add real-time transport only through a later ADR.
- Review fix: dependency matrix now mirrors each Wave-2 todo and Todo 35 exactly; canonical `ARCHITECTURE.md` explicitly wins over ADR-003's stale `audit` layer line.
- Architecture review P0 fix: ADR-006 is now the preflight contract gate. Bootstrap is blocked until its taxonomy, Application-owned port seams, reproducible DecisionRecord, payload-safe segmented audit chain, mandatory RLS, and inbox/outbox/queue protocol have executable contract coverage.

## Review receipts

- Metis: `ses_0acd5f5dcffehf3A2kkcDqN2AZ`; gaps integrated into bootstrap, stack, schema, security, CI, harness and cutover todos.
- Momus round 1: `ses_0accba92dffeKQQEoWaUtZQSd0`; rejected only because reviewer cwd was the old `oh-my-class` repo and relative path did not exist there. Re-review uses the absolute standalone path.
- Oracle round 1: `ses_0accba817ffesP8H8E2pRqfktS`; found dependency-matrix mismatch for Todo 35 and coarse Wave-2 dependency row; both corrected. Also requested explicit canonical precedence for the stale ADR audit placement; corrected.
- Review round 2: Momus `ses_0acc8d928ffe8DkjagwoWhkupB` returned OKAY. Oracle approved with a non-blocking note that Todos 16-18 were still grouped despite different prerequisites; grouping and reverse `Blocks` summaries were normalized before final receipts.
- Review round 3: Momus `ses_0acc1d766ffeulp3M9k3s7oekH` returned OKAY. Oracle approved and identified one non-blocking matrix typo (`Todo 20 Blocks: 31` instead of `33`); corrected before final hash receipts.
- Final hash review: Oracle `ses_0accba817ffesP8H8E2pRqfktS` returned APPROVE; Momus `ses_0acbe1808ffeRc5tE1oZtWF2xO` returned OKAY and noted one UX reference filename word-order typo, corrected before locking the plan.
- Superseded plan SHA-256: `4df1d68c0f1b81f276ad5f011f71729c8666f6fe174f1ec9446bc69cdf57d45e`. It predates the ADR-006 P0 rebasing and is not approval for the current plan.
- Current approved rebased plan SHA-256: `6c19270e3148d4429e9b0bd29069e2ec0faab27334d6ce224875f67974000197`.
- Current deterministic validation: 52 Markdown files passed frontmatter/local-link validation; stale foundation-term sweep passed; plan validator passed 36 ordered todos (P0 + 1–35) with acceptance/QA blocks and P0→Todo 1 dependency.
- ADR-006 rebase review: Oracle continuation `ses_0abfeaafeffedr4DM6HltaGAz6` approved P0 execution after verifying all seven `WF-P0-*` contracts, frontmatter, and dependency corrections. Its two non-blocking documentation nits (convergence summary and performance-envelope link) were fixed before this receipt.
- P0 execution: `.omo/preflight/adr-006/validate.mjs` passed with all seven `WF-P0-*` contracts, 7 positive fixtures, 16 mapped negative fixtures, and zero failures; evidence is `.omo/evidence/preflight-adr-006/validation.json`. This is documentation-contract evidence only, not premature runtime RLS/queue/audit/performance evidence.
- Todo 1 execution: standalone Python 3.13/uv and Node 22/pnpm toolchains, strict Ruff/basedpyright/Biome/TypeScript gates, reproducible lockfiles, and Python/TypeScript hello-contract tests passed. Evidence: `.omo/evidence/task-1-full-product-implementation/verification.json`.
- Todo 2 execution: ADR-006 AST import-boundary enforcement accepts only `application.ports` as the Platform/Adapter implementation exception and rejects six forbidden edge mutations with exact rule IDs. Evidence: `.omo/evidence/task-2-full-product-implementation/verification.json`.
- Todo 3 execution: single-node local/CI Compose runs PostgreSQL 16 and MinIO on isolated ports; Alembic upgrade/downgrade/re-upgrade, seeded-state, and failed-DDL rollback probes plus MinIO object round trip pass. Evidence: `.omo/evidence/task-3-full-product-implementation/verification.json`.
- Todo 4 execution: immutable Pydantic DecisionRecord envelope generates deterministic JSON Schema and Zod artifacts; Python and Zod enforce round trip and mandatory workspace rejection. Evidence: `.omo/evidence/task-4-full-product-implementation/verification.json`.

## Scope IN

- All 13 modules, three runtime processes, REST/OpenAPI, CLI, four Control Room views, GitHub Level-3 adapter, hosted/self-hosted artifacts, 67 harnesses, signed certification, and #539 cutover.

## Scope OUT (Must NOT have)

- No non-GitHub production tracker, microservices split, event-sourced current state, AI authority, silent SoD bypass, QTI/content-generation domain, or unverified Large/Tenant envelope claim.

## Open questions

- None blocking. Defaults above are reversible and follow the canonical docs.

## Approval gate
status: todo-4-complete-todo-5-unblocked
pending-action: execute Todo 5 harness registry and evidence-manifest validation with its own evidence
<!-- When exploration is exhausted and unknowns are answered, set status: awaiting-approval. -->
<!-- That durable record is the loop guard: on a later turn read it and resume at the gate instead of re-running exploration. -->

# Contributing to Work Frontier

Thank you for improving Work Frontier. This repository treats architecture, reproducibility, and
evidence as executable product requirements, not documentation-only conventions.

## Before you start

Read:

1. [`AGENTS.md`](AGENTS.md) for repository-wide engineering rules.
2. [`.omo/plans/full-product-implementation.md`](.omo/plans/full-product-implementation.md) for the
   dependency-ordered implementation plan.
3. [`docs/development.md`](docs/development.md) for local setup and troubleshooting.
4. The relevant architecture/ADR and harness definitions for your change.

Do not start a todo whose dependencies or continuation gate are not demonstrably satisfied.

## Setup

```sh
make doctor
make bootstrap
make check
```

For the full local CI-equivalent path:

```sh
make verify
```

The pinned versions are Python `3.13.5`, Node `22.23.1`, and pnpm `10.20.0`.

## Branches and commits

Create a focused branch from current `main`. Use concise Conventional Commit-style subjects, for
example:

```text
feat(domain): add deterministic snapshot identity
fix(contracts): reject non-canonical source revisions
test(harness): add stale-evidence mutation fixture
docs(devex): document local verification path
```

Keep commits buildable where practical. Avoid mixing refactors, generated churn, and product behavior
in one commit unless they are inseparable.

## Development workflow

1. Add or update a failing test or executable fixture.
2. Implement the smallest coherent change.
3. Run the narrow test while iterating.
4. Run `make fix`.
5. Run `make check`.
6. Run `make verify` for integration, migration, storage, harness, or release-critical changes.
7. Inspect generated artifacts and the complete Git diff.

Canonical contracts and registry outputs must be regenerated through their Make targets; never edit
generated files directly.

## Pull requests

A pull request should explain:

- the problem and active todo/harness IDs;
- the implementation approach and non-goals;
- architecture, contract, persistence, tenancy, concurrency, and security impact;
- exact validation commands and their outcomes;
- migrations, generated artifacts, fixtures, evidence, screenshots, or traces where applicable.

Draft PRs are encouraged for early architecture review. Mark a PR ready only after its checklist is
truthful.

## Review expectations

Reviewers should prioritize:

1. Correctness against executable contracts and the active todo.
2. Determinism, idempotency, concurrency, and failure semantics.
3. Tenant/workspace isolation, authorization, secrets, and evidence safety.
4. Import-boundary and module ownership compliance.
5. Test quality, especially negative and mutation coverage.
6. Operational rollback and observability.
7. Readability and maintainability.

A green test suite does not override a violated architecture or security invariant.

## Reporting security issues

Do not open a public issue containing secrets or an exploitable vulnerability. Contact the repository
owner privately with a minimal reproduction, affected revisions, impact, and suggested containment.

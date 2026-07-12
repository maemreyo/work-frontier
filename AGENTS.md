# AGENTS.md

This file is the canonical operating guide for coding agents working in this repository.
Tool-specific instruction files may add workflow details, but they must not contradict this file.
A more deeply nested `AGENTS.md` may narrow rules for its subtree.

## Mission and current state

Work Frontier is being built as a standalone dependency-aware readiness control plane.
The repository currently contains the foundation toolchain under executable recertification: strict contracts,
architecture-boundary checks, harness/evidence infrastructure, PostgreSQL/MinIO smoke tests,
and frontend TypeScript contract tooling. Do not describe planned API, worker, scheduler,
GitHub adapter, or Control Room features as implemented until executable source and tests exist.

The dependency-ordered implementation plan is
`.omo/plans/full-product-implementation.md`. Treat its architecture and acceptance criteria as
requirements, but verify status claims against code, tests, registry state, and evidence for the
exact subject revision.

## Source-of-truth order

When sources disagree, use this order:

1. Executable contracts, migrations, tests, harness registry, and current source.
2. The active todo and its acceptance criteria in `.omo/plans/full-product-implementation.md`.
3. Canonical architecture and ADR documents.
4. README files, comments, historical reports, and generated summaries.

Never “fix” a failing executable contract by weakening it to match stale prose.

## Read before changing code

1. Read the relevant todo, dependencies, non-goals, harness IDs, and Definition of Done.
2. Inspect the implementation and tests in the affected module.
3. Check the import boundary matrix in `scripts/check_import_boundaries.py`.
4. Check canonical contracts under `backend/src/work_frontier/contracts/`.
5. Check `.omo/harness-registry.json` and existing fixtures/evidence conventions.
6. Use repository skills under `.agents/skills/` when a task matches one.

Keep the change scoped to one coherent outcome. Do not opportunistically implement future todos.

## Golden-path commands

```sh
make doctor       # validate local tools and pinned versions
make bootstrap    # install locked Python and Node dependencies
make check        # static checks, contract/registry drift, unit tests
make verify       # full local CI path, including PostgreSQL and MinIO smokes
make fix          # apply safe Python and frontend formatting/lint fixes
make help         # list supported commands
```

Use `make` targets rather than inventing one-off command variants. CI must use the same targets
developers use locally.

## Architecture rules

Canonical Python layers are:

- `domain`: pure business rules and types; no application, adapter, interface, or platform imports.
- `application`: use cases and outbound ports; may depend on domain and contracts.
- `adapters`: implementations of application ports; may depend on application, domain, contracts,
  and platform where the canonical matrix permits it.
- `interfaces`: HTTP/CLI/process entry points and composition-facing adapters.
- `platform`: cross-cutting runtime infrastructure; never becomes a domain dependency.
- `contracts`: deliberately shared executable contracts with narrowly controlled imports.
- `bootstrap.py`: composition root only; wiring belongs here, not in domain/application modules.

The executable allow matrix in `scripts/check_import_boundaries.py` is authoritative. Any intentional
new edge requires an architecture decision, updated tests, and an explicit matrix change.

## Contract and generated-file rules

- Python/Pydantic is the canonical source for cross-language contracts unless an ADR says otherwise.
- Do not hand-edit generated contract outputs.
- After changing a canonical contract, run `make generate-contracts`, inspect the diff, then run
  `make check-contracts`.
- After changing the harness catalog or implemented command mapping, regenerate and check the
  harness registry.
- Preserve strict/canonical semantics: forbidden extra fields, deterministic serialization,
  lower-case SHA-256 values, and required reproducibility fields.
- Shared positive and negative fixtures must run through every language implementation.

## Evidence and certification rules

Implementation, verification, and certification are separate states.

A claimed pass must be produced by the registered harness for the exact subject revision and include
the registry-owned harness ID, run ID, subject SHA/tree identity, command, exit code, tool versions,
working directory, environment fingerprint, timestamps, stdout/stderr artifact references, and
content hashes where required.

Do not:

- fabricate, manually edit, or copy evidence from another revision;
- treat `skip` or `not_applicable` as `pass`;
- commit stale evidence as proof for the commit that contains the evidence;
- claim release/capacity/security properties without their blocking harnesses.

## Testing expectations

Follow strict TDD for product behavior:

1. Add or update a failing test/fixture that expresses the contract.
2. Implement the smallest coherent behavior.
3. Run the narrow test while iterating.
4. Run `make check`.
5. Run `make verify` when the change touches migrations, persistence, storage, integration wiring,
   harness execution, or release-critical behavior.

Test real boundaries:

- Unit tests may fake application ports.
- Integration tests use real PostgreSQL/MinIO.
- GitHub deterministic tests use frozen fixtures; production-level certification uses an isolated
  sandbox.
- Mutation fixtures must execute the mutation and assert the expected typed failure ID.

Never delete or weaken a test merely to make CI green unless the underlying requirement was
explicitly changed in the same patch.

## Security and tenancy invariants

- No secrets in source, fixtures, logs, evidence payloads, or examples.
- No unscoped database access once tenant/workspace persistence exists.
- Keep authorization, RBAC, separation-of-duties, writer-lease, fencing, and RLS checks explicit.
- AI/Copilot may assist explanation or drafting only; it must never influence readiness decisions,
  rankings, gates, lifecycle state, evidence, or approvals.
- No direct GitHub projection writes before the plan’s cutover and writer-ownership conditions pass.

## Change hygiene

- Keep lockfiles synchronized with manifest changes.
- Add migrations for persisted schema changes; include forward, rollback, and compatibility tests.
- Use Conventional Commit-style subjects (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`).
- Avoid unrelated formatting churn.
- Update docs when commands, architecture, public contracts, or operational behavior change.
- Do not add broad lint/type ignores, `any`, type suppression, or catch-all exceptions without a
  documented and narrowly scoped reason.
- Do not modify `.omo/plans/` checkboxes or continuation status without executable evidence.

## Definition of done

Before presenting work as complete:

- The implementation and tests satisfy the active todo and its dependencies.
- `make check` passes.
- `make verify` passes when applicable.
- Generated contracts and harness registry are current.
- Architecture boundaries remain green.
- New behavior has positive, negative, and failure-path coverage.
- Security/tenant/concurrency implications were considered.
- Documentation and examples are current.
- `git diff` contains only intended changes.
- The final report lists commands actually run and any validation not run.

.DEFAULT_GOAL := help

.PHONY: build-setup-assets check-setup-assets test-setup bootstrap check check-architecture check-contracts check-harness-registry check-preflight check-static clean doctor fix generate-contracts generate-harness-registry harness help infra-down infra-up migration-smoke recertify-foundation storage-smoke test test-domain test-frontend test-python verify test-security test-ops test-final certify-standard

help: ## Show supported development commands
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target>\n\nTargets:\n"} /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-28s %s\n", $$1, $$2}' $(MAKEFILE_LIST)


build-setup-assets: ## Build packaged first-run Setup Center assets
	node scripts/build_setup_assets.mjs

check-setup-assets: ## Fail when packaged Setup Center assets drift
	uv run python scripts/check_setup_assets.py

test-setup: ## Run setup workflow, API, CLI, security, and browser-model tests
	uv run pytest backend/tests/application/setup backend/tests/platform/configuration backend/tests/platform/secrets backend/tests/platform/setup backend/tests/adapters/github/test_setup_adapters.py backend/tests/interfaces/api/test_setup_app.py backend/tests/interfaces/api/test_persistent_setup_routes.py backend/tests/interfaces/test_setup_cli.py backend/tests/contracts/test_setup_generated_contracts.py backend/tests/test_setup_asset_drift.py
	node --test frontend/tests/setup/*.test.mjs

doctor: ## Validate required local tools and pinned versions
	python3 scripts/doctor.py

bootstrap: ## Install locked Python and Node dependencies
	uv sync --all-groups
	pnpm install --frozen-lockfile

check: check-static test ## Run the fast pre-push verification path

check-architecture: ## Enforce Python architecture import boundaries
	uv run python scripts/check_import_boundaries.py

check-static: check-preflight check-architecture check-contracts check-harness-registry check-anatomy check-setup-assets ## Run lint, format, type, contract, registry, architecture, and anatomy checks
	uv run ruff check backend/lib backend/src backend/tests scripts
	uv run ruff format --check backend/lib backend/src backend/tests scripts
	uv run basedpyright
	pnpm --dir frontend run check

fix: ## Apply safe Python and frontend formatter/linter fixes
	uv run ruff check --fix backend/lib backend/src backend/tests scripts
	uv run ruff format backend/lib backend/src backend/tests scripts
	pnpm --dir frontend run fix

generate-contracts: ## Regenerate JSON Schema and frontend Zod contracts
	uv run python scripts/generate_contracts.py

check-contracts: ## Fail when generated contract artifacts drift
	node --test scripts/zod_record_constraints.test.mjs
	uv run python scripts/generate_contracts.py --check

generate-harness-registry: ## Regenerate the machine-readable harness registry
	uv run python scripts/build_harness_registry.py

check-harness-registry: ## Fail when the harness registry drifts
	uv run python scripts/build_harness_registry.py --check

check-anatomy: ## Check anatomy docs for content/source drift
	python3 scripts/check_anatomy_drift.py docs/anatomy --repo-root .

check-preflight: ## Run ADR-006 foundation validation and behavioral tests
	node .omo/preflight/adr-006/validate.mjs
	node --test .omo/preflight/adr-006/validate.test.mjs

infra-up: ## Start PostgreSQL and MinIO and wait for health
	docker compose up -d --wait

infra-down: ## Stop local infrastructure and remove volumes
	docker compose down --volumes --remove-orphans

migration-smoke: ## Verify Alembic upgrade, rollback, and recovery
	DATABASE_URL=postgresql+psycopg://work_frontier:work_frontier@localhost:54329/work_frontier uv run python scripts/migration_smoke.py

storage-smoke: ## Verify MinIO object put/get/delete lifecycle
	MINIO_ENDPOINT_URL=http://localhost:9002 MINIO_ROOT_USER=work-frontier MINIO_ROOT_PASSWORD=work-frontier-minio uv run python scripts/minio_roundtrip.py

test: test-python test-frontend ## Run all unit tests

test-python: ## Run Python tests
	uv run pytest

test-domain: ## Run pure domain entity and authority suites
	uv run pytest backend/tests/domain

test-frontend: ## Run frontend tests
	pnpm --dir frontend run test

harness: ## Run one registry-backed harness by ID (use ID=...)
	uv run python scripts/run_harness.py --id $(ID) --repo-root .

recertify-foundation: ## Run the foundation closure and write supersession evidence
	uv run python scripts/run_harness.py --recertify-foundation --repo-root .

verify: check ## Run the full local CI-equivalent path with guaranteed infrastructure cleanup
	@set -eu; \
	trap '$(MAKE) infra-down' EXIT INT TERM; \
	$(MAKE) infra-up; \
	$(MAKE) migration-smoke; \
	$(MAKE) storage-smoke

clean: ## Remove local caches and build outputs (keeps evidence and lockfiles)
	rm -rf .pytest_cache .ruff_cache .basedpyright .coverage htmlcov
	find backend scripts -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf frontend/dist frontend/tsconfig.tsbuildinfo

test-security: ## Run all 15 registry-owned security harnesses on a clean revision
	@set -eu; trap '$(MAKE) infra-down' EXIT INT TERM; $(MAKE) infra-up; 	for id in $$(seq -f 'WF-HAR-SEC-%02g' 1 15); do $(MAKE) harness ID=$$id; done

test-ops: ## Run all Standard operational harnesses and scoped applicability checks
	@set -eu; trap '$(MAKE) infra-down' EXIT INT TERM; $(MAKE) infra-up; 	for id in WF-HAR-OPS-01 WF-HAR-OPS-02 WF-HAR-OPS-02-L WF-HAR-OPS-02-T WF-HAR-OPS-03 WF-HAR-OPS-04 WF-HAR-OPS-05 WF-HAR-OPS-06 WF-HAR-OPS-07; do $(MAKE) harness ID=$$id; done

test-final: ## Run final backend, browser, accessibility, and AI-off paths
	uv run pytest backend/tests/application/test_copilot.py backend/tests/contract/test_event_schemas.py backend/tests/contracts/test_harness_applicability.py backend/tests/operations/test_certification.py backend/tests/product/test_cutover_539.py backend/tests/release/test_certification.py backend/tests/security/test_hardening.py
	pnpm --dir frontend run test:final

certify-standard: ## Run all 68 harnesses and sign exact-revision Standard certification
	uv run python scripts/run_release_certification.py


.DEFAULT_GOAL := help

.PHONY: bootstrap check check-architecture check-contracts check-harness-registry check-preflight check-static clean doctor fix generate-contracts generate-harness-registry harness help infra-down infra-up migration-smoke recertify-foundation storage-smoke test test-frontend test-python verify

help: ## Show supported development commands
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target>\n\nTargets:\n"} /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-28s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

doctor: ## Validate required local tools and pinned versions
	python3 scripts/doctor.py

bootstrap: ## Install locked Python and Node dependencies
	uv sync --all-groups
	pnpm install --frozen-lockfile

check: check-static test ## Run the fast pre-push verification path

check-architecture: ## Enforce Python architecture import boundaries
	uv run python scripts/check_import_boundaries.py

check-static: check-preflight check-architecture check-contracts check-harness-registry ## Run lint, format, type, contract, registry, and architecture checks
	uv run ruff check backend/src backend/tests scripts
	uv run ruff format --check backend/src backend/tests scripts
	uv run basedpyright
	pnpm --dir frontend run check

fix: ## Apply safe Python and frontend formatter/linter fixes
	uv run ruff check --fix backend/src backend/tests scripts
	uv run ruff format backend/src backend/tests scripts
	pnpm --dir frontend run fix

generate-contracts: ## Regenerate JSON Schema and frontend Zod contracts
	uv run python scripts/generate_contracts.py

check-contracts: ## Fail when generated contract artifacts drift
	uv run python scripts/generate_contracts.py --check

generate-harness-registry: ## Regenerate the machine-readable harness registry
	uv run python scripts/build_harness_registry.py

check-harness-registry: ## Fail when the harness registry drifts
	uv run python scripts/build_harness_registry.py --check

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

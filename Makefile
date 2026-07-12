.PHONY: bootstrap check-architecture check-contracts check-preflight check-static generate-contracts infra-down infra-up migration-smoke storage-smoke test

bootstrap:
	uv sync --all-groups
	pnpm install --frozen-lockfile

check-architecture:
	uv run python scripts/check_import_boundaries.py

check-static:
	$(MAKE) check-preflight
	$(MAKE) check-architecture
	$(MAKE) check-contracts
	uv run ruff check backend/src backend/tests scripts
	uv run ruff format --check backend/src backend/tests scripts
	uv run basedpyright
	pnpm --dir frontend run check

generate-contracts:
	uv run python scripts/generate_contracts.py

check-contracts:
	uv run python scripts/generate_contracts.py --check

check-preflight:
	node .omo/preflight/adr-006/validate.mjs
	node --test .omo/preflight/adr-006/validate.test.mjs

infra-up:
	docker compose up -d --wait

infra-down:
	docker compose down --volumes --remove-orphans

migration-smoke:
	DATABASE_URL=postgresql+psycopg://work_frontier:work_frontier@localhost:54329/work_frontier uv run python scripts/migration_smoke.py

storage-smoke:
	MINIO_ENDPOINT_URL=http://localhost:9002 MINIO_ROOT_USER=work-frontier MINIO_ROOT_PASSWORD=work-frontier-minio uv run python scripts/minio_roundtrip.py

test:
	uv run pytest
	pnpm --dir frontend run test

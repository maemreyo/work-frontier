# Development guide

This guide is the supported local-development path for humans and coding agents.

## Prerequisites

Required for the normal check path:

- Git
- Python `3.13.5`
- [`uv`](https://docs.astral.sh/uv/)
- Node `22.23.1`
- pnpm `10.20.0`

Required for the full verification path:

- Docker with Compose v2

Version sources are intentionally redundant and must stay aligned:

| Tool | Local pin | Manifest/CI pin |
| --- | --- | --- |
| Python | `.python-version` | `pyproject.toml`, `.github/workflows/ci.yml` |
| Node | `.nvmrc` | root/frontend `package.json`, CI |
| pnpm | root `package.json` | frontend `package.json`, CI |

Run `make doctor` after switching branches or changing toolchains.

## First-time setup

```sh
git clone https://github.com/maemreyo/work-frontier.git
cd work-frontier
cp .env.example .env
make doctor
make bootstrap
make check
```

`make bootstrap` uses lockfiles and installs all Python dependency groups plus the root/frontend pnpm
workspace.

## Daily commands

```sh
make help
make check
make test-python
make test-frontend
make fix
```

`make check` is the fast pre-push path. It covers:

- ADR-006 preflight validation and behavioral tests;
- architecture import boundaries;
- generated contract drift;
- harness registry drift;
- Ruff lint and format checks;
- basedpyright strict typing;
- frontend Biome, TypeScript, and Vitest.

## Full verification

```sh
make verify
```

The target runs the fast check path, starts PostgreSQL and MinIO, executes migration and object-store
smoke tests, and always tears the Compose project down through a cleanup trap.

To inspect infrastructure manually:

```sh
make infra-up
docker compose ps
make migration-smoke
make storage-smoke
make infra-down
```

## Contract workflow

After changing a canonical Pydantic contract:

```sh
make generate-contracts
git diff -- contracts frontend/src/contracts
make check-contracts
make check
```

Generated TypeScript/Zod files are outputs, not authoring surfaces.

## Harness registry workflow

After changing the quality harness catalog or implemented command mapping:

```sh
make generate-harness-registry
git diff -- .omo/harness-registry.json
make check-harness-registry
```

A registry entry is not “implemented” merely because prose exists. Its command, evidence behavior,
applicability, and blocking semantics must be executable.

## Evidence workflow

Evidence lives under `.omo/evidence/` and must be tied to the exact subject revision. Local evidence
is useful for iteration; CI evidence is preferred for durable certification.

Do not:

- reuse evidence from a different SHA;
- edit result JSON by hand;
- count skipped/not-applicable blockers as passes;
- include secrets or sensitive payloads in stdout, stderr, property bags, or fixtures.

## Troubleshooting

### Wrong Python, Node, or pnpm version

Run `make doctor`, then use your preferred version manager to install the exact version shown. Re-run
`make bootstrap` after switching versions.

### Lockfile or generated-file drift

Do not patch the generated output manually. Run the relevant generation target and commit the source
change plus deterministic output together.

### Docker ports already in use

The local Compose baseline uses ports defined in `docker-compose.yml`. Stop the conflicting service or
override the host port in a personal, uncommitted Compose override. Do not change shared defaults only
to accommodate one workstation.

### Dirty infrastructure after a failed test

```sh
make infra-down
docker compose ps -a
```

`make verify` normally performs this cleanup automatically.

### CI differs from local

Confirm the exact tool versions with `make doctor`, use locked installs, and run `make verify`. CI
intentionally calls the same Make targets. If behavior still differs, capture the command, tool
versions, environment variables, and complete logs rather than adding a CI-only workaround.

## Adding a new developer command

Expose stable workflows as a documented Make target. The target must:

- be deterministic and non-interactive by default;
- fail on the first real error;
- clean up resources on failure;
- work in CI without hidden workstation state;
- appear in `make help`;
- be referenced by `AGENTS.md` or this guide when it becomes part of the golden path.

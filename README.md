# Work Frontier

Work Frontier is a standalone dependency-aware readiness control plane under dependency-ordered
implementation. The current executable repository is the foundation implementation: canonical contracts,
architecture enforcement, harness/evidence infrastructure, and PostgreSQL/MinIO verification. Product
runtime services and the Control Room are added only by their owning todos.

## Quick start

```sh
make doctor
make bootstrap
make check
```

Run the full local CI-equivalent path, including PostgreSQL migration and MinIO object-storage smokes:

```sh
make verify
```

## Supported toolchain

- Python `3.13.5` through `uv`
- Node `22.23.1`
- pnpm `10.20.0`
- Docker Compose v2 for integration smokes

## Common commands

```sh
make help
make check
make verify
make fix
make generate-contracts
make generate-harness-registry
```

## Repository guide

- [`AGENTS.md`](AGENTS.md) — canonical engineering and coding-agent rules
- [`CLAUDE.md`](CLAUDE.md) — Claude-specific workflow
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contribution and review process
- [`docs/development.md`](docs/development.md) — setup, daily workflow, and troubleshooting
- [`.omo/plans/full-product-implementation.md`](.omo/plans/full-product-implementation.md) —
  dependency-ordered product plan

Do not infer implementation status from target architecture prose alone. Source, tests, executable
contracts, registered harnesses, and evidence for the exact subject revision are authoritative.

# Final deployment, backup, recovery, and upgrade runbook

## Capability truth

`infra/compose/compose.production.yaml` is a hardened **single-node** self-host profile. It is not HA. The managed Kubernetes template declares `managed_standard` only when PostgreSQL, object storage, ingress TLS, backup, and at least two web replicas are supplied by the operator.

## Deploy

Build the immutable image from `infra/docker/Dockerfile`, pin it by digest, inject secret references rather than literal values, apply migrations once, then start web, worker, and scheduler independently. Require TLS at ingress, PostgreSQL (`sslmode=verify-full`), and object storage.

## Backup and restore

Record PostgreSQL LSN, `pg_dump -Fc`, object inventory and SHA-256 hashes in one backup manifest. The restore drill creates a clean database, restores the dump, validates `alembic_version`, verifies object hashes, starts the API, and records RPO/RTO. Standard limits are RPO ≤ 5 minutes and RTO ≤ 60 minutes.

## Upgrade and rollback

Run `make migration-smoke` against a copy of live-size data, deploy worker/scheduler compatibility first, then web. Keep the previous image digest and reversible migration boundary. Roll back application images before database downgrade; never downgrade past an irreversible migration without a documented forward-fix.

## Failure and soak certification

`WF-HAR-OPS-04` is a real 72-hour probe and cannot be shortened for GA. `WF-HAR-OPS-05` restarts PostgreSQL between worker runs and requires zero acknowledged-event loss. `WF-HAR-OPS-06` restores into a clean database and measures RPO/RTO.

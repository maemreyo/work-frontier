# Module: Deployment Infrastructure

**Path:** `infra`
**Role:** Production deployment manifests, Docker image, Kubernetes resources, and observability configuration.

## Public interface

- `docker-compose -f infra/compose/compose.production.yaml up` — production Compose stack.
- `docker build -f infra/docker/Dockerfile .` — production Docker image.
- `kubectl apply -f infra/kubernetes/work-frontier.yaml` — Kubernetes deployment.
- `infra/observability/prometheus.yml` — Prometheus scraping configuration.
- `infra/observability/alerts.yml` — Alertmanager alerting rules.

## Internal structure

- `compose/compose.production.yaml` — production Compose with postgres, minio, and web services.
- `docker/Dockerfile` — production Docker image with uv-installed dependencies.
- `kubernetes/work-frontier.yaml` — Kubernetes Deployment, Service, ConfigMap, and Secret manifests.
- `observability/prometheus.yml` — Prometheus scrape target configuration.
- `observability/alerts.yml` — Alertmanager rule definitions.

## Depends on

- **`control-plane-api`** — the web process container serves the FastAPI application (`infra/docker/Dockerfile:1`)
- external: `postgresql` — production database dependency (`infra/compose/compose.production.yaml:5`)
- external: `minio` — production object storage dependency (`infra/compose/compose.production.yaml:15`)

## Used by

None confirmed.

## Data & side effects

- Declares deployment topology; no runtime behavior within this repository.

## Notes / discrepancies vs existing docs

- Production deployment requires externally managed PostgreSQL and MinIO instances; the Compose file provides local equivalents for testing.

---

_Traced from source on 2026-07-14. Files examined in depth: all 14 files._

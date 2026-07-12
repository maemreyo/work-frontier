---
title: "Deployment Profiles"
version: "1.0.0"
status: "canonical"
owner: "work-frontier"
last_updated: "2026-07-12"
requirement_prefix: "WF-OPS"
---

# Deployment Profiles

Work Frontier runs as a modular monolith: web, worker, and scheduler share a codebase
but run as separate processes. PostgreSQL handles persistence and durable queuing. Object
storage handles file blobs. Two deployment profiles exist: hosted and self-hosted.

---

## Architecture Truth

The system has three runtime processes, one database, and one object store:

```
┌──────────────────────────────────────────────────────┐
│                     Load Balancer                     │
├─────────────┬──────────────────┬─────────────────────┤
│   Web API   │   Worker Pool    │   Scheduler         │
│  (FastAPI)  │  (background)    │  (cron-like)        │
├─────────────┴──────────────────┴─────────────────────┤
│              PostgreSQL (single writer)               │
├──────────────────────────────────────────────────────┤
│              Object Storage (MinIO / S3)              │
└──────────────────────────────────────────────────────┘
```

### Single-Writer HA

PostgreSQL runs as a single writer with streaming replication to one or more read
replicas. This is high-availability for reads, not for writes.

| Property | Behavior |
|----------|----------|
| Write availability | Single writer. If it fails, writes stall until failover completes. |
| Read availability | Read replicas serve reads. Failover is automatic. |
| Failover time | 30-60 seconds (pg_auto_failover or Patroni) |
| Data consistency | Synchronous replication to one replica (zero data loss on failover) |
| Write capacity | Single node. Cannot scale writes horizontally. |

**Docker Compose is not HA.** The development Docker Compose setup runs a single
PostgreSQL instance with no replication. Docker Compose may be used as a production
standalone single-node deployment, but it is not high-availability. HA requires
replication, failover, and load balancing that Compose does not provide. Do not
deploy Docker Compose and call it HA.

### Warm DR

Disaster recovery uses warm standby in a secondary region.

| Property | Behavior |
|----------|----------|
| Primary region | Active. All writes and reads. |
| DR region | Warm standby. Receives replicated data. No active traffic. |
| Failover | Manual. Operator promotes DR region. |
| RPO (Recovery Point Objective) | ≤ 5 minutes (async replication lag) |
| RTO (Recovery Time Objective) | ≤ 60 minutes (failover + DNS + verification) |
| Event durability | ≥ 99.99% (zero acknowledged event loss) |
| Data loss window | ≤ 5 minutes of writes may be lost on failover |
| DR drill frequency | Quarterly (WF-HAR-OPS-06) |

> See [backup-restore-dr.md](../operations/backup-restore-dr.md) for full DR architecture and failover procedures.

---

## Profile: Hosted (WF-OPS-HOSTED)

Managed deployment by the Work Frontier team. Users do not manage infrastructure.

| Component | Specification |
|-----------|--------------|
| Web API | Managed container service (2+ replicas) |
| Worker Pool | Managed container service (auto-scaling 2-8 replicas) |
| Scheduler | Single replica with leader election |
| PostgreSQL | Managed service, multi-AZ, automated backups |
| Object Storage | Managed S3-compatible service |
| Load Balancer | Managed load balancer with health checks |
| SSL/TLS | Managed certificates, auto-renewal |

### Hosted SLOs

| SLO | Target | Measurement |
|-----|--------|-------------|
| Availability | 99.9% monthly | WF-OPS-SLO-01 |
| p95 API latency | < 500 ms (Control Room read) | WF-OPS-SLO-02 |
| Event durability | ≥ 99.99%, zero acknowledged loss | WF-OPS-SLO-03 |
| Data durability | Managed service guarantee (provider SLA) | Not a product-level guarantee |
| Backup RPO | ≤ 5 minutes | WF-OPS-BKP-01 |
| Backup RTO | ≤ 60 minutes | WF-OPS-BKP-02 |

> See [slo-observability.md](../operations/slo-observability.md) for full SLO definitions and alerting.

### Hosted Limitations

| Limitation | Why |
|-----------|-----|
| Single region deployment | Multi-region adds complexity; available on request for Large envelope |
| No custom domain (initially) | Requires DNS management; available post-GA |
| Managed upgrades | Team controls upgrade timing; customers notified 72h in advance |

---

## Profile: Self-Hosted (WF-OPS-SELF-HOSTED)

Deployed and managed by the customer. We provide the container images and documentation.

| Component | Minimum Specification |
|-----------|----------------------|
| Web API | 1 container, 2 CPU / 4 GB RAM |
| Worker Pool | 1 container, 2 CPU / 4 GB RAM |
| Scheduler | 1 container, 0.5 CPU / 1 GB RAM |
| PostgreSQL | 16, 4 CPU / 16 GB RAM, 100 GB SSD |
| Object Storage | MinIO or S3-compatible, 100 GB |
| Load Balancer | Customer-provided (nginx, Traefik, cloud LB) |

### Self-Hosted SLOs

| SLO | Target | Notes |
|-----|--------|-------|
| Availability | Customer-managed | Depends on customer infrastructure |
| Data durability | Customer-managed | Depends on backup strategy |
| Support response | 24h (business days) | For self-hosted tier |

### Self-Hosted Capability Truth

| Capability | Hosted | Self-Hosted |
|-----------|--------|-------------|
| HA (write failover) | Yes (managed single-writer + streaming replication) | Customer must configure replication and failover |
| HA (read scaling) | Yes (managed replicas) | Customer adds read replicas |
| Compose as production | N/A (managed containers) | Standalone single-node only; not HA |
| Auto-scaling workers | Yes (managed) | No (customer scales manually) |
| Automated backups | Yes (managed) | Customer responsibility |
| Monitoring | Included (dashboards + alerts) | Customer sets up (we provide config) |
| Logging | Centralized, retained 90 days | Customer responsibility |
| SSL/TLS | Managed | Customer responsibility |
| Upgrades | Managed, scheduled | Customer responsibility |
| DR | Warm standby, managed | Customer responsibility |
| Release certification | Same artifact as hosted | Same artifact as hosted |

**What self-hosted is not:** Self-hosted means you run the containers. It does not
mean you get hosted-level HA for free. A single Compose deployment is a standalone
single-node deployment suitable for small teams or single-tenant use. HA requires
configuration (replication, failover, load balancing) that the customer must set up
and operate. Both hosted and self-hosted use the same release certification artifact.

---

## Deployment Sizing

### Standard Envelope Deployment

| Component | Resources | Replicas |
|-----------|----------|----------|
| Web API | 2 CPU, 4 GB RAM | 2 |
| Worker Pool | 2 CPU, 4 GB RAM | 2 |
| Scheduler | 0.5 CPU, 1 GB RAM | 1 |
| PostgreSQL | 4 CPU, 16 GB RAM, 50 GB SSD | 1 writer + 1 read replica |
| Object Storage | 200 GB | 1 (or managed S3) |

### Large Envelope Deployment

| Component | Resources | Replicas |
|-----------|----------|----------|
| Web API | 4 CPU, 8 GB RAM | 4 |
| Worker Pool | 4 CPU, 8 GB RAM | 4-8 (auto-scaling) |
| Scheduler | 1 CPU, 2 GB RAM | 1 with standby |
| PostgreSQL | 16 CPU, 64 GB RAM, 500 GB SSD | 1 writer + 3 read replicas |
| Object Storage | 2 TB | Multi-AZ |

---

## Environment Matrix

| Environment | Profile | Purpose | Data |
|-------------|---------|---------|------|
| Local development | Docker Compose | Developer workstation | Synthetic, ephemeral |
| CI | Docker Compose (isolated) | Automated harness execution | Synthetic, per-run |
| Staging | Hosted (scaled down) | Pre-release validation | Anonymized production subset |
| Production | Hosted or Self-Hosted | Live system | Real data |
| DR | Warm standby | Disaster recovery | Replicated from production |

---

## Network Requirements

### Inbound

| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 443 | HTTPS | Load balancer | Web API |
| 5432 | TCP | Internal only | PostgreSQL (app connections) |
| 9000 | HTTPS | Internal only | Object storage (MinIO console) |

### Outbound

| Destination | Port | Purpose |
|-------------|------|---------|
| PostgreSQL | 5432 | App ↔ Database |
| Object Storage | 443 | App ↔ S3/MinIO |
| DNS | 53 | Name resolution |
| NTP | 123 | Time synchronization |

---

## Container Images

| Image | Registry | Tagging |
|-------|----------|---------|
| `workfrontier/web` | ghcr.io | `v{semver}`, `latest` |
| `workfrontier/worker` | ghcr.io | `v{semver}`, `latest` |
| `workfrontier/scheduler` | ghcr.io | `v{semver}`, `latest` |

All images are multi-arch (amd64 + arm64). Images are scanned for vulnerabilities
before publish. Only signed images are available in production registries.

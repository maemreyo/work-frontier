---
title: "SLOs and Observability"
version: "1.0.0"
status: "canonical"
owner: "work-frontier"
last_updated: "2026-07-12"
requirement_prefix: "WF-OPS"
---

# SLOs and Observability

You cannot operate what you cannot see. Observability is not logging. It is the
ability to answer arbitrary questions about system behavior from production data,
without deploying new code.

---

## Service Level Objectives

SLOs define what "working" means in measurable terms. They are not aspirations.
They are thresholds that, when breached, trigger action.

### Availability SLO

| Metric | Target | Window | Measurement |
|--------|--------|--------|-------------|
| Uptime | 99.9% | Monthly | WF-OPS-SLO-01 |
| Error rate (5xx) | < 0.1% | Rolling 24h | WF-OPS-SLO-02 |
| Failed requests | < 0.1% of total | Rolling 24h | WF-OPS-SLO-02 |

**Error budget:** 99.9% uptime allows 43.8 minutes of downtime per month. When the
error budget is consumed, no new features ship until reliability work restores the
budget.

### Latency SLO

| Metric | Target | Measurement |
|--------|--------|-------------|
| Control Room read p95 | < 500 ms | WF-OPS-SLO-04 |
| Program overview / why-blocked p95 | < 1,000 ms | WF-OPS-SLO-04 |
| Webhook-to-decision p95 | < 30,000 ms | WF-OPS-SLO-04 |
| Manual revalidation (Standard) | < 60,000 ms | WF-OPS-SLO-04 |
| Full solve (Standard) | < 5,000 ms | WF-OPS-SLO-04 |
| Full solve (Large) | < 30,000 ms | WF-OPS-SLO-04 |
| Incremental projection | < 2,000 ms | WF-OPS-SLO-04 |
| Worker job pickup | < 1,000 ms p95 | WF-OPS-SLO-05 |

> See [performance-envelope.md](../quality/performance-envelope.md) for full latency tables by envelope.

### Data SLO

| Metric | Target | Measurement |
|--------|--------|-------------|
| Data durability | No loss under normal operations | WF-OPS-SLO-06 |
| Event durability | ≥ 99.99%, zero acknowledged loss | WF-OPS-SLO-07 |
| State model | Current state + append-only evidence records (not full event source) | Architecture constraint |
| Backup RPO | ≤ 5 minutes | WF-OPS-BKP-01 |
| Backup RTO | ≤ 60 minutes | WF-OPS-BKP-02 |
| DR RPO | ≤ 5 minutes | WF-OPS-BKP-03 |
| DR RTO | ≤ 60 minutes | WF-OPS-BKP-04 |

> See [backup-restore-dr.md](../operations/backup-restore-dr.md) for backup strategy and DR procedures.

### Dependency SLO

| Dependency | Availability Target | Latency Target | Measurement |
|-----------|--------------------|----------------|-------------|
| PostgreSQL | 99.99% (managed) | < 10 ms p95 | WF-OPS-SLO-08 |
| Object Storage | 99.99% (managed) | < 50 ms p95 | WF-OPS-SLO-08 |
| GitHub API | 99.9% (external) | < 500 ms p95 | WF-OPS-SLO-09 |

> See [deployment-profiles.md](../operations/deployment-profiles.md) for hosted vs. self-hosted capability truth.

---

## Observability Pillars

### Metrics

Numeric measurements over time. Answers "how much" and "how fast."

| Metric Category | Examples | Collection |
|----------------|----------|------------|
| Request rate | Requests per second by endpoint | Application metrics |
| Error rate | 5xx count, rate by endpoint | Application metrics |
| Latency | p50/p95/p99 by endpoint (see latency SLO above) | Application metrics |
| Event durability | Acknowledged events persisted / total acknowledged | Application metrics |
| Queue depth | Pending jobs by type | Database query |
| Worker utilization | Active jobs, idle workers | Application metrics |
| Database connections | Active, idle, waiting | pg_stat_activity |
| Database query duration | p50/p95 by query type | pg_stat_statements |
| Object storage operations | Upload/download count, bytes | Storage metrics |
| Memory usage | RSS by process | OS metrics |
| CPU usage | Utilization by process | OS metrics |
| Disk usage | Used, available by mount | OS metrics |

### Logs

Timestamped events with context. Answers "what happened."

| Log Category | Level | Retention |
|-------------|-------|-----------|
| Application logs | INFO, WARN, ERROR | 30 days |
| Access logs | INFO | 30 days |
| Audit logs | INFO (immutable) | 1 year |
| Migration logs | INFO | Permanent |
| Security events | WARN, ERROR | 1 year |

**Structured logging only.** Every log line is JSON with these fields:

```json
{
  "timestamp": "2026-07-12T10:30:00Z",
  "level": "info",
  "service": "web",
  "trace_id": "abc123",
  "span_id": "def456",
  "message": "Request processed",
  "endpoint": "/api/workspaces",
  "duration_ms": 142,
  "status_code": 200
}
```

No unstructured log lines. No log lines without trace_id.

### Traces

Requests tracked across service boundaries. Answers "where is time spent."

| Property | Value |
|----------|-------|
| Protocol | OpenTelemetry |
| Sampling | 100% for errors, 10% for normal requests |
| Propagation | W3C TraceContext |
| Storage | Exported to tracing backend (Grafana Tempo, Jaeger, or equivalent) |

Every request gets a trace_id that follows it from web API through worker processing
to database queries. This allows answering "why is this request slow" without guessing.

### Incident Telemetry

Incident telemetry is domain-aware and privacy-respecting:

| Property | Rule |
|----------|------|
| Domain awareness | Telemetry identifies Work Frontier domain context (item IDs, program IDs, gate states) for debugging |
| PII redaction | User emails, names, and tracker credentials redacted from all telemetry output |
| Evidence records | Append-only; no full event source replay from telemetry |
| Retention | 30 days for operational telemetry, 1 year for incident telemetry |
| Access | On-call engineers; post-mortem participants during incident window |

---

## Alerting

### Alert Tiers

| Tier | Response | Channel | Examples |
|------|----------|---------|----------|
| P1 (Critical) | Immediate, all hands | PagerDuty + Slack + SMS | Service down, data loss, security breach |
| P2 (High) | Within 1 hour | PagerDuty + Slack | Error budget burning, latency SLO breach |
| P3 (Medium) | Within 4 hours | Slack | Resource pressure, degraded dependency |
| P4 (Low) | Next business day | Email, ticket | Non-urgent anomalies, capacity warnings |

### Critical Alerts (P1)

| Alert | Condition | Action |
|-------|-----------|--------|
| ServiceDown | Health check fails for > 2 minutes | Investigate immediately, page on-call |
| HighErrorRate | 5xx rate > 1% for > 5 minutes | Investigate, may page |
| EventDurabilityDrop | Acknowledged event loss detected | Immediate investigation, potential data loss incident |
| DatabaseConnectionPoolExhausted | All connections in use for > 1 minute | Investigate, may restart |
| DiskSpaceCritical | < 10% free on any mount | Emergency cleanup or expansion |
| SecurityEventDetected | Auth bypass or injection attempt | Immediate investigation, potential incident |

### Warning Alerts (P2)

| Alert | Condition | Action |
|-------|-----------|--------|
| ErrorBudgetBurning | Projected to consume budget in < 7 days | Reliability sprint |
| LatencySLOBreach | p95 > target for > 10 minutes | Investigate regression |
| QueueBacklogGrowing | Queue depth increasing for > 30 minutes | Check worker health |
| DatabaseReplicationLag | Replica lag > 10 seconds | Check network, replication health |

---

## Dashboards

### Operational Dashboard

Shows current system health at a glance.

| Panel | Data Source | Refresh |
|-------|------------|---------|
| Request rate (by endpoint) | Application metrics | 30s |
| Error rate (by endpoint) | Application metrics | 30s |
| Latency distribution (p50/p95/p99) | Application metrics | 30s |
| Active workers / idle workers | Application metrics | 30s |
| Queue depth (by job type) | Database | 60s |
| Database connection count | pg_stat_activity | 30s |
| CPU / Memory / Disk | OS metrics | 30s |

### SLO Dashboard

Shows error budget consumption and trend.

| Panel | Data Source | Refresh |
|-------|------------|---------|
| Availability (monthly) | Derived from uptime | 5m |
| Error budget remaining | Derived from error rate | 5m |
| Latency SLO status | Application metrics | 5m |
| Trend (7-day, 30-day) | Historical metrics | 1h |

### Investigation Dashboard

Drill-down for debugging specific issues.

| Panel | Data Source | Refresh |
|-------|------------|---------|
| Trace viewer | Tracing backend | On-demand |
| Slow queries | pg_stat_statements | 5m |
| Error logs (last hour) | Log storage | 30s |
| Worker job history | Database | 5m |

---

## Monitoring Stack

| Component | Recommended | Alternative |
|-----------|------------|-------------|
| Metrics collection | Prometheus | VictoriaMetrics |
| Metrics storage | Prometheus / Mimir | VictoriaMetrics |
| Log aggregation | Loki | Elasticsearch |
| Tracing | Grafana Tempo | Jaeger |
| Dashboards | Grafana | — |
| Alerting | Alertmanager + PagerDuty | Opsgenie |

The monitoring stack is separate from the application stack. It must not share
resources (CPU, memory, disk) with production workloads.

---

## SLO Review Process

| Activity | Frequency | Owner |
|----------|-----------|-------|
| Error budget review | Weekly | Engineering lead |
| SLO target adjustment | Quarterly | Engineering lead + stakeholders |
| Alert tuning (reduce noise) | Monthly | On-call rotation |
| Dashboard review | Quarterly | Engineering lead |
| Runbook review | Quarterly | On-call rotation |

SLO targets are reviewed quarterly. They may tighten (if the system is reliably
exceeding targets) or loosen (if targets are causing excessive noise without
improving user experience). Target changes are documented with justification.

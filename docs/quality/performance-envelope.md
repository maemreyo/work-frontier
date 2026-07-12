---
title: "Performance Envelope"
version: "1.0.0"
status: "canonical"
owner: "work-frontier"
last_updated: "2026-07-12"
requirement_prefix: "WF-PERF"
---

# Performance Envelope

Performance is not a single number. It is an envelope of dimensions that together
define what the system can handle. Two envelopes are defined: Standard and Large.
Every envelope dimension has a measured target and a verification harness.

---

## Envelope Definitions

### Standard Envelope (WF-PERF-STD)

The default operating envelope. Most deployments run here.

| Dimension | Target | Verification Harness |
|-----------|--------|---------------------|
| Items | 10,000 | WF-HAR-OPS-02 |
| Edges (relationships between items) | 50,000 | WF-HAR-OPS-02 |
| Repositories | 100 | WF-HAR-OPS-02 |
| Concurrent users | 50 | WF-HAR-OPS-02 |
| Queue depth | 5,000 pending jobs | WF-HAR-OPS-02 |
| Database size | 10 GB | WF-HAR-OPS-02 |

### Large Envelope (WF-PERF-LRG)

For organizations with heavy workloads. Requires explicit sizing beyond defaults.

| Dimension | Target | Verification Harness |
|-----------|--------|---------------------|
| Items | 100,000 | WF-HAR-OPS-02-L |
| Edges | 500,000 | WF-HAR-OPS-02-L |
| Repositories | 1,000 | WF-HAR-OPS-02-L |
| Concurrent users | 200 | WF-HAR-OPS-02-L |
| Queue depth | 50,000 pending jobs | WF-HAR-OPS-02-L |
| Database size | 100 GB | WF-PERF-LRG-01 |

**Large envelope requires infrastructure changes.** It is not a configuration toggle.
Specific minimum resources are listed in the deployment profiles document.

### Tenant Aggregate Envelope (WF-PERF-TENANT)

Upper bounds for the aggregate state a single tenant's data can reach across all
programs and items. Exceeding these limits requires architectural consultation.

| Dimension | Target | Verification Harness |
|-----------|--------|---------------------|
| Items (total across all programs) | 1,000,000 | WF-HAR-OPS-02-T |
| Edges (total across all items) | 5,000,000 | WF-HAR-OPS-02-T |
| Repositories (total connected) | 10,000 | WF-HAR-OPS-02-T |

> These are upper bounds, not recommended operating sizes. Performance degrades as
> limits approach. Standard and Large envelopes are the supported operating targets.

---

## Latency Targets

All latency targets are measured at the 95th percentile (p95) unless stated otherwise.

### Work Frontier Core Latency (Agreed Targets)

| Operation | Standard p95 | Large p95 | Incremental p95 | Measurement |
|-----------|-------------|-----------|-----------------|-------------|
| Control Room read | < 500 ms | < 1,500 ms | — | WF-HAR-PRODUCT-01 |
| Program overview / why-blocked | < 1,000 ms | < 3,000 ms | — | WF-HAR-PRODUCT-02 |
| Webhook-to-decision | < 30,000 ms | < 60,000 ms | — | WF-HAR-PRODUCT-03 |
| Manual revalidation | < 60,000 ms | < 180,000 ms | — | WF-HAR-PRODUCT-04 |
| Full solve | < 5,000 ms | < 30,000 ms | — | WF-HAR-OPS-02 |
| Incremental projection | — | — | < 2,000 ms | WF-HAR-OPS-02 |

### API Response Latency

| Endpoint Category | Standard p95 | Large p95 | Measurement |
|-------------------|-------------|-----------|-------------|
| Health check | 50 ms | 100 ms | WF-HAR-OPS-01 |
| Single-item read | 200 ms | 500 ms | WF-PERF-03 |
| Single-item write | 300 ms | 800 ms | WF-PERF-03 |
| List with pagination | 500 ms | 1,500 ms | WF-PERF-04 |
| Complex query (joins) | 1,000 ms | 3,000 ms | WF-PERF-04 |
| Report generation | 5,000 ms | 15,000 ms | WF-PERF-05 |
| File upload (< 10 MB) | 2,000 ms | 5,000 ms | WF-PERF-06 |

### Worker Processing Latency

| Operation | Standard p95 | Large p95 | Measurement |
|-----------|-------------|-----------|-------------|
| Job pickup to start | 500 ms | 1,000 ms | WF-PERF-07 |
| Simple job execution | 2,000 ms | 5,000 ms | WF-PERF-07 |
| Complex job execution | 10,000 ms | 30,000 ms | WF-PERF-07 |
| Job retry delay (first) | 5,000 ms | 5,000 ms | WF-PERF-07 |

### Scheduler Latency

| Operation | Standard p95 | Large p95 | Measurement |
|-----------|-------------|-----------|-------------|
| Schedule trigger to execution | 2,000 ms | 5,000 ms | WF-PERF-08 |

---

## Throughput Targets

| Metric | Standard | Large | Measurement |
|--------|---------|-------|-------------|
| Requests per second (sustained) | 100 | 400 | WF-HAR-OPS-02 |
| Jobs processed per minute | 200 | 800 | WF-HAR-OPS-02 |
| Concurrent active connections | 50 | 200 | WF-HAR-OPS-02 |
| Database transactions per second | 500 | 2,000 | WF-PERF-09 |

---

## Resource Targets

### Standard Envelope

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU (total across all components) | 4 cores | 8 cores |
| Memory (total) | 8 GB | 16 GB |
| Disk (database) | 20 GB SSD | 50 GB SSD |
| Disk (object storage) | 50 GB | 200 GB |
| Network | 100 Mbps | 1 Gbps |

### Large Envelope

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU (total across all components) | 16 cores | 32 cores |
| Memory (total) | 32 GB | 64 GB |
| Disk (database) | 200 GB SSD | 500 GB SSD |
| Disk (object storage) | 500 GB | 2 TB |
| Network | 1 Gbps | 10 Gbps |

---

## Scalability Limits

These are known limits, not aspirational targets. The system is not designed to
operate beyond them without architectural changes.

| Dimension | Hard Limit | Consequence of Exceeding |
|-----------|-----------|-------------------------|
| Single database connection pool | 200 connections | Connection starvation, request queuing |
| Single worker concurrency | 50 concurrent jobs | Memory exhaustion, OOM kill |
| Single queue partition | 100,000 pending items | Dequeue latency degrades linearly |
| Max upload size | 100 MB | Request rejected at application layer |
| Max report dataset | 1,000,000 rows | Query timeout (configurable, default 60s) |
| Max workspace members | 500 | Permission check latency degrades |

---

## Performance Harnesses

### WF-PERF-01: Baseline Establishment

| Field | Value |
|-------|-------|
| **Command** | `k6 run tests/perf/baseline.js --env ENVELOPE=standard` |
| **What it runs** | Measures baseline latency and throughput with minimal load |
| **Artifact** | `evidence/perf/baseline-standard.json` |
| **Purpose** | Establishes the reference point for regression detection |

### WF-PERF-02: Standard Envelope Load

| Field | Value |
|-------|-------|
| **Command** | `k6 run tests/perf/standard-load.js --out json=evidence/perf/standard-load.json` |
| **What it runs** | Sustained load at Standard envelope limits for 30 minutes |
| **Pass criteria** | All p95 latencies within Standard targets. Error rate < 0.1%. |
| **Blocks release** | Yes |

### WF-PERF-02-L: Large Envelope Load

| Field | Value |
|-------|-------|
| **Command** | `k6 run tests/perf/large-load.js --env ENVELOPE=large --out json=evidence/perf/large-load.json` |
| **What it runs** | Sustained load at Large envelope limits for 30 minutes |
| **Pass criteria** | All p95 latencies within Large targets. Error rate < 0.1%. |
| **Blocks release** | Only for a release declaring Large-envelope support; otherwise not applicable |

### WF-HAR-OPS-02-T: Tenant Aggregate Capacity

| Field | Value |
|-------|-------|
| **Command** | `k6 run tests/ops/tenant-aggregate-capacity.js --out json=evidence/ops/tenant-aggregate-capacity.json` |
| **What it runs** | Correctness, isolation, resource growth, and query behavior at the Tenant Aggregate upper bounds |
| **Pass criteria** | No correctness loss, isolation breach, unbounded resource growth, or silent truncation; architectural consultation threshold is reported |
| **Blocks release** | Only for a release explicitly certifying Tenant Aggregate bounds; otherwise not applicable |

### WF-PERF-03: Single-Item Operations

| Field | Value |
|-------|-------|
| **Command** | `k6 run tests/perf/single-item.js --out json=evidence/perf/single-item.json` |
| **What it runs** | 1,000 sequential reads and writes of single items |
| **Pass criteria** | p95 read within target, p95 write within target |

### WF-PERF-04: List and Query Operations

| Field | Value |
|-------|-------|
| **Command** | `k6 run tests/perf/list-query.js --out json=evidence/perf/list-query.json` |
| **What it runs** | Paginated lists and complex queries at Standard envelope data volumes |
| **Pass criteria** | p95 within targets for all query types |

### WF-PERF-05: Report Generation

| Field | Value |
|-------|-------|
| **Command** | `k6 run tests/perf/report-gen.js --out json=evidence/perf/report-gen.json` |
| **What it runs** | Generate reports of varying sizes at Standard envelope |
| **Pass criteria** | p95 within targets. Memory usage stable (no growth trend). |

### WF-PERF-06: File Upload/Download

| Field | Value |
|-------|-------|
| **Command** | `k6 run tests/perf/file-io.js --out json=evidence/perf/file-io.json` |
| **What it runs** | Upload and download files at various sizes (1 KB to 10 MB) |
| **Pass criteria** | p95 within targets for each size bucket |

### WF-PERF-07: Worker Processing

| Field | Value |
|-------|-------|
| **Command** | `k6 run tests/perf/worker-processing.js --out json=evidence/perf/worker.json` |
| **What it runs** | Enqueue jobs at varying rates; measure pickup-to-completion latency |
| **Pass criteria** | p95 pickup latency within target. Job completion rate meets throughput target. |

### WF-PERF-08: Scheduler Trigger Latency

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/perf/test_scheduler_latency.py -v` |
| **What it runs** | Measures time from schedule trigger to job execution start |
| **Pass criteria** | p95 within target |

### WF-PERF-09: Database Throughput

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/perf/test_db_throughput.py -v` |
| **What it runs** | Measures database transaction throughput under concurrent load |
| **Pass criteria** | TPS within target. Connection pool utilization < 80%. |

### WF-PERF-LRG-01: Large Data Volume

| Field | Value |
|-------|-------|
| **Command** | `pytest tests/perf/test_large_volume.py -v` |
| **What it runs** | Database operations on 100 GB dataset |
| **Pass criteria** | Query performance within Large targets. Backup/restore within time limits. |

---

## Regression Detection

### Baseline Comparison

Every performance harness run compares against the previous release's baseline.
Regressions are flagged when:

- p95 latency increases by more than 10%
- Throughput decreases by more than 5%
- Memory usage increases by more than 15%
- Error rate increases by any amount

### Regression Handling

1. Regression detected → harness fails
2. Failure produces a diff report showing before/after metrics
3. Diff report is attached to the ReleaseCertification evidence
4. Regression must be resolved or explicitly accepted (with justification) before release

---

## Measurement Methodology

### How Latency Is Measured

- Client-side measurement (includes network round-trip for API endpoints)
- Server-side measurement (internal timing for worker/scheduler operations)
- Minimum 1,000 samples per measurement point
- Outliers above 3 standard deviations excluded from p95 calculation (but counted in error rate)

### How Throughput Is Measured

- Sustained rate over 5-minute windows
- Must be sustainable, not burst. Peak throughput is recorded but not the target.
- Measured with all components running (web, worker, scheduler), not isolated

### How Resource Usage Is Measured

- CPU: average utilization over measurement window (not peak)
- Memory: RSS (resident set size) at steady state (after warmup)
- Disk: used bytes at start and end of soak test (to detect growth)
- Connections: peak concurrent database connections during test

---

## Honest Limits

What the performance envelope does not cover:

| Not Covered | Why | What To Do |
|------------|-----|-----------|
| Real-world network variability | Environment-dependent | Test with your network conditions |
| Third-party API latency | External dependency | Monitor separately, budget for it |
| Browser rendering performance | Client-dependent | Separate frontend performance testing |
| Multi-region latency | Architecture-dependent | Specific testing for multi-region deployments |
| Exact production numbers | Every deployment differs | Use envelope as baseline, calibrate to your load |

Do not treat these numbers as guarantees for your specific deployment. They are
verified targets for the defined envelope dimensions under controlled conditions.

> Related: [deployment-profiles.md](../operations/deployment-profiles.md) for
> infrastructure sizing, [slo-observability.md](../operations/slo-observability.md)
> for SLO definitions and alerting, [backup-restore-dr.md](../operations/backup-restore-dr.md)
> for RPO/RTO targets (≤ 5m / ≤ 60m), [upgrades-compatibility.md](../operations/upgrades-compatibility.md)
> for support windows (MAJOR 18 months). Performance envelope numbers are verified
> targets for the defined envelope dimensions under controlled conditions, not
> arbitrary guarantees borrowed from cloud provider SLAs.

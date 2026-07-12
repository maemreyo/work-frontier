---
title: "Backup, Restore, and Disaster Recovery"
version: "1.0.0"
status: "canonical"
owner: "work-frontier"
last_updated: "2026-07-12"
requirement_prefix: "WF-OPS"
---

# Backup, Restore, and Disaster Recovery

Backup completion alone is not production proof. A backup that has never been restored
is a hypothesis, not a guarantee. Every backup strategy must be validated by a restore
test, and every restore test must be validated by application-level verification.

---

## Backup Strategy

### PostgreSQL Backups

| Property | Value | Reference |
|----------|-------|-----------|
| Method | Continuous WAL archiving + daily base backups | WF-OPS-BKP-01 |
| RPO (Recovery Point Objective) | ≤ 5 minutes | Maximum data loss window |
| Retention | 30 days | |
| Storage | Separate from database volume (S3 or equivalent) | |
| Encryption | AES-256 at rest | |
| Integrity verification | Weekly restore to test environment | WF-HAR-OPS-06 |

**Backup schedule:**

| Backup Type | Frequency | Retention | Window |
|------------|-----------|-----------|--------|
| WAL segment | Continuous (every 16 MB) | 7 days | Streaming |
| Base backup | Daily 02:00 UTC | 30 days | 2-hour maintenance window |
| Logical dump (schema) | Weekly Sunday 03:00 UTC | 90 days | 1-hour maintenance window |

### Object Storage Backups

| Property | Value | Reference |
|----------|-------|-----------|
| Method | Cross-region replication | WF-OPS-BKP-02 |
| RPO | 24 hours (replication lag) | |
| Retention | 90 days | |
| Versioning | Enabled (keeps last 5 versions) | |

### Configuration Backups

| Property | Value |
|----------|-------|
| Method | Git repository (infrastructure as code) |
| What | Docker Compose files, environment configs, alert rules, dashboard definitions |
| Retention | Permanent (git history) |

---

## Backup Verification

Backup verification is not optional. It runs quarterly as part of the disaster
recovery drill (WF-HAR-OPS-06).

### Verification Steps

| Step | What It Proves | Evidence |
|------|---------------|----------|
| 1. Restore database from backup | Backup is valid and readable | Restore log, timing |
| 2. Restore object storage from backup | Files are intact | File count, checksum comparison |
| 3. Start application against restored data | Application schema is compatible | Health check passes |
| 4. Run smoke tests against restored data | Data integrity at application level | WF-HAR-OPS-01 results |
| 5. Compare data checksums | No corruption during backup or restore | Checksum diff report |
| 6. Verify expired/deleted data stays expired/deleted | Restore must not resurrect expired or deleted data | Authority status check; lifecycle state verification |

**If any step fails, the backup strategy has a gap.** The gap must be identified and
fixed before the next quarterly drill.

### Verification Schedule

| Activity | Frequency | Harness |
|----------|-----------|---------|
| Full restore drill | Quarterly | WF-HAR-OPS-06 |
| Restore timing measurement | Quarterly | WF-HAR-OPS-06 |
| Checksum verification | Weekly (automated) | WF-OPS-BKP-03 |
| Backup completeness check | Daily (automated) | WF-OPS-BKP-04 |

> See [deployment-profiles.md](../operations/deployment-profiles.md) for architecture topology and [slo-observability.md](../operations/slo-observability.md) for alerting thresholds.

---

## Restore Procedures

### Database Restore

| Scenario | Method | Expected Duration | Evidence Required |
|----------|--------|-------------------|-------------------|
| Point-in-time recovery | WAL replay to target time | < 15 min (Standard) | Recovery log with timestamps |
| Full restore from base backup | Restore base + WAL replay | < 60 min (Standard) | Full restore log |
| Restore to different host | Backup to new location | < 60 min (Standard) | Cross-host verification |

**Restore is not "copy the file back."** Restore includes:

1. Restore database files from backup
2. Replay WAL segments to desired point in time
3. Verify database starts and accepts connections
4. Run application-level integrity checks
5. Verify application starts and serves correctly
6. Verify expired/deleted data stays expired/deleted (restore must not resurrect)
7. Measure total time against RTO target

**State model:** Work Frontier stores current state plus append-only evidence records,
not a full event source. Restore recovers current state and evidence chain integrity.
Evidence records are immutable; restore does not replay events to reconstruct state.

### Object Storage Restore

| Scenario | Method | Expected Duration |
|----------|--------|-------------------|
| Single file | Restore from version history | < 5 minutes |
| Full bucket | Cross-region restore | < 2 hours |
| Selective restore | Restore specific prefix | < 1 hour |

---

## Disaster Recovery

### DR Architecture

```
┌─────────────────────┐          ┌─────────────────────┐
│    Primary Region    │          │     DR Region       │
│                      │  async   │                     │
│  ┌─────────────┐    │  repl    │  ┌─────────────┐   │
│  │ PostgreSQL  │──────────────────│ PostgreSQL  │   │
│  │ (writer)    │    │          │  │ (standby)   │   │
│  └─────────────┘    │          │  └─────────────┘   │
│                      │          │                     │
│  ┌─────────────┐    │          │  ┌─────────────┐   │
│  │ Object Store│──────────────────│ Object Store│   │
│  └─────────────┘    │          │  └─────────────┘   │
│                      │          │                     │
│  ┌─────────────┐    │          │  ┌─────────────┐   │
│  │ App Services│    │          │  │ App Services│   │
│  │ (active)    │    │          │  │ (standby)   │   │
│  └─────────────┘    │          │  └─────────────┘   │
└─────────────────────┘          └─────────────────────┘
```

### DR Targets

| Metric | Target | Reference |
|--------|--------|-----------|
| RPO (data loss window) | ≤ 5 minutes | WF-OPS-BKP-03 |
| RTO (time to recovery) | ≤ 60 minutes | WF-OPS-BKP-04 |
| Event durability | ≥ 99.99%, zero acknowledged loss | WF-OPS-SLO-07 |
| DR region | Geographically distant from primary | |
| Replication | Asynchronous (acceptable lag: ≤ 5 minutes) | |

### DR Scenarios

| Scenario | Trigger | Runbook | Expected RTO |
|----------|---------|--------|-------------|
| Primary database failure | Automated failover | WF-OPS-RB-40 | ≤ 30 min |
| Primary region outage | Manual failover | WF-OPS-RB-41 | ≤ 60 min |
| Data corruption | Point-in-time restore | WF-OPS-RB-42 | ≤ 60 min |
| Security breach | Isolate + restore from clean backup | WF-OPS-RB-42 | ≤ 60 min |

### DR Failover Procedure

| Step | Action | Owner | Time |
|------|--------|-------|------|
| 1 | Declare incident | On-call engineer | T+0 |
| 2 | Assess: is primary recoverable? | On-call engineer | T+10 min |
| 3 | If not recoverable, initiate DR failover | Engineering lead | T+15 min |
| 4 | Promote DR database to primary | DBA | T+25 min |
| 5 | Update DNS to point to DR region | Platform team | T+35 min |
| 6 | Verify application health in DR | On-call engineer | T+45 min |
| 7 | Verify data integrity and event durability | QA | T+55 min |
| 8 | Resume normal operations | Engineering lead | T+60 min |
| 9 | Post-incident review | Team | T+48h |

---

## Rollback

Rollback is not restore. Rollback is returning the application to a previous version.
Restore is returning data to a previous state. Both may be needed.

> See [upgrades-compatibility.md §Rollback Decision Criteria](../operations/upgrades-compatibility.md#rollback-decision-criteria)
> for the full decision tree and [upgrade evidence requirements](../operations/upgrades-compatibility.md#upgrade-evidence-requirements).

### Application Rollback

| Scenario | Method | Evidence Required |
|----------|--------|-------------------|
| Bad deployment | Revert to previous container image tag | Deployment log |
| Bad migration | Rollback migration + redeploy previous version | Migration log, data verification |
| Bad configuration | Revert config change + restart | Config diff, restart log |

### Data Rollback

| Scenario | Method | Evidence Required |
|----------|--------|-------------------|
| Bad data write | Point-in-time restore to before the write | Restore log, data verification |
| Bulk data corruption | Full restore from pre-corruption backup | Full restore log |
| Schema migration data loss | Restore from pre-migration backup | Restore log, schema verification |

### Rollback Decision Tree

```
Is the issue code or data?
├── Code issue
│   ├── Can you hotfix? → Deploy hotfix
│   └── Cannot hotfix? → Roll back to previous deployment
└── Data issue
    ├── Can you surgically fix? → Fix affected records
    └── Cannot fix surgically?
        ├── Is the bad write < 5 min old? → Point-in-time restore (RPO ≤ 5m)
        └── Is the bad write > 5 min old? → Restore from most recent backup
```

---

## What Backup/Restore Is Not

| Misconception | Reality |
|--------------|---------|
| "We have backups" | Backups that haven't been restored are hypotheses |
| "Backup completed successfully" | Completion means the file was written, not that it can be restored |
| "We have DR" | DR that hasn't been drilled is documentation, not capability |
| "Restore is fast" | Restore speed depends on data size and infrastructure; measure it against ≤ 60m RTO |
| "DR failover is automatic" | Warm DR requires manual failover. Automated failover is active-active, which this is not. |
| "Events survive crashes" | Only acknowledged events are durably persisted (≥ 99.99%); unacknowledged events may be lost |
| "Point-in-time recovery is instant" | WAL replay takes time; RPO ≤ 5 minutes means up to 5 minutes of writes may be lost |

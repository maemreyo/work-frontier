---
title: "Incident Response and Runbook Index"
version: "1.0.0"
status: "canonical"
owner: "work-frontier"
last_updated: "2026-07-12"
requirement_prefix: "WF-OPS"
---

# Incident Response and Runbook Index

Incidents are not problems to solve in the moment. They are situations to navigate
using pre-defined procedures. The goal is not to be clever during an incident. The
goal is to follow the runbook, contain the damage, restore service, and learn.

---

## Incident Severity

| Severity | Definition | Response Time | Escalation |
|----------|-----------|---------------|------------|
| SEV1 | Service fully down, data loss, security breach | Immediate | All hands, executive notification |
| SEV2 | Major feature unavailable, significant performance degradation | 15 minutes | On-call + engineering lead |
| SEV3 | Minor feature unavailable, minor performance issue | 1 hour | On-call |
| SEV4 | Cosmetic issue, non-urgent | Next business day | Ticket queue |

---

## Incident Response Phases

### Phase 1: Detection (T+0)

| Action | Owner | Evidence |
|--------|-------|----------|
| Alert fires or user reports issue | Monitoring / User | Alert timestamp, report channel |
| Acknowledge alert | On-call engineer | Acknowledgment timestamp |
| Assess severity | On-call engineer | Severity classification |

### Phase 2: Triage (T+5 min)

| Action | Owner | Evidence |
|--------|-------|----------|
| Identify affected components | On-call engineer | Component list |
| Check runbook for matching scenario | On-call engineer | Runbook ID |
| Determine if user data is at risk | On-call engineer | Risk assessment |
| If SEV1, page additional responders | On-call engineer | Page log |

### Phase 3: Containment (T+15 min)

| Action | Owner | Evidence |
|--------|-------|----------|
| Follow runbook containment steps | On-call engineer | Runbook execution log |
| Isolate affected component if needed | On-call engineer | Isolation action log |
| Preserve evidence (logs, metrics, state) | On-call engineer | Evidence archive |
| Capture domain-aware telemetry (item IDs, program IDs, gate states) | On-call engineer | Telemetry snapshot (PII redacted) |
| Communicate status to stakeholders | Engineering lead | Status update |

### Phase 4: Resolution (T+varies)

| Action | Owner | Evidence |
|--------|-------|----------|
| Execute fix (runbook or ad hoc) | On-call engineer | Fix action log |
| Verify service restored | On-call engineer | Health check results |
| Verify no data loss or corruption | DBA / On-call | Data verification log |
| Remove containment measures | On-call engineer | Action log |
| Confirm all-clear to stakeholders | Engineering lead | Status update |

### Phase 5: Post-Incident (T+24-48h)

| Action | Owner | Evidence |
|--------|-------|----------|
| Write incident report | Incident commander | Report document |
| Conduct blameless post-mortem | Team | Post-mortem notes |
| Identify root cause | Team | Root cause analysis |
| Create follow-up action items | Engineering lead | Action item tickets |
| Update runbooks if needed | On-call engineer | Updated runbook |

---

## Runbook Index

> Cross-references: [deployment-profiles.md](../operations/deployment-profiles.md) for
> architecture topology, [slo-observability.md](../operations/slo-observability.md) for
> alerting thresholds, [backup-restore-dr.md](../operations/backup-restore-dr.md) for
> restore procedures, [upgrades-compatibility.md](../operations/upgrades-compatibility.md)
> for rollback decision criteria.

### Infrastructure Runbooks

| Runbook ID | Scenario | Trigger |
|-----------|----------|---------|
| WF-OPS-RB-01 | PostgreSQL connection pool exhaustion | Alert: DatabaseConnectionPoolExhausted |
| WF-OPS-RB-02 | PostgreSQL replication lag | Alert: DatabaseReplicationLag |
| WF-OPS-RB-03 | Disk space critical | Alert: DiskSpaceCritical |
| WF-OPS-RB-04 | Object storage unavailable | Alert: ObjectStorageUnreachable |
| WF-OPS-RB-05 | DNS resolution failure | Alert: DNSResolutionFailed |

### Application Runbooks

| Runbook ID | Scenario | Trigger | Cross-Reference |
|-----------|----------|---------|-----------------|
| WF-OPS-RB-10 | Web API process crash | Alert: ServiceDown (web) | [deployment-profiles.md](../operations/deployment-profiles.md) |
| WF-OPS-RB-11 | Worker process crash | Alert: ServiceDown (worker) | [deployment-profiles.md](../operations/deployment-profiles.md) |
| WF-OPS-RB-12 | Scheduler process crash | Alert: ServiceDown (scheduler) | [deployment-profiles.md](../operations/deployment-profiles.md) |
| WF-OPS-RB-13 | Worker job queue stuck | Alert: QueueBacklogGrowing | [slo-observability.md](../operations/slo-observability.md) |
| WF-OPS-RB-14 | API latency spike | Alert: LatencySLOBreach | [slo-observability.md](../operations/slo-observability.md) |
| WF-OPS-RB-15 | High error rate | Alert: HighErrorRate | [slo-observability.md](../operations/slo-observability.md) |

### Data Runbooks

| Runbook ID | Scenario | Trigger | Cross-Reference |
|-----------|----------|---------|-----------------|
| WF-OPS-RB-20 | Database corruption detected | Alert: DataIntegrityCheckFailed | [backup-restore-dr.md](../operations/backup-restore-dr.md) |
| WF-OPS-RB-21 | Accidental data deletion | User report | [backup-restore-dr.md §Rollback](../operations/backup-restore-dr.md#rollback) |
| WF-OPS-RB-22 | Migration failure | Alert: MigrationFailed | [upgrades-compatibility.md §Migration Rollback](../operations/upgrades-compatibility.md#migration-rollback) |
| WF-OPS-RB-23 | Backup failure | Alert: BackupFailed | [backup-restore-dr.md §Backup Strategy](../operations/backup-restore-dr.md#backup-strategy) |

### Security Runbooks

| Runbook ID | Scenario | Trigger | Cross-Reference |
|-----------|----------|---------|-----------------|
| WF-OPS-RB-30 | Authentication bypass attempt | Alert: SecurityEventDetected | [verification-strategy.md §Security](../quality/verification-strategy.md#security-harness-wf-har-security) |
| WF-OPS-RB-31 | Suspicious API activity | Alert: SuspiciousActivity | [slo-observability.md](../operations/slo-observability.md) |
| WF-OPS-RB-32 | Dependency vulnerability | Alert: CriticalCVE | [upgrades-compatibility.md §Upgrade Schedule](../operations/upgrades-compatibility.md#upgrade-schedule) |
| WF-OPS-RB-33 | Secret exposure | Alert: SecretDetectedInLogs | [verification-strategy.md §Static](../quality/verification-strategy.md#layer-1-static-wf-har-static) |

### DR Runbooks

| Runbook ID | Scenario | Trigger | Cross-Reference |
|-----------|----------|---------|-----------------|
| WF-OPS-RB-40 | Primary database failure (failover) | Alert: PrimaryDBDown | [backup-restore-dr.md §DR Failover](../operations/backup-restore-dr.md#disaster-recovery) |
| WF-OPS-RB-41 | Primary region outage (DR failover) | Manual declaration | [backup-restore-dr.md §DR Failover](../operations/backup-restore-dr.md#disaster-recovery) |
| WF-OPS-RB-42 | Data restoration from backup | Alert: DataLossDetected | [backup-restore-dr.md §Restore](../operations/backup-restore-dr.md#restore-procedures) |

---

## Runbook Template

Every runbook follows this structure:

```markdown
# WF-OPS-RB-XX: [Scenario Name]

## Trigger
What alert or event triggers this runbook.

## Severity
Expected severity level.

## Impact
What users experience during this incident.

## Diagnosis
Steps to confirm this is the correct scenario.

## Containment
Steps to stop the damage.

## Resolution
Steps to restore service.

## Verification
Steps to confirm the fix worked.

## Escalation
When and how to escalate.

## Prevention
What to do after the incident to prevent recurrence.

## Evidence
What to capture during the runbook execution.
```

---

## On-Call Rotation

| Property | Value |
|----------|-------|
| Rotation schedule | Weekly |
| Primary on-call | 1 engineer |
| Secondary on-call | 1 engineer (backup) |
| Escalation path | Primary → Secondary → Engineering lead → CTO |
| Handoff | Weekly, with written status of open issues |

### On-Call Responsibilities

1. Respond to alerts within defined response times
2. Follow runbooks for known scenarios
3. Escalate when runbook is insufficient
4. Communicate status to stakeholders
5. Document all actions taken

---

## Communication Templates

### Initial Status (T+15 min)

```
[SEV{X}] {Brief description}
Status: Investigating
Impact: {What users experience}
Next update: {Time}
```

### Update (every 30 min for SEV1/SEV2)

```
[SEV{X}] {Brief description}
Status: {Investigating / Identified / Fixing / Monitoring}
Impact: {Current impact}
Actions taken: {What we've done}
Next update: {Time}
```

### All-Clear

```
[SEV{X}] {Brief description}
Status: Resolved
Duration: {Total incident duration}
Root cause: {Brief root cause}
Follow-up: {Link to post-mortem}
```

---

## Incident Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Mean time to acknowledge (MTTA) | < 5 minutes (SEV1/SEV2) | WF-OPS-INC-01 |
| Mean time to contain (MTTC) | < 30 minutes (SEV1) | WF-OPS-INC-02 |
| Mean time to resolve (MTTR) | < 2 hours (SEV1) | WF-OPS-INC-03 |
| Incidents per month | Trending downward | WF-OPS-INC-04 |
| Runbook coverage | > 90% of incidents have runbooks | WF-OPS-INC-05 |

---

## Post-Mortem Process

| Step | Deadline | Owner |
|------|----------|-------|
| Draft incident report | 24 hours after resolution | Incident commander |
| Conduct post-mortem meeting | 48 hours after resolution | Team |
| Publish final post-mortem | 5 business days after resolution | Engineering lead |
| Create action items | During post-mortem meeting | Team |
| Complete action items | 30 days after post-mortem | Assigned owners |

### Post-Mortem Principles

1. **Blameless.** Focus on systems and processes, not individuals.
2. **Evidence-based.** Every claim in the post-mortem is backed by data.
3. **Actionable.** Every root cause has a corresponding action item.
4. **Timely.** Post-mortems happen while memory is fresh.

---

## Runbook Maintenance

| Activity | Frequency | Owner |
|----------|-----------|-------|
| Review all runbooks | Quarterly | On-call rotation |
| Update runbooks after incidents | After every incident | Incident commander |
| Add new runbooks for new failure modes | As identified | Engineering team |
| Test runbooks (dry run) | Quarterly | On-call rotation |
| Remove obsolete runbooks | When component removed | Engineering team |

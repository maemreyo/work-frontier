---
title: "Upgrades and Compatibility"
version: "1.0.0"
status: "canonical"
owner: "work-frontier"
last_updated: "2026-07-12"
requirement_prefix: "WF-OPS"
---

# Upgrades and Compatibility

Upgrades are not events. They are processes with defined steps, rollback paths, and
verification gates. Every upgrade must be rehearsed in staging before production.

---

## Versioning

### SemVer

Work Frontier follows Semantic Versioning 2.0.0.

```
MAJOR.MINOR.PATCH

MAJOR: Breaking changes to API, data model, or behavior
MINOR: New features, backward-compatible
PATCH: Bug fixes, backward-compatible
```

### What Each Bump Means

| Bump | API Impact | Data Impact | Migration Required | Support Window |
|------|-----------|-------------|-------------------|---------------|
| MAJOR | Breaking changes | Breaking schema changes | Yes, mandatory | 18 months from next MAJOR |
| MINOR | New endpoints, optional fields | Additive schema changes | Optional (new features) | 9 months from next MAJOR |
| PATCH | Bug fixes only | No schema changes | No | Until next MINOR or MAJOR |

---

## Support Windows

| Version Line | Support Duration | End-of-Life Policy |
|-------------|-----------------|-------------------|
| Current MAJOR | 18 months from next MAJOR release | Active development and fixes |
| Previous MAJOR | 9 months from current MAJOR release | Security fixes only |
| Older than previous MAJOR | No support | No fixes, no security patches |

### Support Window Example

```
v1.x.x released Jan 2026
  ├── v2.0.0 released Jul 2026
  │     └── v1.x.x supported until Jan 2027 (security fixes only) [18 months from v2.0.0]
  └── v3.0.0 released Jan 2027
        └── v2.x.x supported until Jul 2027 (security fixes only) [9 months from v3.0.0]
        └── v1.x.x support ended (no fixes)
```

### What "Security Fixes Only" Means

- Critical and high CVE fixes backported to the previous MAJOR
- No feature backports
- No bug fixes for non-security issues
- No new database migrations (schema frozen)
- Upgrade to current MAJOR is recommended

> See [deployment-profiles.md](../operations/deployment-profiles.md) for hosted vs. self-hosted upgrade responsibilities and [backup-restore-dr.md](../operations/backup-restore-dr.md) for rollback procedures.

---

## Upgrade Process

### Pre-Upgrade

| Step | Action | Owner |
|------|--------|-------|
| 1 | Review changelog for breaking changes | Engineering lead |
| 2 | Check migration requirements | DBA |
| 3 | Run upgrade against staging environment | Engineering lead |
| 4 | Verify staging passes all harnesses | CI system |
| 5 | Review backup status (backup completed within last hour) | DBA |
| 6 | Communicate maintenance window to stakeholders | Engineering lead |

### Upgrade Execution

| Step | Action | Evidence Required |
|------|--------|-------------------|
| 1 | Create database backup | Backup confirmation with timestamp |
| 2 | Put system in maintenance mode (optional, for MAJOR) | Maintenance mode log |
| 3 | Run database migrations | Migration log with timing |
| 4 | Deploy new application version | Deployment log with image tag |
| 5 | Verify application health | Health check results |
| 6 | Run smoke tests | WF-HAR-OPS-01 results |
| 7 | Exit maintenance mode | Maintenance mode log |
| 8 | Monitor for 30 minutes | Dashboard screenshots, error rate |

### Post-Upgrade

| Step | Action | Evidence Required |
|------|--------|-------------------|
| 1 | Verify all harnesses pass in production | Harness results |
| 2 | Verify SLO metrics stable | Dashboard comparison (before/after) |
| 3 | Verify no new errors in logs | Log search results |
| 4 | Run 72h soak test (mandatory per release; 4h quick-soak per deployment) | Soak test results from WF-HAR-OPS-04 |
| 5 | Update release notes | Changelog entry |
| 6 | Close upgrade ticket | Ticket with all evidence linked |

---

## Database Migrations

Migrations are the highest-risk part of any upgrade. Every migration must be:
tested on production-size data, reversible (or have a documented escape plan),
and timed within the maintenance window.

### Migration Rules

| Rule | Why |
|------|-----|
| Every migration must have a rollback path | Failed migrations must be recoverable |
| Migrations must be tested on Standard envelope data | Timing matters at scale |
| No migration during peak hours | Reduces blast radius |
| Migration log captures timing | Proves the migration completed within the window |
| Schema changes must be backward-compatible (MINOR) | Rolling deploys need both old and new code to work |

### Migration Execution

```
1. Pre-migration backup (WF-OPS-BKP-05)
2. Run migration forward
   ├── Record start time
   ├── Record each step timing
   ├── Record end time
   └── Record row counts (before/after)
3. Verify schema matches expected state
4. Run application smoke tests against new schema
5. If any step fails:
   ├── Rollback migration
   ├── Verify rollback schema
   ├── Resume normal operations
   └── File incident ticket
```

### Migration Compatibility Matrix

| Change Type | MINOR Safe? | Requires MAJOR? | Backward-Compatible? |
|------------|-------------|-----------------|---------------------|
| Add column (nullable) | Yes | No | Yes |
| Add column (NOT NULL with default) | Yes | No | Yes |
| Remove column | No | Yes | No |
| Rename column | No | Yes | No |
| Add table | Yes | No | Yes |
| Remove table | No | Yes | No |
| Change column type | No | Yes | No |
| Add index (non-blocking) | Yes | No | Yes |
| Add index (blocking) | No | Yes | Depends on size |

---

## Rolling Upgrades

For hosted deployments, rolling upgrades allow zero-downtime MINOR and PATCH upgrades.

### Rolling Upgrade Process

```
1. Deploy new version to one replica
2. Wait for health check to pass
3. Verify no errors in new replica logs
4. Deploy to next replica
5. Repeat until all replicas updated
6. Deploy to scheduler (leader election handles transition)
7. Monitor full fleet for 30 minutes
```

### Rolling Upgrade Constraints

| Constraint | Why |
|-----------|-----|
| Database migration must run before app deploy | New code may depend on new schema |
| No breaking API changes in MINOR/PATCH | Old and new replicas serve simultaneously |
| Database must be backward-compatible with both versions | During rolling deploy, both versions query the DB |

---

## Compatibility Guarantees

### API Compatibility

| Version Change | Guarantee |
|---------------|-----------|
| MINOR | All existing endpoints continue to work. New endpoints added. No field removals. |
| PATCH | No API changes except bug fixes. |
| MAJOR | Breaking changes possible. Migration guide provided. |

### Data Compatibility

| Version Change | Guarantee |
|---------------|-----------|
| MINOR | New columns are nullable or have defaults. Existing data untouched. |
| PATCH | No data schema changes. |
| MAJOR | Schema changes possible. Migration script provided. |

### Client Compatibility

| Scenario | Guarantee |
|----------|-----------|
| Old client, new server (MINOR) | Works. New features unavailable. |
| New client, old server (MINOR) | Works if client doesn't use new features. |
| Old client, new server (MAJOR) | May not work. Upgrade client required. |

---

## Upgrade Rollback

### Application Rollback

If the new version has issues after deployment:

```
1. Stop deploying (if rolling upgrade in progress)
2. Redeploy previous version across all replicas
   ├── For container deployments: change image tag back
   ├── For Kubernetes: rollback deployment
   └── For Compose: re-deploy with previous image
3. Verify health check
4. Run smoke tests
5. Monitor for stability
```

### Migration Rollback

If a database migration fails:

```
1. Stop the migration if still running
2. Run the rollback migration (if available)
3. If no rollback migration:
   ├── Restore from pre-migration backup
   ├── Verify schema integrity
   └── Redeploy previous application version
4. Verify application health
5. File incident ticket with full migration log
```

### Rollback Decision Criteria

| Condition | Action |
|-----------|--------|
| Migration fails | Rollback migration, investigate |
| New version crashes | Redeploy previous version |
| New version has data corruption | Restore from backup + redeploy previous version |
| New version has performance regression | Redeploy previous version, investigate |
| New version has security vulnerability | Deploy hotfix, not rollback (vulnerability exists in both) |

---

## Upgrade Schedule

| Activity | Frequency | Owner |
|----------|-----------|-------|
| PATCH releases | As needed (bug fixes) | Engineering lead |
| MINOR releases | Monthly | Engineering lead |
| MAJOR releases | Annually (or as needed) | Engineering lead |
| Dependency updates | Monthly | Automated (Dependabot/Renovate) |
| Security patches | As needed (within 72h for critical) | Security team |

---

## Upgrade Evidence Requirements

Every upgrade to production must produce:

1. **Staging test results** showing the upgrade succeeded in staging
2. **Database backup confirmation** taken before the upgrade
3. **Migration log** with timing and row counts
4. **Deployment log** with image tags and timestamps
5. **Post-upgrade smoke test results**
6. **30-minute monitoring comparison** (before vs. after)

Evidence is retained for the duration of the version's support window.

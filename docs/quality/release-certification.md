---
title: "Release Certification"
version: "1.0.0"
status: "canonical"
owner: "work-frontier"
last_updated: "2026-07-12"
requirement_prefix: "WF-HAR"
---

# Release Certification

A release is not declared by word, version bump, or changelog. A release is certified
when a ReleaseCertification artifact exists, is signed, and references the exact commit
it was built from. Hosted and self-hosted deployments use the same certification artifact.

---

## Contract

A `ReleaseCertification` is a signed, structured document binding a git commit to
evidence that all required harnesses passed.

```python
from datetime import datetime
from typing import Literal

class HarnessEvidence:
    harness_id: str                # e.g. "WF-HAR-INTEG-01"
    status: Literal["pass", "fail", "skip"]
    evidence_path: str             # path to structured results file
    commit_sha: str                # exact commit this harness ran against
    service_versions: dict[str, str]  # every dependency and its version
    duration_seconds: float
    runner_metadata: dict          # OS, runtime version, resource info
    timestamp: datetime

class ReleaseCertification:
    version: str                   # SemVer, e.g. "1.2.0"
    commit_sha: str                # exact commit, full 40-char SHA
    commit_message: str            # first line of commit message
    branch: str                    # branch the release was built from
    harnesses: list[HarnessEvidence]  # one entry per required harness
    all_passed: bool               # computed: all statuses are "pass"
    total_duration_seconds: float  # sum of all harness durations
    generated_at: datetime
    generated_by: str              # CI system identity
    signature: str                 # Ed25519 signature over the serialized cert
    signature_key_id: str          # which key signed this cert
```

### Invariants

1. **commit_sha is the truth.** The certification applies to exactly one commit. No
   floating references like `latest` or `main`. The SHA is pinned at build time.

2. **Every required harness has an entry.** If a harness is in the required set and
   is not listed, `all_passed` must be `False`. Omission is not the same as passing.

3. **No skip without justification.** A harness status of `skip` requires a
   `skip_reason` field and is only permitted for harnesses not marked "Blocks release"
   in the harness catalog. Skipped harnesses that block release make `all_passed` False.

4. **Signature covers everything.** The signature is computed over the serialized
   certification excluding the signature field itself. Tampering with any field invalidates
   the signature.

5. **Service versions are real.** The `service_versions` dict must come from the actual
   build environment, not a configuration file. Versions are recorded at harness execution
   time.

---

## Signing

### Key Management

| Field | Value |
|-------|-------|
| Algorithm | Ed25519 |
| Key storage | CI secret store (GitHub Actions secrets, or equivalent) |
| Key rotation | Every 90 days, or immediately on suspected compromise |
| Key revocation | Publish revoked key ID to project README; old signatures marked invalid |

### Signing Process

1. CI system generates the `ReleaseCertification` after all harnesses complete.
2. CI system serializes the certification to canonical JSON (sorted keys, no whitespace).
3. CI system signs the serialized JSON with the Ed25519 private key.
4. CI system stores the signature in the certification and publishes the signed artifact.
5. The public key is available for verification at `https://<project>/keys/release-signing.pub`.

### Verification

```bash
# Verify a release certification
python scripts/verify-release-cert.py \
  --cert evidence/release-certification.json \
  --key https://<project>/keys/release-signing.pub
```

Verification checks:
- Signature is valid for the serialized certification body
- Every required harness is present with status "pass"
- Commit SHA exists in the repository history
- Service versions are plausible (no placeholder values)
- Timestamp is within the CI build window

---

## Evidence Chain

Every certification references a chain of evidence that must be independently verifiable.

```
ReleaseCertification
  ├── commit_sha: <full 40-char SHA>
  ├── commit_message: <first line>
  │
  ├── evidence/static/
  │     ├── type-check.json
  │     ├── import-boundaries.json
  │     ├── lint.json
  │     └── secrets.json
  │
  ├── evidence/domain/
  │     ├── frontier-computation.json
  │     ├── precedence.json
  │     ├── dependency-chains.json
  │     ├── policy-gates.json
  │     └── source-authority.json
  │
  ├── evidence/property/
  │     ├── frontier-determinism.json
  │     ├── dependency-acyclicity.json
  │     ├── readiness-monotonicity.json
  │     ├── projection-convergence.json
  │     └── input-ordering.json
  │
  ├── evidence/metamorphic/
  │     ├── frontier-replay.json
  │     ├── frontier-monotonicity.json
  │     ├── readiness-monotonicity.json
  │     ├── projection-parity.json
  │     └── invalid-component-isolation.json
  │
  ├── evidence/contract/
  │     ├── api-schema.json
  │     ├── migration.json          ← migration evidence (forward timing, rollback verification)
  │     ├── event-schema.json
  │     ├── inter-service.json
  │     └── cross-language.json
  │
  ├── evidence/integration/
  │     ├── postgres.json
  │     ├── object-storage.json
  │     ├── durable-queue.json
  │     ├── web-server.json
  │     ├── worker.json
  │     └── scheduler.json
  │
  ├── evidence/product/
  │     ├── onboarding-recommendation/  ← first Recommended Next with rationale
  │     ├── why-blocked/               ← dependency chain root cause resolution
  │     ├── atomic-claim-race.json     ← concurrent claim consistency
  │     ├── dependency-repair/          ← proposed repair approval
  │     ├── stale-decision.json         ← stale authority rejection
  │     └── projection-update.json      ← mutation triggers recomputation
  │
  ├── evidence/ops/
  │     ├── smoke.json
  │     ├── load-test.json          ← performance evidence (all p95 targets)
  │     ├── event-durability.json   ← ≥ 99.99% durability, zero acknowledged loss
  │     ├── soak-test.json          ← 72h soak per release, 4h quick-soak per deployment
  │     ├── failure-injection.json  ← no acknowledged event loss under failure
  │     ├── dr-drill.json           ← restore evidence (RTO ≤ 60m, RPO ≤ 5m)
  │     └── migration-live-size.json
  │
  ├── evidence/crosscut/
  │     ├── github-sandbox.json     ← adapter evidence (real GitHub sandbox)
  │     └── 539-replay.json         ← replay hash (SHA-256 of golden-file snapshots)
  │
  ├── evidence/security/
  │     ├── auth-bypass.json
  │     ├── zap-baseline.json
  │     ├── ssrf.json
  │     ├── idor.json
  │     ├── csrf.json
  │     ├── rate-limiting.json
  │     ├── dependency-audit.json
  │     ├── tls.json
  │     ├── permission-escalation.json
  │     ├── safety-gate-bypass.json
  │     ├── override-bypass.json
  │     ├── authority-manipulation.json
  │     ├── credential-exposure.json
  │     ├── evidence-tampering.json
  │     └── audit-integrity.json
  │
  ├── evidence/accessibility/
  │     ├── wcag-aa.json
  │     ├── keyboard-nav.json
  │     ├── focus-appearance.json
  │     └── drag-alternatives.json
  │
  ├── evidence/sbom/
  │     └── provenance.spdx.json    ← SBOM/provenance (generated from lockfiles)
  │
  └── evidence/rollback/
        └── rollback-manifest.json  ← previous version image tag + rollback command
```

### Evidence Artifact Requirements

Every evidence file must contain:

1. **harness_id**: Matches the certification entry
2. **commit_sha**: Same commit as the certification
3. **results**: Structured test results (pass/fail per test case)
4. **timestamps**: Start and end of harness execution
5. **environment**: Service versions, OS, runtime version
6. **artifacts**: Paths to any generated files (screenshots, traces, logs)
7. **content_hash**: SHA-256 of the evidence file itself (for tamper detection)

Evidence files are stored alongside the build artifacts and must be retained for the
duration of the release's support window plus 90 days.

---

## Release Process

### Pre-Certification Checklist

Before the CI pipeline begins:

1. [ ] All code changes merged to the release branch
2. [ ] Version bump committed (SemVer)
3. [ ] Changelog updated
4. [ ] No pending security advisories for this commit
5. [ ] Dependencies audited (WF-HAR-SEC-03)

### Pipeline Execution

```
1. Checkout commit (pinned SHA)
2. Install dependencies (pinned lockfiles)
3. Generate SBOM/provenance from lockfiles
4. Run Layer 1: Static harnesses (WF-HAR-STATIC-*)
5. Run Layer 2: Domain harnesses (WF-HAR-DOMAIN-*)
6. Run Layer 3: Property harnesses (WF-HAR-PROPERTY-*)
7. Run Layer 4: Metamorphic harnesses (WF-HAR-META-*)
8. Run Layer 5: Contract harnesses (WF-HAR-CONTRACT-*)
   ├── If commit includes schema changes: run migration evidence
   └── If commit changes adapters: run adapter integration tests against real sandbox
9. Run Layer 6: Integration harnesses (WF-HAR-INTEG-*)
   ├── Start Docker Compose stack
   ├── Wait for all services healthy
   ├── Run harnesses
   └── Capture logs and metrics
10. Run Layer 7: Product-path harnesses (WF-HAR-PRODUCT-*)
    ├── Deploy to test environment
    ├── Run Control Room read latency (< 500ms p95)
    ├── Run Program overview latency (< 1s p95)
    ├── Run Webhook-to-decision latency (< 30s p95)
    ├── Run Manual revalidation (< 60s Standard)
    ├── Run Full solve (< 5s Standard, < 30s Large)
    ├── Run Incremental projection (< 2s)
    └── Capture screenshots and traces
11. Run Layer 8: Operational harnesses (WF-HAR-OPS-*)
    ├── Smoke test
    ├── Load test (all p95 latency targets)
    ├── Event durability test (≥ 99.99%, zero acknowledged loss)
    ├── (Every release) 72h soak test; (every deployment) 4h quick-soak
    ├── Failure injection, DR drill (RTO ≤ 60m)
    └── (Per migration) Live-size migration test
12. Run Cross-Cutting harnesses
    ├── WF-HAR-GITHUB-SANDBOX-* (adapter evidence)
    ├── WF-HAR-539-REPLAY-* (replay hashes)
    ├── WF-HAR-SEC-* (security evidence)
    └── WF-HAR-A11Y-* (accessibility evidence)
13. Collect all evidence files
14. Verify all content hashes
15. Record rollback manifest (previous version image tag + rollback command)
16. Generate ReleaseCertification
17. Sign ReleaseCertification
18. Publish certification + evidence bundle
```

### Post-Certification

1. Tag the commit with the version: `v{version}`
2. Create GitHub release with certification summary
3. Attach evidence bundle as release asset
4. Notify stakeholders with certification link

---

## Certification Status

| Status | Meaning |
|--------|---------|
| **certified** | All required harnesses passed. Certification signed. |
| **partial** | Some harnesses passed, others skipped (only non-blocking). |
| **uncertified** | Required harness failed or was skipped. Release blocked. |
| **revoked** | Certification was valid but is now invalid (security issue, critical bug). |

A release can only be deployed if its certification status is `certified`.

---

## Revocation

A certification is revoked when:

1. A critical vulnerability is discovered post-release
2. A harness is found to have been incorrectly passing (bad assertion, wrong fixture)
3. Service version evidence is found to be fabricated
4. The signing key is compromised

Revocation process:

1. Set certification status to `revoked`
2. Add revocation reason and timestamp
3. Re-sign the revoked certification (so the revocation itself is authenticated)
4. Publish to the same location as the original certification
5. Notify all downstream consumers

A revoked certification cannot be un-revoked. A new certification must be issued
against a new commit.

---

## What ReleaseCertification Is Not

| Misconception | Reality |
|--------------|---------|
| "All tests pass" | Coverage proves execution, not correctness. Certification requires explicit harnesses. |
| "CI is green" | CI green means the pipeline completed. Certification means every required evidence artifact exists and is signed. |
| "We tagged it" | A tag is a pointer. A certification is a signed claim backed by evidence. |
| "We deployed it" | Deployment is an action. Certification is the proof that the action was justified. |
| "The diagram shows it works" | Diagrams describe intent. Certification proves behavior. |
| "Coverage is 95%" | Coverage is a metric. Certification is a contract. |

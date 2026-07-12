---
id: WF-REF-001
title: "Verified Facts Reference: oh-my-class Super Epic #539 Fixture"
status: accepted
owner: Work Frontier reference maintainers
date: 2026-07-12
scope: oh-my-class issue hierarchy (reference fixture for Work Frontier)
classification: reference
supersedes: null
---

# WF-REF-001: Verified Facts Reference

## Purpose

Single source of truth for **observed** facts about oh-my-class Super Epic #539. This hierarchy is Work Frontier's canonical reference fixture — the data the projection engine processes, validates against, and cutover targets. Every downstream document references this file. No design opinions or implementation plans belong here.

---

## 1. Issue Identity (observed 2026-07-12)

| Property | Observed value | Source |
|----------|---------------|--------|
| Issue number | #539 | GitHub |
| No native subissues | `GET /repos/{owner}/{repo}/issues/539/subissues` returns empty set | GitHub API (observed) |
| No native dependency edges | No GitHub dependency API entries for #539 | GitHub API (observed) |
| No GitHub Projects assignment | #539 is not in any GitHub Project board | GitHub UI (observed) |
| Role | Generated report summarizing five Epic branches | Issue body content (observed) |

---

## 2. Issue Markers (observed)

Issues in this fixture carry HTML comment markers in their body text:

```
<!-- omc-program:{program}; issue:{key} -->
```

**Observation:** Membership is grouped by program marker. The marker identifies which program an issue belongs to.

---

## 3. Child Relationship Prose (observed)

Issues contain a `## Parent` section in their body text using prose (natural-language description of the parent relationship).

**Observation:** The current Work Frontier generator does **not** parse the `## Parent` prose. The generator extracts dependency information from `## Blocked by` sections instead.

---

## 4. Dependency References (observed)

Dependencies between issues are expressed as Markdown body text in `## Blocked by` sections:

```
## Blocked by
#538
```

These are **not** GitHub dependency API edges. They are prose references in issue bodies.

---

## 5. Epics and Terminals (observed 2026-07-12)

| Issue | Observed role | Terminal source |
|-------|--------------|----------------|
| #539 | Generated report summarizing five Epic branches | — |
| #460 | Epic (E1) | — |
| #475 | Epic (E2) | — |
| #488 | Epic (E3) | — |
| #504 | Epic (E4) | — |
| #522 | Epic (E5) | — |
| #474 | Terminal of E1 | PROGRAM_GATES policy |
| #487 | Terminal of E2 | PROGRAM_GATES policy |
| #503 | Terminal of E3 | PROGRAM_GATES policy |
| #521 | Terminal of E4 | PROGRAM_GATES policy |
| #538 | Terminal of E5 | PROGRAM_GATES policy |

**Note:** Terminal status is determined by `PROGRAM_GATES` policy (ProgramSpec), not by position in the `## Blocked by` body-text graph alone.

---

## 6. Effective Edges (observed 2026-07-12)

Edges in the effective dependency graph, with provenance:

| Edge | Provenance | Source evidence |
|------|-----------|----------------|
| #538 blocks #503 | **Policy** (PROGRAM_GATES) | Not present in #503 body `## Blocked by`; added by program policy |
| #487 blocks #474 | **Policy** (PROGRAM_GATES) | Not present in #474 body `## Blocked by`; added by program policy |
| #503 blocks #474 | **Policy** (PROGRAM_GATES) | Not present in #474 body `## Blocked by`; added by program policy |
| #521 blocks #474 | **Policy** (PROGRAM_GATES) | Not present in #474 body `## Blocked by`; added by program policy |

**Important:** `PROGRAM_GATES` policy adds these edges to targets even when the target issue bodies do **not** list them in `## Blocked by`. The effective edge set is the union of textual body-text references and policy-injected edges. These four edges are **policy-only** — they have no textual provenance in the bodies of #503 or #474.

Edges are reconstructed from the combination of Markdown body text and `PROGRAM_GATES` policy, not from GitHub's dependency API.

---

## 7. Epic Execution Checklist (observed)

Epic issues contain an execution checklist in their body text.

**Observation:** The checklist is a **consistency assertion** — it asserts what should be true when the epic is complete. It does not represent live task tracking.

---

## 8. `ready-for-agent` Label (observed 2026-07-12)

**Observation:** The `ready-for-agent` label appears on issues that are also blocked by open dependencies. This indicates the label means **scoped and well-defined** (an agent can understand and begin work), **not** that the issue is ready to merge or ship.

---

## 9. Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-07-12 | Initial verified facts. | Work Frontier |
| 2026-07-12 | Rewritten: stripped to observed-only facts. Removed unverified branch/merge claims. Added markers, prose, checklist, label semantics. | Work Frontier |
| 2026-07-12 | Principal audit: corrected §5 terminals by ProgramSpec. Rewrote §6 with textual vs policy provenance; removed false body-text claims for #503/#474. | Work Frontier |

---

> **Observed facts only.** Do not add claims without a verifiable source and observation timestamp. Design opinions → ADRs. Implementation plans → WF-DEL-*.

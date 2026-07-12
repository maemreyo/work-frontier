---
id: ADR-002
title: "Tracker-Neutral Snapshot-to-Decision Engine"
status: accepted
owner: Work Frontier architecture
date: 2026-07-12
scope: Work Frontier core architecture
classification: decision
related: [WF-REF-001, WF-DEL-001]
---

# ADR-002: Tracker-Neutral Snapshot-to-Decision Engine

## Status

Accepted

## Context

Work Frontier ingests work items, normalizes them into a dependency graph, computes readiness, and surfaces the recommended next task. WF-REF-001 shows the #539 fixture has no native subissues, no dependency API edges, no Projects. Dependencies live in Markdown `## Blocked by`. Markers are HTML comments. `## Parent` prose exists but isn't parsed. A tracker-coupled engine would miss these.

## Decision

The Frontier Engine is **tracker-neutral**. It reads normalized snapshots via TrackerConnection adapters, never raw tracker APIs.

```
Tracker Source → TrackerConnection (adapter) → Snapshot Store → Frontier Engine → Control Room
```

| Engine depends on | Tracker-neutral? |
|------------------|-----------------|
| Snapshot schema (WorkItem, edges, authority) | Yes |
| Policy config | Yes |
| Feature flags | Yes |

Tracker-aware code stays in TrackerConnection adapters only.

## Consequences

**+** Survives tracker migrations. Testable without API. New tracker = new adapter.
**-** Adapter maintenance per tracker. Schema is critical contract.

---

| Date | Change | Author |
|------|--------|--------|
| 2026-07-12 | Accepted. | Work Frontier |

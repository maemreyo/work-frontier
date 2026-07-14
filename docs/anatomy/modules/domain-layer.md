# Module: Domain Layer

**Path:** `backend/src/work_frontier/domain`
**Role:** Pure business rules, entities, value objects, policies, authority reconciliation, frontier engine, graph traversal, proposals, authorization, coordination, cutover, and emergency access.

## Public interface

- `Authority` and authority reconciliation with precedence and freshness ordering.
- `FrontierItem`, `FrontierEngine` — readiness frontier computation and ranking.
- `DependencyGraph` — dependency graph with reachability and acyclicity checking.
- `WorkItem`, `Decision`, `Lease`, `Proposal` — core domain entities.
- `Policy` evaluation for decision gates and completion conditions.
- `Authorization` — role-based access control rules.
- `Coordination` — lease coordination and fencing tokens.
- `Cutover` — writer cutover domain logic.
- `Emergency` — break-glass emergency access policies.

## Internal structure

- `authority.py` — authority types, precedence, freshness, reconciliation.
- `entities.py` — core domain entities (WorkItem, Decision, Lease, Proposal).
- `frontier.py` — frontier engine with ranking and cursor-based pagination.
- `graph.py` — dependency graph with incrementality, reachability, and cycle detection.
- `edges.py` — edge and dependency relationship types.
- `policies.py` — policy gate evaluators.
- `identifiers.py` — branded domain identifier types.
- `errors.py` — domain-specific typed errors.
- `authorization.py` — RBAC authorization rules.
- `coordination.py` — lease coordination and fencing.
- `cutover.py` — writer cutover domain logic.
- `emergency.py` — break-glass emergency access.
- `proposals.py` — proposal lifecycle and validation.

## Depends on

- No internal module dependencies; pure Python with no framework imports.

## Used by

None confirmed.

## Data & side effects

- Pure domain logic with no I/O or side effects.

---

_Traced from source on 2026-07-14. Files examined in depth: all 14 files._

# System Diagram: Work Frontier

## System context

```mermaid
graph LR
system["Work Frontier"]
actor0(("Developer"))
actor1(("GitHub Actions"))
external0["PostgreSQL"]
external1["MinIO"]
actor0 -->|runs checks and harnesses| system
actor1 -->|executes CI workflow| system
system -->|migration smoke| external0
system -->|object lifecycle smoke| external1
```

## Module dependency graph

```mermaid
graph TD
foundation-preflight["Foundation Preflight"]
contracts["Canonical Contracts"]
evidence-runtime["Evidence Runtime"]
architecture-enforcement["Architecture Enforcement"]
contract-generation["Contract Generation"]
infrastructure-smoke["Infrastructure Smoke"]
frontend-foundation["Frontend Foundation"]
delivery-ci["Delivery and CI"]
foundation-preflight --> contracts
evidence-runtime --> contracts
architecture-enforcement --> contracts
contract-generation --> contracts
infrastructure-smoke --> contracts
frontend-foundation --> contract-generation
delivery-ci --> foundation-preflight
delivery-ci --> contract-generation
delivery-ci --> architecture-enforcement
delivery-ci --> evidence-runtime
delivery-ci --> infrastructure-smoke
delivery-ci --> frontend-foundation
```

Modules: [Foundation Preflight](modules/foundation-preflight.md) · [Canonical Contracts](modules/contracts.md) · [Evidence Runtime](modules/evidence-runtime.md) · [Architecture Enforcement](modules/architecture-enforcement.md) · [Contract Generation](modules/contract-generation.md) · [Infrastructure Smoke](modules/infrastructure-smoke.md) · [Frontend Foundation](modules/frontend-foundation.md) · [Delivery and CI](modules/delivery-ci.md)

## Key flows

### Foundation preflight gate

```mermaid
sequenceDiagram
participant p0 as "GitHub Actions"
participant p1 as "foundation-preflight"
participant p2 as "contracts"
p0->>p1: run validator and tests
p1->>p2: apply contract-specific rules
p1->>p0: pass/fail plus evidence
```

### Contract generation and drift check

```mermaid
sequenceDiagram
participant p0 as "delivery-ci"
participant p1 as "contract-generation"
participant p2 as "contracts"
participant p3 as "frontend-foundation"
p0->>p1: run --check
p1->>p2: read Pydantic schema
p1->>p3: compare generated Zod artifact
```

### Harness evidence lifecycle

```mermaid
sequenceDiagram
participant p0 as "delivery-ci"
participant p1 as "evidence-runtime"
participant p2 as "contracts"
participant p3 as "infrastructure-smoke"
p0->>p1: execute blocking harnesses
p1->>p2: validate registry and evidence
p1->>p3: run smoke commands
p1->>p0: return evidence bound to subject SHA
```

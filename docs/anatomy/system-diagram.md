# System Diagram: Work Frontier

## System context

```mermaid
graph LR
developer((Developer)) -->|runs checks| wf[Work Frontier foundation toolchain]
gha[GitHub Actions] -->|executes workflow| wf
wf -->|migration smoke| pg[(PostgreSQL)]
wf -->|object lifecycle smoke| minio[(MinIO)]
```

## Module dependency graph

```mermaid
graph TD
foundation_preflight[foundation-preflight] -->|validates DecisionRecord-shaped baseline documents and hash fields| contracts[contracts]
evidence_runtime[evidence-runtime] -->|loads registry and evidence schemas and serializes validated records| contracts[contracts]
architecture_enforcement[architecture-enforcement] -->|writes EvidenceRecord-compatible results for the boundary check| contracts[contracts]
contract_generation[contract-generation] -->|imports the canonical DecisionRecord model as the source schema| contracts[contracts]
infrastructure_smoke[infrastructure-smoke] -->|emits structured evidence for infrastructure checks| contracts[contracts]
frontend_foundation[frontend-foundation] -->|consumes the generated DecisionRecord Zod schema| contract_generation[contract-generation]
delivery_ci[delivery-ci] -->|runs the preflight gate before verification| foundation_preflight[foundation-preflight]
delivery_ci[delivery-ci] -->|checks generated contract drift| contract_generation[contract-generation]
delivery_ci[delivery-ci] -->|runs import-boundary enforcement through the harness suite| architecture_enforcement[architecture-enforcement]
delivery_ci[delivery-ci] -->|executes registered harnesses and records evidence| evidence_runtime[evidence-runtime]
delivery_ci[delivery-ci] -->|starts services and executes database/object-store smokes| infrastructure_smoke[infrastructure-smoke]
delivery_ci[delivery-ci] -->|runs frontend quality checks| frontend_foundation[frontend-foundation]
```

Modules: [foundation-preflight](modules/foundation-preflight.md) · [contracts](modules/contracts.md) · [evidence-runtime](modules/evidence-runtime.md) · [architecture-enforcement](modules/architecture-enforcement.md) · [contract-generation](modules/contract-generation.md) · [infrastructure-smoke](modules/infrastructure-smoke.md) · [frontend-foundation](modules/frontend-foundation.md) · [delivery-ci](modules/delivery-ci.md)

## Key flows

### Foundation preflight gate

```mermaid
sequenceDiagram
participant GitHub Actions as GitHub Actions
participant foundation_preflight as foundation-preflight
participant contracts as contracts
GitHub Actions->>foundation_preflight: run validator and tests
foundation_preflight->>contracts: apply contract-specific rules
foundation_preflight->>GitHub Actions: pass/fail plus evidence
```

### Contract generation and drift check

```mermaid
sequenceDiagram
participant delivery_ci as delivery-ci
participant contract_generation as contract-generation
participant contracts as contracts
participant frontend_foundation as frontend-foundation
delivery_ci->>contract_generation: run --check
contract_generation->>contracts: read Pydantic schema
contract_generation->>frontend_foundation: compare generated Zod artifact
```

### Harness evidence lifecycle

```mermaid
sequenceDiagram
participant delivery_ci as delivery-ci
participant evidence_runtime as evidence-runtime
participant contracts as contracts
participant infrastructure_smoke as infrastructure-smoke
delivery_ci->>evidence_runtime: execute blocking harnesses
evidence_runtime->>contracts: validate registry and evidence
evidence_runtime->>infrastructure_smoke: run smoke commands
evidence_runtime->>delivery_ci: return evidence bound to subject SHA
```

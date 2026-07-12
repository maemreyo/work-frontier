---
id: WF-VI-003
title: "Tổng quan vận hành: Work Frontier"
status: accepted
owner: Work Frontier operations
date: 2026-07-12
scope: Work Frontier operations
classification: vi-curated
language: vi
canonical: [ADR-003, ADR-005, WF-REF-002, WF-DEL-001]
---

# WF-VI-003: Tổng quan vận hành

> Về Work Frontier sản phẩm. Xem tài liệu tiếng Anh canonical.

---

## 1. Kiến trúc

Work Frontier là **deep modular monolith** với 13 module, 4 lớp.

**Domain:** identity, tenancy, connections, graph, policies, decisions, audit
**Application:** ingestion, normalization, projections, approvals, copilot
**Interfaces:** control-room

**Nguồn:** [ADR-003](../decisions/ADR-003-modular-monolith.md)

---

## 2. Writer Ownership States

| Trạng thái | Hành động |
|-----------|---------|
| Legacy active | Legacy script sở hữu writer |
| Shadow | Cả 2 chạy, chỉ legacy xuất bản |
| Projection active | Work Frontier sở hữu writer |

Rollback: khôi phục legacy writer. < 5 phút. Stale-write guard: từ chối ghi khi snapshot cũ.

**Nguồn:** [ADR-005](../decisions/ADR-005-github-first-controlled-cutover.md)

---

## 3. 13 Stage Harness Gate

| Stage | Module | Gate chính |
|-------|--------|-----------|
| 1 | Foundation | Schema validation |
| 2a | Tenancy + Identity | Isolation, identity test |
| 2b | Persistence + Ledger | Immutability, checksum |
| 3 | GitHub + Ingestion + Normalization | Fixture 100% |
| 4 | Reconciliation | Precedence test |
| 5 | Graph + Policy + Decisions | Acyclic, deterministic |
| 6 | Evidence + Gates | Gate-evidence wiring |
| 7 | Projections + Approvals | Projection labeling, approval |
| 8 | Claims + Attention | Anomaly emission |
| 9 | REST + CLI | OpenAPI, CLI smoke |
| 10 | Control Room UX | Display accuracy |
| 11 | Copilot | Determinism, AI boundary |
| 12 | Operations + Security | Alert, security, backup |
| 13 | Certification + Cutover | Fixture cert, rollback drill |

**Nguồn:** [WF-DEL-001](../delivery/implementation-sequence.md)

---

## 4. DoD (Definition of Done)

13 stage xanh, 13 module hoàn thành, 100% fixture, writer ownership rõ ràng, evidence records append-only, graph được kiểm tra cycle, policy deterministic, AI boundary, REST valid, CLI smoke, UX accessible, monitoring/alert/backup, security audit, cutover đạt semantic parity, rollback < 5 phút, không P0/P1, tài liệu được review.

**Nguồn:** [WF-DEL-001 §3](../delivery/implementation-sequence.md)

---

## 5. Liên kết

| Nội dung | Tài liệu |
|----------|---------|
| ADR modular monolith | [ADR-003](../decisions/ADR-003-modular-monolith.md) |
| ADR cutover | [ADR-005](../decisions/ADR-005-github-first-controlled-cutover.md) |
| Kế hoạch cuối cùng | [WF-REF-002](../reference/oh-my-class/shadow-compare-cutover.md) |
| Thứ tự triển khai | [WF-DEL-001](../delivery/implementation-sequence.md) |
| Tổng quan | [WF-VI-001](./work-frontier-overview.md) |

---

## Change Log

| Ngày | Thay đổi | Tác giả |
|------|---------|---------|
| 2026-07-12 | Tổng quan vận hành ban đầu. | Work Frontier |
| 2026-07-12 | Viết lại: 13 module, 13 stage, full DoD. | Work Frontier |
| 2026-07-12 | Kiểm tra chính: thêm dấu tiếng Việt. Thay Feature Flag bằng Writer Ownership States. | Work Frontier |

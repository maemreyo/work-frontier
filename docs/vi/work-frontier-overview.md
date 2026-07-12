---
id: WF-VI-001
title: "Tổng quan Work Frontier: Sản phẩm điều khiển sẵn sàng"
status: accepted
owner: Work Frontier product
date: 2026-07-12
scope: Work Frontier product
classification: vi-curated
language: vi
canonical: [WF-REF-001, WF-REF-002, WF-DEL-001, ADR-002, ADR-003]
---

# WF-VI-001: Tổng quan Work Frontier

> Tài liệu tiếng Việt curated. Xem tài liệu tiếng Anh canonical cho chi tiết.

---

## 1. Work Frontier là gì?

Work Frontier là **sản phẩm điều khiển sẵn sàng** (readiness control plane) độc lập. Nó kết nối với hệ thống theo dõi công việc (ví dụ: GitHub Issues), chuẩn hóa dữ liệu thành đồ thị phụ thuộc, tính toán sẵn sàng, và đề xuất **việc làm tiếp theo** tốt nhất.

Work Frontier **không phải** phần mềm giáo dục hay hệ thống tạo nội dung. Nó là công cụ kỹ thuật phục vụ nhóm phát triển.

**Nguồn:** [Product Vision](../product/vision.md), [Product Overview](../product/overview.md)

---

## 2. Ba lớp kiến trúc

```
Hệ thống theo dõi (GitHub, Linear, Jira...)
        │
        ▼
┌──────────────────────┐
│  TrackerConnection    │  ← Adapter: chuẩn hóa dữ liệu
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│              Frontier Engine                   │
│  Ingest → Authority Merge → Edge Graph →      │
│  Gate Eval → Readiness → Ranking →            │
│  Recommended Next                              │
└──────────┬───────────────────────────────────┘
           │
           ▼
┌──────────────────────┐
│  Frontier Control Room│  ← Giao diện người dùng
└──────────────────────┘
```

**Nguồn:** [ADR-002](../decisions/ADR-002-tracker-neutral-engine.md)

---

## 3. 13 Module

| Lớp | Module | Trách nhiệm |
|-----|--------|-----------|
| Domain | identity | Xác định actor |
| Domain | tenancy | Quản lý tenant |
| Domain | connections | Quản lý kết nối tracker |
| Domain | graph | Đồ thị phụ thuộc |
| Domain | policies | Quy tắc sẵn sàng |
| Domain | decisions | DecisionRecord, readiness và xếp hạng xác định |
| Domain | audit | Evidence ledger chỉ ghi thêm |
| Application | ingestion | Thu thập dữ liệu từ adapter |
| Application | normalization | Chuẩn hóa loại tracker → domain |
| Application | projections | Ảnh hiện tại, auto-projection |
| Application | approvals | Phê duyệt, HITL |
| Application | copilot | Giải thích quyết định và đề xuất thay đổi; không sở hữu xếp hạng |
| Interfaces | control-room | REST/OpenAPI, CLI |

**Nguồn:** [ADR-003](../decisions/ADR-003-modular-monolith.md)

---

## 4. Fixture oh-my-class #539

#539 là **dữ liệu mẫu đã xác minh** để kiểm tra chính xác projection.

- Có markers `<!-- omc-program:...; issue:... -->`
- Có phần `## Parent` nhưng generator hiện tại không parse
- Dependencies từ `## Blocked by` và `PROGRAM_GATES` policy
- 5 Epics, 5 terminals (xác định bởi ProgramSpec)
- Policy edges (#538→#503, #487/#503/#521→#474) có thể không có trong body text
- `ready-for-agent` = scoped, không phải ready

**Nguồn:** [WF-REF-001](../reference/oh-my-class/verified-facts.md)

---

## 5. Quy trình cuối cùng (8 pha)

1. **Import** — Đọc dữ liệu, tạo snapshot
2. **Shadow** — Chạy cả 2 engine, chỉ gửi legacy
3. **Compare exact DecisionRecord/report** — So sánh trường từng trường
4. **Approval** — Nhóm duyệt, rollback tested
5. **Disable old workflow and claim owner** — Tắt legacy, Work Frontier sở hữu writer
6. **Publish** — Projection xuất bản
7. **Observe** — Giám sát ổn định
8. **Legacy verify-only/retire** — Legacy chỉ đọc, sau đó nghỉ hưu

**Nguồn:** [WF-REF-002](../reference/oh-my-class/shadow-compare-cutover.md)

---

## 6. Điều kiện sẵn sàng sản xuất (DoD)

1. 13 stage đã xây và gate xanh.
2. 13 module hoàn thành.
3. 100% fixtrue xử lý đúng.
4. Writer ownership states hoạt động. Stale-write guard hoạt động.
5. Evidence ledger chỉ ghi thêm, checksum chain.
6. Graph acyclic sau mỗi mutation.
7. Policy deterministic.
8. AI không bypass lifecycle/gates.
9. REST/OpenAPI valid.
10. CLI smoke test.
11. Control Room UX accessible.
12. Monitoring, alert, backup/restore.
13. Security audit pass.
14. Cutover đạt tương đương ngữ nghĩa chính xác cho DecisionRecord và báo cáo được quản lý; khác biệt trình bày phải được phê duyệt rõ ràng.
15. Rollback < 5 phút.
16. Không P0/P1 open.
17. Tài liệu WF-REF, WF-DEL, ADR, Vietnamese accepted.

**Nguồn:** [WF-DEL-001 §3](../delivery/implementation-sequence.md)

---

## 7. Liên kết

| Nội dung | Tài liệu |
|----------|---------|
| Sự thật đã xác minh | [WF-REF-001](../reference/oh-my-class/verified-facts.md) |
| Kế hoạch cuối cùng | [WF-REF-002](../reference/oh-my-class/shadow-compare-cutover.md) |
| Thứ tự triển khai | [WF-DEL-001](../delivery/implementation-sequence.md) |
| Ma trận truy nguồn | [WF-DEL-002](../delivery/traceability-matrix.md) |
| Chỉ mục ADR | [ADR-001](../decisions/ADR-index.md) |

---

## Change Log

| Ngày | Thay đổi | Tác giả |
|------|---------|---------|
| 2026-07-12 | Tổng quan ban đầu. | Work Frontier |
| 2026-07-12 | Viết lại: sản phẩm điều khiển sẵn sàng, full DoD, fix typo. | Work Frontier |
| 2026-07-12 | Kiểm tra chính: thêm dấu tiếng Việt. Sửa §5 thành 8 pha đúng. Sửa §4 policy edges. Sửa §6 writer ownership. | Work Frontier |

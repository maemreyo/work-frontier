---
id: WF-VI-002
title: "Hành trình người dùng: Work Frontier"
status: accepted
owner: Work Frontier UX
date: 2026-07-12
scope: Work Frontier user journeys
classification: vi-curated
language: vi
canonical: [WF-REF-001, WF-REF-002, WF-DEL-001, product/overview.md]
---

# WF-VI-002: Hành trình người dùng

> Ba vai trò: Builder, Coordinator, Operator. Xem tài liệu tiếng Anh canonical.

---

## 1. Builder (Người xây dựng)

Cấu hình pipeline projection và module.

| Bước | Hành động | Kết quả |
|------|----------|---------|
| 1 | Cấu hình TrackerConnection cho GitHub | Adapter sẵn sàng |
| 2 | Xác định schema snapshot | Schema đã xác định |
| 3 | Xây dựng domain types (WorkItem, edges, authority) | Domain types valid |
| 4 | Xây dựng graph + policies + decisions | Graph deterministic |
| 5 | Xây dựng projection + approval pipeline | Pipeline hoàn chỉnh |
| 6 | Xây dựng evidence ledger | Ledger append-only |
| 7 | Chạy fixture test (WF-REF-001) | 100% facts reproduced |

**Nguồn:** [WF-DEL-001 Stages 1-7](../delivery/implementation-sequence.md)

---

## 2. Coordinator (Người điều phối)

Quản lý cuối cùng từ legacy sang projection.

| Bước | Hành động | Kết quả |
|------|----------|---------|
| 1 | Xác nhận fixtrue import đúng | Snapshot xác nhận |
| 2 | Kích hoạt Shadow mode | Cả 2 engine chạy |
| 3 | Xem báo cáo so sánh | Fidelity score |
| 4 | Field-by-field comparison exact DecisionRecord/report | Phân tích chi tiết |
| 5 | Duyet approval | Writer ownership chuyển |
| 6 | Disable legacy, claim owner | Work Frontier sở hữu |
| 7 | Publish projection | Projection xuất bản |
| 8 | Giám sát ổn định | On dinh |

**Nguồn:** [WF-REF-002](../reference/oh-my-class/shadow-compare-cutover.md)

---

## 3. Operator (Người vận hành)

Quản trị hàng ngày.

| Bước | Hành động | Kết quả |
|------|----------|---------|
| 1 | Theo dõi dashboard (fidelity, error, latency) | Dashboard hoạt động |
| 2 | Xử lý alert fidelity > 5% | Alert xử lý |
| 3 | Xử lý alert error > 5% | Rollback thực hiện |
| 4 | Kiểm tra stale-write incidents | Không có stale write |
| 5 | Kiểm tra link health | Link integrity OK |
| 6 | Báo cáo hàng tuần | Báo cáo ổn định |

**Nguồn:** [WF-REF-002 §5](../reference/oh-my-class/shadow-compare-cutover.md)

---

## 4. Liên kết

| Nội dung | Tài liệu |
|----------|---------|
| Tổng quan | [WF-VI-001](./work-frontier-overview.md) |
| Thứ tự triển khai | [WF-DEL-001](../delivery/implementation-sequence.md) |
| Kế hoạch cuối cùng | [WF-REF-002](../reference/oh-my-class/shadow-compare-cutover.md) |

---

## Change Log

| Ngày | Thay đổi | Tác giả |
|------|---------|---------|
| 2026-07-12 | Hành trình người dùng (Builder, Coordinator, Operator). | Work Frontier |
| 2026-07-12 | Kiểm tra chính: thêm dấu tiếng Việt. Sửa Coordinator theo 8 pha đúng. Sửa Operator: stale-write thay vì flag. | Work Frontier |

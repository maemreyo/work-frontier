---
id: WF-VI-004
title: "Thuật ngữ: Work Frontier"
status: accepted
owner: Work Frontier domain
date: 2026-07-12
scope: Work Frontier terminology
classification: vi-curated
language: vi
canonical: [WF-REF-001, ADR-002, ADR-003, ADR-004, product/vision.md]
---

# WF-VI-004: Thuật ngữ

> Thuật ngữ Work Frontier. Xem tài liệu tiếng Anh canonical.

---

## 1. Sản phẩm

| Tiếng Việt | Tiếng Anh | Định nghĩa |
|-----------|----------|-----------|
| Sản phẩm điều khiển sẵn sàng | Readiness control plane | Hệ thống tính toán sẵn sàng và đề xuất việc tiếp theo |
| Đồ thị phụ thuộc | Dependency graph | Mối quan hệ giữa các work items |
| Việc làm tiếp theo | Recommended Next | WorkItem được xếp hạng cao nhất |
| Quy tắc sẵn sàng | Readiness policy | Quy định điều kiện sẵn sàng |
| Đánh giá gate | Gate evaluation | Kiểm tra điều kiện cho từng WorkItem |
| Xếp hạng | Ranking | Xếp hạng deterministic, lexicographic |

---

## 2. Domain

| Tiếng Việt | Tiếng Anh | Định nghĩa |
|-----------|----------|-----------|
| WorkItem | WorkItem | Đơn vị công việc cơ bản |
| DecisionRecord | DecisionRecord | WorkItem được phong phú với ranking, gate, provenance |
| Authority status | Authority status | Quyền ưu tiên giữa các nguồn dữ liệu |
| Provenance | Provenance | Ai nói gì, khi nào, từ nguồn nào |
| WorkLease | WorkLease | Sở hữu chính (leaseholder) và tham gia phụ của một WorkItem |
| AttentionItem | AttentionItem | Tín hiệu bất thường, cần hành động |
| EvidenceRecord | EvidenceRecord | Băng ghi trong evidence ledger, typed entry cho completion policies |

---

## 3. Module

| Tiếng Việt | Tiếng Anh | Lớp |
|-----------|----------|-----|
| Xác định | identity | Domain |
| Quản lý tenant | tenancy | Domain |
| Kết nối tracker | connections | Domain |
| Đồ thị | graph | Domain |
| Quy tắc | policies | Domain |
| Quyết định | decisions | Domain |
| Sổ chi ghi thêm | audit | Domain |
| Thu thập | ingestion | Application |
| Chuẩn hóa | normalization | Application |
| Ảnh hiện tại | projections | Application |
| Phê duyệt | approvals | Application |
| Copilot | copilot | Application |
| Điều khiển | control-room | Interfaces |

---

## 4. Fixture

| Tiếng Việt | Tiếng Anh | Định nghĩa |
|-----------|----------|-----------|
| Dữ liệu mẫu | Reference fixture | Dữ liệu đã xác minh để kiểm tra |
| Marker | `<!-- omc-program:...; issue:... -->` | Nhóm issue theo program |
| `## Blocked by` | Dependency prose | Phụ thuộc trong Markdown body |
| `## Parent` | Parent prose | Mối quan hệ cha (không được parse) |
| ready-for-agent | ready-for-agent | Scoped, không phải ready |
| PROGRAM_GATES | ProgramSpec policy edges | Policy edges thêm vào ngay cả khi body không liệt kê |

---

## 5. Liên kết

| Nội dung | Tài liệu |
|----------|---------|
| Fixture glossary | [WF-REF-001](../reference/oh-my-class/verified-facts.md) |
| ADR index | [ADR-001](../decisions/ADR-index.md) |
| Tổng quan | [WF-VI-001](./work-frontier-overview.md) |
| Vision | [product/vision.md](../product/vision.md) |

---

## Change Log

| Ngày | Thay đổi | Tác giả |
|------|---------|---------|
| 2026-07-12 | Thuật ngữ ban đầu. | Work Frontier |
| 2026-07-12 | Viết lại: chỉ thuật ngữ Work Frontier sản phẩm. | Work Frontier |
| 2026-07-12 | Kiểm tra chính: sửa "Diễn đàn" → "Thuật ngữ". Thêm dấu tiếng Việt. Sửa WorkLease definition. Thêm PROGRAM_GATES. | Work Frontier |

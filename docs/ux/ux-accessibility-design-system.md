---
title: Work Frontier — Accessibility and Design System
id: WF-UX-007
version: 2.0.0
status: canonical
owner: UX Architecture
last_updated: "2026-07-12"
replaces: 1.0.0
supersedes: null
---

# Accessibility and Design System Specification

> **Purpose**: Defines the accessibility standards, design system foundations, and task harness acceptance criteria for Work Frontier. Every pixel shipped must conform to this spec.

---

## 1. Accessibility Standard

**Work Frontier targets WCAG 2.2 Level AA as the minimum.** No feature ships without meeting every applicable success criterion at the AA level.

### 1.1 WCAG 2.2 Specific Criteria

These WCAG 2.2 criteria receive explicit attention because they affect Work Frontier's interactive patterns:

| Criterion | Work Frontier Relevance |
|-----------|------------------------|
| **2.4.11 Focus Not Obscured (Minimum)** | Builder canvas "What next" is sticky. Focus indicators on WorkItems must never be hidden behind it. |
| **2.4.13 Focus Appearance** | All interactive elements use a focus indicator with ≥ 3:1 contrast ratio against adjacent colors, ≥ 2px perimeter. |
| **2.5.7 Dragging Movements** | WorkItem reordering in Program views must have a non-drag alternative (move up/down buttons or keyboard shortcuts). |
| **2.5.8 Target Size (Minimum)** | All touch/click targets ≥ 24×24 CSS pixels. Decision type badges, status indicators, and copilot accept/dismiss buttons meet this. |
| **3.2.6 Consistent Help** | Help link position is consistent across all views: always in the same location in the header or footer. |
| **3.3.7 Redundant Entry** | Onboarding forms do not ask for the same information twice across steps. |
| **3.3.8 Accessible Authentication (Minimum)** | Login does not rely solely on cognitive function tests (CAPTCHAs, puzzles). SSO or password with optional TOTP. |

### 1.2 General WCAG 2.2 AA Criteria

All remaining applicable WCAG 2.2 AA criteria apply. Key areas:

| Category | Applicable Criteria |
|----------|-------------------|
| **Perceivable** | 1.1.1 Non-text Content, 1.3.1 Info and Relationships, 1.3.4 Orientation, 1.4.3 Contrast (Minimum), 1.4.4 Resize Text, 1.4.10 Reflow, 1.4.11 Non-text Contrast, 1.4.13 Content on Hover or Focus |
| **Operable** | 2.1.1 Keyboard, 2.1.2 No Keyboard Trap, 2.4.1 Bypass Blocks, 2.4.2 Page Titled, 2.4.3 Focus Order, 2.4.6 Headings and Labels, 2.4.7 Focus Visible, 2.5.1 Pointer Gestures, 2.5.2 Pointer Cancellation |
| **Understandable** | 3.1.1 Language of Page, 3.2.1 On Focus, 3.2.2 On Input, 3.3.1 Error Identification, 3.3.3 Error Suggestion, 3.3.4 Error Prevention |
| **Robust** | 4.1.2 Name, Role, Value |

---

## 2. Keyboard and Screen Reader Requirements

### 2.1 Keyboard Navigation

| Rule | Description |
|------|-------------|
| KB-01 | Every interactive element is reachable via `Tab` in a logical order. |
| KB-02 | No keyboard traps exist anywhere in the UI. `Escape` always closes modals, drawers, and popovers. |
| KB-03 | Arrow keys navigate within composite widgets (kanban board, WorkItem list, decision feed). |
| KB-04 | `Enter` or `Space` activates buttons and links. |
| KB-05 | Global keyboard shortcuts are available and discoverable via `?` shortcut: |
| | `1`-`4` Switch to Builder / Coordinator / Executive / Operator |
| | `/` Search |
| | `Esc` Close current overlay, return to canvas |
| | `?` Toggle shortcut help |
| KB-06 | Shortcuts never conflict with screen reader shortcuts (e.g., VoiceOver's `VO+` combos, NVDA modifier keys). |
| KB-07 | Focus is managed programmatically: when a modal opens, focus moves to the modal. When it closes, focus returns to the trigger. |
| KB-08 | Live regions (`aria-live="polite"`) announce copilot proposals, decision changes, and status updates. |

### 2.2 Screen Reader Support

| Rule | Description |
|------|-------------|
| SR-01 | All views use proper ARIA landmarks: `<main>`, `<nav>`, `<aside>`, `<header>`, `<footer>`. |
| SR-02 | Decision type cards include `role="article"` with `aria-label` containing the decision type and a one-line summary. |
| SR-03 | Copilot ProposedChanges are wrapped in `aria-live="polite"` regions. They are announced when they appear and when they are accepted/dismissed. |
| SR-04 | The Program canvas uses `role="list"` / `role="listitem"` for WorkItem cards. Reordering is announced via live region: "Moved [WorkItem] to position [N]." |
| SR-05 | Empty states include meaningful text, not just illustrations. Every empty state has an `aria-label` or visible heading. |
| SR-06 | Charts and graphs (Executive view) have table equivalents. See §5. |
| SR-07 | Form validation errors are associated with their fields via `aria-describedby` and announced via `aria-live="assertive"`. |

---

## 3. CJK and Localization

### 3.1 Text Expansion

| Language Family | Typical Expansion | Tested At |
|----------------|-------------------|-----------|
| English (base) | 1.0× | Default |
| French / German / Spanish | 1.2–1.5× | 1.5× |
| Japanese | 1.5–2.0× | 2.0× |
| Chinese (Simplified / Traditional) | 1.0–1.3× | 1.5× |
| Korean | 1.2–1.5× | 1.5× |
| Arabic | 1.0–1.5× | 1.5× |

| Rule | Description |
|------|-------------|
| L10N-01 | No UI element assumes a fixed text width. All containers use `min-width` with `max-width` and `overflow-wrap: break-word`. |
| L10N-02 | Button labels truncate with ellipsis after a minimum readable length. Tooltip shows full text. |
| L10N-03 | Decision type labels ("Computed", "Policy", "AI suggestion", etc.) are translated and tested at 2× expansion. |
| L10N-04 | Date and time formatting uses the user's locale. ISO 8601 is the wire format; display is localized. |

### 3.2 Vertical Text

| Rule | Description |
|------|-------------|
| VT-01 | Japanese vertical text mode (`writing-mode: vertical-rl`) is available as a **user preference** in the Builder canvas WorkItem cards and decision feed. Vertical text is not required by default and is not activated automatically based on locale. |
| VT-02 | Vertical text does not break layout: cards resize, action bars reposition to the top or bottom edge. |
| VT-03 | Vertical text is a user preference, not auto-detected from locale. The user must explicitly enable it in accessibility settings. |
| VT-04 | Vertical text is only supported where it is justified by the content or user need. It is not a blanket requirement for CJK locales. |

### 3.3 Right-to-Left (RTL)

| Rule | Description |
|------|-------------|
| RTL-01 | All layouts mirror for Arabic, Hebrew, and Persian. Navigation moves to the right side. |
| RTL-02 | Icons that imply direction (arrows, chevrons) flip horizontally in RTL mode. |
| RTL-03 | Decision type borders and accents maintain their semantic meaning in RTL. |

### 3.4 Viewport Range

Work Frontier must render correctly across the full viewport range: 320px minimum to ultrawide (≥ 2560px).

| Rule | Description |
|------|-------------|
| VR-01 | At 320px, the Builder view collapses to a single column. "What next" and the WorkItem list are stacked. No horizontal scroll. |
| VR-02 | At 768px, secondary navigation is accessible via bottom sheet or hamburger. Two-column layout becomes available. |
| VR-03 | At 1280px, full four-view navigation is visible. Builder and Coordinator can show side-by-side detail panels. |
| VR-04 | At ultrawide (≥ 2560px), content is max-width constrained. The Builder canvas does not stretch to fill the full viewport. Max content width is 1440px, centered. |
| VR-05 | All disclosure levels (L1–L4 per [UX Architecture §4.1](ux-architecture.md#41-disclosure-levels)) are accessible at every viewport width. |

### 3.5 High Contrast and Reduced Motion

| Rule | Description |
|------|-------------|
| HC-01 | Work Frontier respects `prefers-contrast: more` and `prefers-color-scheme: dark`. High contrast mode increases border widths, text contrast, and removes translucent overlays. |
| HC-02 | In high contrast mode, all decision type visual treatments remain distinguishable. Border styles (solid, dashed, dotted, striped) are the primary differentiator, not color alone. |
| HC-03 | Work Frontier respects `prefers-reduced-motion: reduce`. All animations are disabled or reduced to opacity-only transitions. No content moves or animates. |
| HC-04 | Reduced motion mode is tested on every animated element: pulse animations, slide transitions, toast notifications, and Copilot proposal appearances. |

---

## 4. Design System Foundations

### 4.1 Typography

| Token | Value | Use |
|-------|-------|-----|
| `--font-sans` | `system-ui, -apple-system, 'Segoe UI', Roboto, 'Noto Sans', 'Noto Sans CJK SC', 'Noto Sans CJK JP', 'Noto Sans CJK KR', sans-serif` | Body text. CJK fonts in the stack ensure no FOUT for CJK users. |
| `--font-mono` | `'SF Mono', 'Fira Code', 'Noto Sans Mono CJK', monospace` | Code snippets, technical content. |
| `--text-xs` | 12px | Labels, captions. |
| `--text-sm` | 14px | Secondary text, metadata. |
| `--text-base` | 16px | Body text. Minimum for readable content. |
| `--text-lg` | 18px | Section headings within cards. |
| `--text-xl` | 24px | View-level headings. |
| `--text-2xl` | 32px | Program titles in Builder canvas. |

### 4.2 Color System

| Token | Purpose | Contrast (on white) |
|-------|---------|-------------------|
| `--color-text-primary` | Body text | ≥ 7:1 |
| `--color-text-secondary` | Metadata, timestamps | ≥ 4.5:1 |
| `--color-text-disabled` | Inactive elements | ≥ 3:1 (non-text contrast only) |
| `--color-border-default` | Card borders, dividers | ≥ 3:1 against background |
| `--color-action-primary` | Primary buttons, links | ≥ 4.5:1 |
| `--color-status-computed` | Computed decision border | Blue. ≥ 3:1 on white. |
| `--color-status-policy` | Policy decision border | Amber. ≥ 3:1 on white. |
| `--color-status-human` | Human override border | Green. ≥ 3:1 on white. |
| `--color-status-ai` | AI suggestion border | Purple (subtle). ≥ 3:1 on white. |
| `--color-status-degraded` | Degradation indicator | Red. ≥ 3:1 on white. |
| `--color-status-stale` | Stale data badge | Amber text. ≥ 4.5:1 on white. |
| `--color-status-provisional` | Provisional content border | Orange left accent. ≥ 3:1 on white. |

### 4.3 High Contrast Mode Tokens

| Token | Purpose | High Contrast Override |
|-------|---------|----------------------|
| `--hc-border-width` | Decision card borders in high contrast | `3px` (default: `2px`) |
| `--hc-text-contrast` | Text contrast in high contrast | `--color-text-primary` used for all text roles |
| `--hc-overlay-opacity` | Overlay/translucent elements | `1.0` (fully opaque) |

### 4.4 Spacing and Layout

| Token | Value |
|-------|-------|
| `--space-xs` | 4px |
| `--space-sm` | 8px |
| `--space-md` | 16px |
| `--space-lg` | 24px |
| `--space-xl` | 32px |
| `--space-2xl` | 48px |

| Rule | Description |
|------|-------------|
| DS-01 | All spacing uses the token scale. No ad-hoc pixel values. |
| DS-02 | Builder canvas WorkItem cards have a minimum `--space-lg` gap between them. |
| DS-03 | Action buttons have a minimum `--space-sm` gap between them. |
| DS-04 | Page-level padding is `--space-xl` on viewports ≥ 768px, `--space-md` on narrower viewports. |

### 4.5 Component Inventory

| Component | Where Used | Key Behavior |
|-----------|-----------|-------------|
| **Decision card** | Builder canvas, decision feed | Displays decision type with visual treatment per [UX Architecture §3](ux-architecture.md#3-decision-semantics). |
| **WorkItem card** | Builder canvas | Authority badge, freshness indicator, evidence status, claim/open-in-GitHub actions. |
| **Program card** | Coordinator board, Executive summary | Program name, readiness status, WorkItem count, risk indicator. |
| **Copilot ProposedChange** | Builder canvas (inline) | `AI suggestion` treatment, Accept/Dismiss actions, "View reasoning" disclosure. |
| **Status badge** | Everywhere | Single-line status with icon and label. |
| **Empty state** | Any view when data is absent | Illustration + heading + single action. |
| **Toast notification** | Any view | Auto-dismiss after 5s for informational, persistent for warnings. |
| **Modal dialog** | Confirmation, settings | Focus-trapped, `Escape` to close, returns focus to trigger. |
| **Drawer** | Context panel, settings | Slides from right. Focus trapped within. |
| **Sticky action bar** | Builder canvas (bottom) | Never obscures focused elements above it. |

---

## 5. Graph and Table Equivalence

Every chart, graph, or visual data representation in Work Frontier must have an equivalent accessible form.

| Rule | Description |
|------|-------------|
| GTE-01 | Every chart in the Executive view has a **View as table** toggle. |
| GTE-02 | The table equivalent uses semantic HTML `<table>`, `<thead>`, `<tbody>`, `<th>`, `<td>` with proper `scope` attributes. |
| GTE-03 | The toggle is a visible button, not a keyboard-only or screen-reader-only feature. |
| GTE-04 | When viewing the table equivalent, the chart is hidden (not stacked below it) to reduce cognitive load. |
| GTE-05 | The table includes the same data as the chart, with the same units and formatting. |
| GTE-06 | Executive trend charts provide `aria-label` describing the trend in natural language: "Readiness score increased from 65% to 82% over the last 4 weeks." |
| GTE-07 | Coordinator kanban boards can be viewed as a list table. |

---

## 6. Authority Status UI in Design System

Design system token definitions for the five authority statuses per [UX Architecture §5.1](ux-architecture.md#51-authority-statuses):

| Token | Value | Use |
|-------|-------|-----|
| `--color-authoritative` | `#2563EB` (blue-600) | Authoritative status border and icon. |
| `--color-authoritative-bg` | `#EFF6FF` (blue-50) | Authoritative card background. |
| `--color-stale` | `#B45309` (amber-700) | Stale badge text. |
| `--color-stale-bg` | `#FEF3C7` (amber-100) | Stale badge background. |
| `--color-conflicted` | `#DC2626` (red-600) | Conflicted status left accent. |
| `--color-conflicted-bg` | `#FEF2F2` (red-50) | Conflicted card background. |
| `--color-unavailable` | `#6B7280` (gray-500) | Unavailable status text. |
| `--color-unavailable-bg` | `#F9FAFB` (gray-50) | Unavailable card background. |
| `--color-provisional-border` | `#C2410C` (orange-700) | Left accent on provisional content. |
| `--color-provisional-bg` | `#FFF7ED` (orange-50) | Provisional card background. |
| `--border-style-stale` | `2px solid var(--color-stale)` | Stale indicator. |
| `--border-style-provisional` | `3px left solid var(--color-provisional-border)` | Provisional indicator. |
| `--border-style-conflicted` | `3px left solid var(--color-conflicted)` | Conflicted indicator. |
| `--border-style-degraded` | `2px repeating linear-gradient(45deg, var(--color-status-degraded), var(--color-status-degraded) 4px, transparent 4px, transparent 8px)` | Degraded decision card border. |

---

## 7. Task Harness Acceptance Criteria

A **task harness** is a structured acceptance test that validates a feature against this spec. Every feature must pass its task harness before shipping.

### 7.1 Harness Structure

Each harness entry specifies:

| Field | Description |
|-------|-------------|
| **ID** | Unique identifier: `WF-UX-007-TH-NNN`. |
| **Feature** | The feature being tested. |
| **Criterion** | The specific accessibility or design system rule being validated. |
| **Method** | How to test: automated scan, manual keyboard test, screen reader test, or visual regression. |
| **Pass condition** | The exact observable result that constitutes a pass. |
| **Blocking** | Whether a failure blocks release (always `true` for WCAG 2.2 AA criteria). |

### 7.2 Harness Entries

| ID | Feature | Criterion | Method | Pass Condition | Blocking |
|----|---------|-----------|--------|---------------|----------|
| WF-UX-007-TH-001 | Builder canvas | KB-01 through KB-08 | Manual keyboard | All interactive elements reachable via Tab in logical order. No traps. | Yes |
| WF-UX-007-TH-002 | Decision cards | DD-01, DD-06, SR-02 | Screen reader (NVDA/VoiceOver) | Decision type announced on focus. | Yes |
| WF-UX-007-TH-003 | Copilot ProposedChanges | SR-03, DD-02 | Screen reader | Proposal announced when it appears. Accept/dismiss announced. | Yes |
| WF-UX-007-TH-004 | Executive charts | GTE-01 through GTE-06 | Automated + manual | Table toggle works. Table contains same data. `aria-label` present. | Yes |
| WF-UX-007-TH-005 | CJK text expansion | L10N-01, L10N-02 | Visual regression at 2× | No truncation, no overflow, no overlap. | Yes |
| WF-UX-007-TH-006 | RTL layout | RTL-01 through RTL-03 | Visual regression in Arabic locale | Layout mirrors. Icons flip. Meaning preserved. | Yes |
| WF-UX-007-TH-007 | Focus appearance | WCAG 2.4.13 | Automated (axe-core) | All focus indicators ≥ 3:1 contrast, ≥ 2px perimeter. | Yes |
| WF-UX-007-TH-008 | Target size | WCAG 2.5.8 | Automated (axe-core) | All targets ≥ 24×24 CSS pixels. | Yes |
| WF-UX-007-TH-009 | Drag alternative | WCAG 2.5.7 | Manual keyboard | WorkItem reorder completable via move-up/move-down buttons or `Alt+Arrow`. | Yes |
| WF-UX-007-TH-010 | Empty states | SR-05 | Screen reader | Every empty state has a meaningful heading or `aria-label`. | Yes |
| WF-UX-007-TH-011 | Error states | SR-07, ER-03 | Screen reader + keyboard | Errors announced via `aria-live`. Focus moves to error. Recovery action focusable. | Yes |
| WF-UX-007-TH-012 | Color tokens | DS-02 | Automated (contrast scanner) | All text meets AA contrast ratios against its background. | Yes |
| WF-UX-007-TH-013 | Vertical text (JP) | VT-01, VT-02 | Visual regression | Layout intact with `writing-mode: vertical-rl`. | No (progressive) |
| WF-UX-007-TH-014 | Onboarding forms | KB-01, KB-07, L10N-04 | Keyboard + screen reader | All fields labeled. Focus managed. Date/time localized. | Yes |
| WF-UX-007-TH-015 | Evidence collection UI | KB-01, SR-07 | Keyboard + screen reader | Evidence upload/input is keyboard-accessible. Status announced. | Yes |

### 7.3 Harness Execution

| Rule | Description |
|------|-------------|
| HARNESS-01 | Automated checks run in CI on every PR (axe-core, visual regression). |
| HARNESS-02 | Manual checks (keyboard, screen reader) run on every release candidate. |
| HARNESS-03 | CJK and RTL checks run on every release candidate using localized test fixtures. |
| HARNESS-04 | A harness failure on a blocking criterion blocks the release. No exceptions. |
| HARNESS-05 | Harness results are recorded in the release checklist. |

---

## 8. Design System Governance

| Rule | Description |
|------|-------------|
| DSG-01 | New components require an accessibility review before merging to the component library. |
| DSG-02 | Color tokens are never overridden inline. All color usage goes through tokens. |
| DSG-03 | New decision types (beyond the 5 defined in [UX Architecture §3](ux-architecture.md#3-decision-semantics)) require a spec update before implementation. |
| DSG-04 | Component changes that affect focus management, ARIA roles, or keyboard behavior require a screen reader test before merging. |
| DSG-05 | The design system is versioned. Breaking changes follow semver. |

---

## 9. Cross-References

| Document | Section | Relevance |
|----------|---------|-----------|
| [UX Architecture](ux-architecture.md) | §3 Decision Semantics | Decision type visual treatments originate here. |
| [UX Architecture](ux-architecture.md) | §4 Progressive Disclosure | Disclosure levels drive the focus management rules. |
| [UX Architecture](ux-architecture.md) | §5 Authority and Freshness | Design tokens for authority statuses defined here. |
| [Critical Journeys](ux-critical-journeys.md) | §10 Accessibility Audit Path | Audit checklist references this spec. |
| [Authorization](../security/authorization.md) | §4 Separation of Duties | View-level permissions affect keyboard navigation. |
| [AI Governance](../security/ai-governance.md) | §2.4 Copilot UI Rules | Copilot UI treatment rules referenced in SR-03. |

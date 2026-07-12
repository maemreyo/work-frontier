---
Status: Active
Owner: Work Frontier team
Last reviewed: 2026-07-12
Source of truth: This file
Related requirements: WF-DOM-15
---

# TrackerConnection

**WF-DOM-15**: A TrackerConnection represents a live link between Work Frontier and an external tracker (GitHub Issues, Linear, Jira, etc.). It is the only point where tracker-specific knowledge enters the system.

## Purpose

TrackerConnections normalize tracker-specific APIs, status schemes, and relationship models into [WorkItem](work-item.md) snapshots with [authority status](authority-statuses.md) that the engine processes uniformly. Tracker-native statuses map into the five canonical [lifecycle](lifecycle-and-completion.md) states: `planned`, `active`, `completed`, `cancelled`, `unknown`.

## Structure

| Field | Type | Description |
|-------|------|-------------|
| `connection_id` | ULID | Unique identifier. |
| `tracker_type` | enum | `github`, `linear`, `jira`, `gitlab`, `custom`. |
| `tracker_url` | string | Base URL of the tracker instance. |
| `connection_name` | string | Human-readable name. |
| `status` | enum | `active`, `paused`, `error`, `disconnected`. |
| `sync_config` | SyncConfig | How and when this connection syncs. |
| `field_mapping` | FieldMapping | Maps tracker fields to WorkItem fields. |
| `status_mapping` | StatusMapping | Maps tracker-native statuses to canonical lifecycle states. |
| `created_at` | ISO 8601 | When established. |
| `last_sync_at` | ISO 8601 or null | Last successful sync. |
| `error_log` | list[SyncError] | Recent sync errors, capped at 100. |

## Sync Config

| Field | Type | Description |
|-------|------|-------------|
| `mode` | enum | `webhook`, `poll`, `both`. |
| `poll_interval_seconds` | int or null | For `poll` mode. Default 300. |
| `webhook_secret` | string or null | HMAC secret for signature verification. |
| `batch_size` | int | Max items per sync cycle. Default 50. |

## Status Mapping

The TrackerConnection includes a configurable status mapping that translates tracker-native statuses to canonical lifecycle states. The default mapping is defined in [Lifecycle and Completion](lifecycle-and-completion.md#normalization-rules). Operators can customize mappings per connection.

| Tracker status | Canonical lifecycle |
|---------------|-------------------|
| `open`, `todo`, `backlog`, `new` | `planned` |
| `in_progress`, `doing`, `blocked`, `in_review`, `claimed` | `active` |
| `done`, `closed`, `resolved`, `shipped` | `completed` |
| `cancelled`, `wontfix`, `invalid`, `duplicate` | `cancelled` |
| Unmapped or ambiguous | `unknown` |

## Field Mapping

| Tracker field | Maps to | Transform |
|--------------|---------|-----------|
| GitHub `title` | WorkItem `title` | Direct copy. |
| GitHub `body` | WorkItem `description` | Direct copy. |
| GitHub `labels[].name` | WorkItem `labels` | Direct copy. |
| GitHub `state` | WorkItem `lifecycle` | Via [status mapping](#status-mapping). |
| GitHub `assignee.login` | WorkItem `primary_owner` | User ID mapping. |
| GitHub `milestone.title` | WorkItem `program_ids` | Program membership mapping. |
| GitHub issue relationships | [Edges](edges.md) | `blocks` / `related_to` mapping. |

## Sync Protocol

### Inbound (Tracker to Work Frontier)

1. TrackerConnection receives a change event.
2. The adapter normalizes it into a WorkItem snapshot. Source level: `native tracker` for status fields, `structured metadata` for labels/milestones, `parsed Markdown` for relationship extraction from description.
3. Status fields map to canonical lifecycle states via the [status mapping](#status-mapping).
4. The snapshot is written with the appropriate [precedence level](authority-statuses.md#source-precedence).
5. The engine re-evaluates on the next cycle.

### Outbound (Work Frontier to Tracker)

The engine never pushes state changes directly. Outbound actions are proposals:

1. The engine or human proposes an action.
2. TrackerConnection translates to tracker-specific API calls.
3. The action is logged with provenance.
4. The tracker's response is captured as a new inbound snapshot.

## Authority Status of Tracker Data

Data from a TrackerConnection carries [authority status](authority-statuses.md) based on sync freshness:

| Condition | Authority status |
|-----------|-----------------|
| Fresh sync, no conflicts | `authoritative` |
| Pending sync events | `provisional` |
| `last_sync_at` older than threshold | `stale` |
| Multiple trackers disagree | `conflicted` |
| Tracker unreachable | `unavailable` |

When a TrackerConnection is stale or disconnected, the engine emits a `connection_degraded` [AttentionItem](attention-items.md).

## TrackerConnection and Edges

Tracker relationships are mapped to [Edges](edges.md) during sync:

| Tracker relationship | Edge type | Direction |
|---------------------|-----------|-----------|
| "blocks" / "is blocked by" | `blocks` | As reported. |
| "relates to" | `related_to` | Bidirectional. |
| Issue in epic/milestone | `contains` | Parent → child. |
| "requires" / "depends on" | `blocks` | As reported. |

When the tracker doesn't have a relationship concept, the adapter infers edges from structural containment.

---
name: anatomy-link
description: >-
  Inserts or updates a small, marked, idempotent block in agent-instruction
  files such as AGENTS.md and CLAUDE.md that points coding agents at an
  existing `anatomy` skill output. Use when the user asks to link, wire up,
  connect, or hook anatomy docs into agent instructions so future sessions
  discover the architecture trace before re-deriving it from source. It
  touches only content between its own markers. Not for generating or
  refreshing architecture documentation; use `anatomy` for that.
---

# Anatomy Link

## Purpose

`anatomy` writes architecture documentation, but a future coding-agent
session only benefits if it knows those files exist. This skill inserts a
short pointer block into agent-read files while preserving every byte
outside its own markers:

```text
<!-- anatomy:start -->
...
<!-- anatomy:end -->
```

Re-running it is idempotent. Existing blocks are updated; absent blocks are
inserted once; unrelated human-written content remains untouched.

## Workflow

Confirm that the chosen anatomy output contains `index.md`, then run:

```bash
python3 scripts/link.py <repo_root> \
  [--anatomy-root docs/anatomy] \
  [--targets AGENTS.md CLAUDE.md] \
  [--create] [--check]
```

- `--anatomy-root` is relative to the repository root and supports custom
  trace locations.
- Default targets are `AGENTS.md` and `CLAUDE.md`.
- Missing targets are skipped unless `--create` is explicitly supplied.
- `--check` reports intended changes without writing.

The block links only to outputs that actually exist, includes manifest
commit freshness when available, and describes `entry-points.md` as a
confirmed inventory with any grouped coverage disclosed. It does not claim
that heuristic scanning proves every possible framework-generated entry
point.

Report which files were updated, created, skipped, or already current.

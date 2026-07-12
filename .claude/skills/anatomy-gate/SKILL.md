---
name: anatomy-gate
description: >-
  Runs a pass/fail staleness check of an existing docs/anatomy/ output
  (written by the `anatomy` skill) against the current source tree, with
  severity ranked by how central each stale module is. Use for pre-commit
  hooks, CI checks on a pull request, or whenever the user asks whether
  docs/anatomy is stale, out of date, or needs a re-trace before merging --
  as a quick check, not a full re-trace. Triggers on requests to "check if
  the architecture docs are stale," "add a CI/pre-commit check for
  docs/anatomy," "gate this PR on docs freshness," or similar. Does not
  write or update any documentation itself -- for that, use the `anatomy`
  skill. Requires a prior `anatomy` run (a `_manifest.json` and
  `_modules.json` already sitting in the output folder); if neither
  exists, say so and point at the `anatomy` skill instead of guessing.
---

# Anatomy Gate

## Why this is a separate skill

`anatomy` itself already computes a hash-modules + diff every time it
runs (Phase 0, for deciding full vs incremental scope). That's built for
a human reading context before a re-trace. A gate that runs on every
commit or pull request needs a hard pass/fail result with an exit code,
without loading anatomy's full tracing workflow merely to answer whether
the existing documentation is stale. This skill provides that check.

## What it does

`scripts/docs_gate.py` re-hashes each module using the same file-selection
and content-hash contract as `anatomy/scripts/state.py`, vendored in
`scripts/_state_lite.py` so this skill remains independently installable.
It diffs the result against `_manifest.json`, then cross-references stale
modules against `_graph.json` health signals to rank severity.

It also reuses the manifest's persisted scan policy, including the actual
custom output root, and treats unreadable-file or hashing failures as
high-severity **unknown state** rather than passing or manufacturing a
stable pseudo-hash.

Severity policy:

- **high** -- a removed or newly added module; a changed most-connected
  module; an unreadable/hash error; or a scan-policy mismatch that makes
  freshness unverifiable.
- **medium** -- a changed module not otherwise classified, or degraded
  classification when `_graph.json` is unavailable.
- **low** -- a changed module currently listed as an orphan candidate.

This ranking keeps the gate useful in daily work: central or unknown-state
failures should be loud, while low-blast-radius drift can remain advisory
unless the user explicitly chooses a stricter threshold.

## Running it

```bash
python3 scripts/docs_gate.py <output_root> [--repo-root PATH] \
  [--fail-on {high,medium,low,none}] [--format {json,text}]
```

- `<output_root>` is `docs/anatomy/` or the exact custom output directory
  used by the previous trace.
- `--repo-root` defaults to the current working directory. Pass it
  explicitly when invoked elsewhere.
- `--fail-on` defaults to `high`. `none` is report-only and always exits 0
  unless setup itself is invalid.
- `--format text` provides concise local output; JSON is the default for CI.

Exit codes:

- `0` -- pass at the selected threshold.
- `1` -- stale or unknown findings meet the selected threshold.
- `2` -- setup or input error, including missing/malformed state files.

Report both the exit code and the returned `status`; never paraphrase a
failure or unknown state as current documentation.

## Setting this up as a hook or CI check

For a local pre-commit hook:

```bash
python3 <path-to-skill>/scripts/docs_gate.py docs/anatomy --format text
```

For a pull-request check, run the same command from the repository root
with JSON output. Start with `--fail-on high`; teams can tighten it after
observing the noise level. Do not silently default to medium or low.

Do not create or edit hook/CI configuration unless the user explicitly
asks. The command and its policy are the primary deliverable.

## Deliberately coarse content hashing

A comment-only or whitespace-only edit still counts as a source change.
The skill does not try to filter such changes with a heuristic. Avoiding a
small false-positive cost is not worth introducing false negatives into a
documentation-staleness gate.

## Relationship to the other anatomy skills

- `anatomy` creates and refreshes the trace and writes the versioned
  manifest plus scan policy.
- `anatomy-ask` uses the same freshness contract to decide whether a narrow
  read-only answer can safely rely on an existing trace.
- `anatomy-drift-watch` compares `_graph.json` snapshots across runs for
  structural drift; it does not check source-vs-document freshness.

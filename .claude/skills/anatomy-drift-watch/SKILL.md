---
name: anatomy-drift-watch
description: >-
  Compares the current docs/anatomy/_graph.json against the last archived
  snapshot to detect architectural drift since the previous anatomy run --
  new dependency cycles, new orphan modules, and modules whose
  most-connected rank jumped sharply -- and nudges toward writing a short
  ADR when it finds something worth a deliberate decision. Use right
  after an `anatomy` re-trace finishes (full or incremental), or whenever
  the user asks "did the architecture shift since last time," "did that
  refactor change what's central to this system," or "should we write an
  ADR for this." Not for a first-ever trace (there's nothing to compare
  against yet -- it just establishes a baseline) and not for checking
  whether docs are stale relative to source (that's `anatomy-gate`).
---

# Anatomy Drift Watch

## Why this is a separate skill, and why it needs a new script

Unlike `anatomy-gate` and `anatomy-ask`, this one can't be built purely by
re-reading `_manifest.json`/`_graph.json` as they exist right now:
`graph_export.py`/`rollup.py` only ever look at the *current* state of the
graph, with no concept of "compared to last time." Answering "did the
architecture shift" requires an *old* snapshot to diff against -- and
because `anatomy`'s own Phase 5 overwrites `_graph.json` in place every
run, that old snapshot is gone by the time this skill would normally be
invoked (right after an `anatomy` run finishes). `anatomy` itself is
meant to stay as-is (see the parent `anatomy` skill), so this skill keeps
its **own** rolling archive instead of asking `anatomy` to change its
write order:

- `scripts/graph_history.py` -- archives snapshots into
  `docs/anatomy/_graph_history/` and tells you which one is "latest"
  (the most recently archived snapshot, i.e. the one from the run before
  this one).
- `scripts/diff_health_signals.py` -- the actual comparison: new cycles,
  new/resolved orphan candidates, and `most_connected` rank movement
  between two `_graph.json`s.

As long as you call `latest` (to get the comparison point) **before**
`archive` (to record this run's result for next time), the two calls
bracket the same before/after comparison a pre-write backup would have
given -- just computed after the fact instead of before.

## Workflow

### 1. Confirm there's a current `_graph.json` to work from

This skill assumes an `anatomy` run (full or incremental) just finished,
so `<output_root>/_graph.json` reflects the current state. If it's stale
relative to source (a re-trace hasn't actually happened since a while
ago), that's a different problem -- `anatomy-gate` covers that; don't try
to solve it here.

### 2. Get the previous snapshot

```bash
python3 scripts/graph_history.py latest <output_root>
```

- **`latest` is `null`** -- no prior snapshot exists. This is either the
  first time this skill has run against this repo, or `_graph_history/`
  was deleted. There's nothing to diff against. Skip straight to step 4
  (archive the current snapshot as the baseline) and tell the user
  plainly: "no prior snapshot to compare -- this run establishes the
  baseline for future drift checks." Don't invent a comparison or guess.
- **`latest` is a path** -- continue to step 3.

### 3. Diff

```bash
python3 scripts/diff_health_signals.py <latest_path> <output_root>/_graph.json
```

Read the result's `drift_detected` field and the individual lists:

- `new_cycles` -- a dependency cycle that didn't exist in the previous
  snapshot. Always worth a look; not automatically a bug (see
  `anatomy/references/output-templates.md`'s own note that cycles can be
  intentional), but silent is the wrong default.
- `new_to_most_connected` -- a module that wasn't ranked in the previous
  snapshot's top-N and now is. Often the more interesting signal than a
  rank *jump* within the list, since it usually means something that used
  to be peripheral just became load-bearing.
- `rank_jumps` -- a module that was already ranked and moved by at least
  the threshold (default 3 positions; pass `--rank-jump-threshold` to
  adjust if the user wants a more/less sensitive check).
- `new_orphans` / `resolved_orphans` / `dropped_from_most_connected` /
  `resolved_cycles` -- reported for context. These don't set
  `drift_detected` on their own (they're generally "good news" or neutral
  findings), but mention them in your summary if they're part of the same
  story as something that did trigger drift.

If `drift_detected` is `false`, say so plainly and skip to step 5 --
don't manufacture an ADR nudge out of context-only findings.

### 4. If drift was detected, nudge toward an ADR -- don't write one unprompted

Draft the ADR content using `references/adr-template.md`, filling in the
`Trigger` line directly from the diff output (quote the actual finding,
don't paraphrase loosely) and a genuine `Assessment` based on actually
looking at what changed (open the relevant module doc(s) if you need to
understand *why* the rank moved or the cycle appeared, not just *that* it
did). Show the draft to the user before writing anything -- the
`Decision` field is a human judgment call (accepted as-is / needs
follow-up / reverted), not something to fill in unilaterally on the
user's behalf. Once they've confirmed or supplied the decision, write it
to `docs/anatomy/decisions/<date>-<slug>.md`.

If the same run surfaced more than one distinct finding (e.g. a new
cycle *and* an unrelated rank jump), draft a separate ADR per finding
unless the user's own explanation makes clear they're the same
underlying change.

### 5. Archive the current snapshot for next time

```bash
python3 scripts/graph_history.py archive <output_root> [--keep 30]
```

Do this last, after steps 2-4 have already used the previous snapshot --
archiving doesn't touch `_graph.json` itself, only adds a copy under
`_graph_history/`, so ordering here is about keeping the workflow
readable, not about correctness of the diff itself.

### 6. Report back

State plainly: whether this was a baseline run or a real comparison,
whether drift was detected and what kind, and whether an ADR was written
(and where) or the user declined/deferred. If nothing changed
architecturally, a one-line "no drift since the last trace" is a
complete and useful answer -- don't pad it out.

## Relationship to the other satellite skills

- `anatomy-gate` answers "are the docs stale relative to source right
  now" -- a source-vs-docs check. This skill answers "did the *shape* of
  the system change since the last trace" -- a graph-vs-graph check. A
  repo can have zero gate findings (docs perfectly fresh) and still show
  drift here (the fresh docs describe a genuinely different, newly
  central module than they used to).
- `anatomy-ask` doesn't use this skill's history at all -- it answers
  single questions from the current trace, not "what changed."

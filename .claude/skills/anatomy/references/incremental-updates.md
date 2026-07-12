# Handling a pre-existing output folder

This is Phase 0 of the workflow in SKILL.md, expanded. The goal: re-running
this skill on a codebase that's already been traced should be fast and
should only touch what actually changed, while still keeping `index.md`,
`system-diagram.md`/`.html`, and `entry-points.md` fully correct for the
_current_ state of the whole system -- not just the part that changed.

## The manifest

`docs/anatomy/_manifest.json` records what was traced and a content hash
per module:

```json
{
  "version": 2,
  "source_root": "/abs/path/at/trace/time",
  "scan_policy": {
    "version": 1,
    "gitignore_root": ".",
    "excludes": ["docs/anatomy", "docs/system-trace"],
    "unreadable_file_policy": "error"
  },
  "modules": {
    "api": { "hash": "sha256...", "file_count": 3 },
    "services": { "hash": "sha256...", "file_count": 5 }
  },
  "generated_at": "2026-07-09T12:34:56Z",
  "source_commit": "abc123... or null if not a git repo"
}
```

The hash is content-based (sha256 over every file in the module, produced by
`scripts/state.py hash-modules`) rather than relying on mtimes or git alone.
This matters because:

- Working trees have uncommitted changes constantly; git-commit-only
  comparison would miss them.
- Not every codebase is a git repo at all (vendored drops, extracted
  archives, a folder someone handed you).
- mtimes get touched by checkouts, CI, and editors without content actually
  changing, which would cause spurious "changed" flags.

`source_commit` is still recorded when available, purely as a friendly
reference point for the user ("last traced at commit abc123") -- never as
the sole basis for the diff decision.

`scan_policy` records the repository-root `.gitignore` basis, generated-output
exclusions, and unreadable-file behavior used for the hashes. This is essential
when a module maps to `.`: without excluding the actual output root, writing the
trace changes the module hash and every later run appears stale forever. The two
historical defaults are always excluded; a custom output root must be passed to
every scanner/hasher with `--output-root`. Version-1 manifests have no policy
field and are accepted once for migration; after a version-2 manifest exists, a
policy change is surfaced explicitly because the old and new hashes may not be
comparable.

Path information isn't in `_manifest.json` -- it's kept in a sibling file,
`docs/anatomy/_modules.json`, the persisted copy of Phase 2's slug ->
relative-path mapping (`{"api": "src/api", ...}`). Two consumers: Phase 2
on a later run, to reuse a still-valid path's existing slug instead of
inventing a new one (see SKILL.md's Phase 2); and `scripts/graph_export.py`,
to fill in each module's `path` field when it builds `_graph.json`. Written
at the *start* of Phase 5, before `graph_export.py` needs it -- earlier
than `_manifest.json`, which waits for Phase 6's fresh hashes -- every run,
full or incremental.

## Migrating from an older `docs/system-trace` output

Earlier versions of this skill defaulted to `docs/system-trace/` instead of
`docs/anatomy/`. If `docs/anatomy/_manifest.json` doesn't exist, check for
`docs/system-trace/_manifest.json` before concluding this is a clean first
run. If you find one there:

- Don't silently start a brand-new full trace into `docs/anatomy/` -- that
  leaves two documentation sets sitting in the same repo, with no signal to
  a future reader (or a future run of this skill) about which one is
  current, and doubles the drift-from-code problem this skill exists to
  prevent.
- Tell the user what you found and offer to migrate: `git mv
docs/system-trace docs/anatomy` (or a plain move if it's not a git repo),
  then proceed as an ordinary incremental update against the moved manifest.
  The manifest's content is location-independent (it's keyed by module
  hashes, not by its own path), so a straight rename is safe and loses
  nothing.
- If the user would rather keep the old location, that's fine -- just
  operate against `docs/system-trace/` for the rest of this run instead of
  defaulting to `docs/anatomy/`, and say so plainly in your summary so it's
  not a silent, easy-to-forget deviation from the default.

## Fast path: answering one specific question without a full run

The read-only fast path is implemented by the separate `anatomy-ask` skill.
Route narrow questions against an existing trace there instead of loading this
write-oriented workflow. `anatomy-ask` reads `_manifest.json` and
`_modules.json`, applies the same scan policy and module hashes, names the
trace's age, and refuses to present a changed/removed/unknown module as current.
If the request becomes "update the docs," return here and perform an ordinary
incremental update.

## Decision tree

**1. Does `docs/anatomy/_manifest.json` exist?**

- **No, and neither it nor a legacy `docs/system-trace/_manifest.json`
  exists** -> straightforward full trace. This is the common case for a
  first run.
- **No, but the folder exists with other content** (hand-written docs, or
  output from a version of this skill old enough to predate the manifest
  entirely) -> there's no reliable state to diff against. Do a full trace.
  Skim what's already there first though -- if it uses module names/slugs
  that make sense, reuse them for continuity rather than picking different
  ones. Mention in your summary to the user that no prior trace-state was
  found, so this was a full trace rather than an update.
- **Yes** -> continue to step 2.

**2. Get the current module list** (Phase 1/2 of the main workflow: run
`scripts/inventory.py`, decide module boundaries per
`references/module-detection.md`).

**3. Compute fresh hashes and diff:**

```bash
python3 scripts/state.py hash-modules <repo_root> <modules.json> --output-root <output_root> --with-policy > fresh_hashes.json
python3 scripts/state.py diff <old_manifest_path> fresh_hashes.json
```

This returns `unchanged`, `changed`, `added`, `removed`, hashing
`errors`, `scan_policy_changed`, and a `change_ratio` with a built-in
recommendation. Any hashing error means unknown state and aborts the update. A
policy change must be reviewed before treating old/new hashes as comparable.

**4. Decide the update scope:**

- **Nothing in changed/added/removed** -> the trace is already current.
  Still worth confirming this to the user rather than silently doing
  nothing -- e.g. "Checked for changes since the last trace (commit
  abc123) -- nothing has changed, docs/anatomy is up to date."
- **Some changed/added/removed, ratio comfortably below the ~60% line** ->
  incremental update:
  - Re-trace only the modules in `changed` and `added` (full Phase 3/4
    tracing for those specifically).
  - Delete `modules/<slug>.md` for anything in `removed`.
  - Leave `modules/<slug>.md` untouched for everything in `unchanged` --
    don't re-read or rewrite those files, other than the narrow
    edges-into-a-changed-module check below. This is the whole point of the
    manifest: it lets you skip real work, not just skip announcing it.
- **Ratio at or above ~60%, or the repo structure looks fundamentally
  reorganized** (e.g. most top-level directories are new) -> the diff
  itself will say so in its `recommendation` field. Don't silently pick a
  side here -- tell the user what the diff found and ask whether they want
  a full re-trace or to proceed incrementally anyway. A mostly-rewritten
  system is exactly the case where partial patching risks leaving the
  overall picture inconsistent.
- The user can always override either way by simply asking for a full
  re-trace, or by deleting `_manifest.json` themselves as a manual reset.

## Edges into a changed module

The hash diff only describes which module's own files changed. Two additional
steps keep relationships correct without re-tracing every unchanged module.

First, for each **outbound `Depends on` edge from an unchanged module into a
changed module**, reopen only the cited call site and confirm the relationship's
behavior, failure mode, and target are still accurate. Edit only that bullet if
needed. `Used by` is derived data; do not independently hand-maintain it during
this check.

Second, after changed/added docs are written and removed docs are deleted,
transpose the **complete current** `Depends on` graph:

```bash
python3 scripts/sync_reverse_edges.py <output_root> --write
python3 scripts/sync_reverse_edges.py <output_root> --check
```

This graph-wide pass covers the case the old existing-line rule missed: changed
module `B` can newly depend on unchanged module `A`, even though `A` has no old
`Used by B` line to revisit. The same pass adds that new reverse edge, removes
stale ones, mirrors confirmation markers/citations, preserves external bullets
and coverage footers, and reports internal targets with no current module doc.

## Regenerating the whole-system files

**Regenerate `index.md`, `entry-points.md`, `_entrypoint-scan.json`,
`_diagram-data.json`, both rendered diagram files, and `_graph.json`
unconditionally**, even in incremental mode. They describe the current full
system. `render_diagrams.py` creates both diagram formats from the canonical
JSON, while `_graph.json` is exported last from verified module/entry-point
output.

The part that isn't automatic: rebuilding these requires knowing every
current module's role, dependencies, and entry points -- including the ones
in `unchanged`, which Phase 4 didn't re-read this run. Get that information
by reading the _existing_ `modules/<slug>.md` file for each unchanged
module (updated already, if applicable, by the edges-into-a-changed-module
step above) rather than trying to recall it from earlier in a long
conversation, or re-deriving it from scratch, or -- worst case -- quietly
omitting unchanged modules from the new diagrams because they weren't
re-traced this run. An unchanged module still belongs in the full picture;
"unchanged" describes whether you re-verify it, not whether it exists.

**Write the updated manifest** with `scripts/state.py write`, including
fresh hashes for every current module and the `scan_policy` emitted by
`state.py hash-modules --with-policy`, so the next run can distinguish source
drift from a changed file-selection contract.
`_modules.json` (see "The manifest" section above) was already refreshed at
the start of Phase 5, so slugs stay stable across runs too -- nothing
further to do for it here.

## Reporting back to the user

Whatever the outcome, say plainly in your final summary which mode ran (full
vs incremental), which modules were re-traced vs left alone, what (if
anything) got removed, and whether any edges-into-a-changed-module check
turned up a stale "Depends on"/"Used by" line worth calling out. This is
short to write and it's the difference between the user trusting an "up to
date" claim versus wondering whether the skill actually looked.

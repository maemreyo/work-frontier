---
name: anatomy-ask
description: >-
  Answers a narrow, specific question about a codebase directly from an
  existing docs/anatomy/ output (written by the `anatomy` skill), without
  re-running any tracing. Use for questions like "where does X live,"
  "what would changing Y break," "which module handles the /orders
  route," or "is the payments module still coupled to billing" -- against
  a repo that's already been traced. This skill owns that read-only route;
  use it instead of loading `anatomy`'s full 7-Phase create/update workflow.
  If no `_manifest.json` exists yet at the expected output location, say
  so and point at the `anatomy` skill to produce one first -- don't
  attempt to trace anything from this skill. Not for requests to
  create, refresh, or update the documentation itself, and not for
  questions about a codebase that has never been traced.
---

# Anatomy Ask

## What this is, and isn't

The main `anatomy` skill delegates this read-only route here. This skill
exists so a quick question doesn't pull the full 7-Phase write workflow
description into context, or tempt a re-trace when a read is all that's
needed. If the person's request turns into "okay, now update the docs for
that," that's the cue to hand off to the `anatomy` skill for an
incremental update -- this skill only reads, never writes.

## Workflow

### 1. Locate the output

Default to `docs/anatomy/` unless the user names a different path. Check
for `_manifest.json` there.
Pass that exact output path to `freshness_check.py`; the persisted scan
policy ensures a root module does not hash the generated trace itself.


- **Not found** -- check `docs/system-trace/_manifest.json` too (the
  older default location `anatomy` used to write to, in case this repo
  was traced by an older version of that skill). If neither exists, tell
  the user plainly: no existing trace to answer from, and point them at
  the `anatomy` skill to produce one. Don't try to answer from a cold
  read of the source yourself -- that's a different, much larger task
  than this skill is scoped for.
- **Found** -- continue.

### 2. Map the question to a module (or modules)

Read `index.md`'s module table first -- it's short and gives you the
slug -> responsibility -> doc-file mapping in one place. For a
route/CLI-command/queue-consumer question, check `entry-points.md`
instead (or in addition), since that's the file organized by entry point
rather than by module.

If the question doesn't map cleanly onto anything in the trace (a
brand-new area of the codebase, a question about something the trace
never covered), that's a signal this fast path doesn't apply -- say so
and suggest an `anatomy` incremental update instead of guessing.

### 3. Check freshness before answering

Never answer from a `docs/anatomy/` output without checking whether it's
current -- a confident answer from stale docs is worse than saying
"I'm not sure." Run:

```bash
python3 scripts/freshness_check.py <output_root> --repo-root <repo_root> --module <slug>
```

(Omit `--module` if the question spans more than one module -- run it once
per relevant slug, or once with no `--module` to just get the repo-wide
diff if that's easier for the case at hand.)

Read `module_status` and `caveat` from the result:

- `unchanged` (repo-wide `change_ratio` is `0.0`, or this specific module
  is in `unchanged` even if other modules changed) -- answer directly.
  If `change_ratio > 0`, the script's `caveat` field already has the
  right "some other modules changed, this one hasn't" wording -- include
  it, don't imply the whole repo is fresh when only this slice is.
- `changed` or `added` -- the fast path doesn't apply for this module.
  Don't answer confidently from a doc that's known-stale. Tell the user
  the relevant module has changed since the last trace and offer either
  a best-effort answer clearly flagged as possibly outdated (using the
  script's `caveat` text) or an `anatomy` incremental update to get a
  reliable answer.
- `removed` -- the module's doc still exists but its source doesn't
  anymore. Say so plainly rather than answering as if it's live code.
- `not_found` -- the slug didn't match anything; re-check step 2's
  mapping rather than guessing at a doc file.

### 4. Answer from the existing docs

Once freshness is confirmed (or the user has accepted a flagged
best-effort answer), read `index.md` plus the specific
`modules/<slug>.md` file(s) -- and `entry-points.md` if the question was
about a route/command/consumer/cron job. Answer directly, citing the
same `path:line` citations already sitting in the module doc's "Depends
on"/"Used by"/"Public interface" lines rather than re-deriving them.
Keep the answer scoped to what was actually asked -- this skill is for a
quick, specific answer, not a rewrite of the module doc into prose.

### 5. Always name the trace's age

Every answer should make clear how current the information is -- e.g.
"as of the last anatomy run (commit `abc123`, <date>)" -- pulled from
`_manifest.json`'s `generated_at`/`source_commit` fields (also returned
by `freshness_check.py`). This is cheap to include and is the difference
between the user trusting the answer and having to double-check it
themselves.

## Relationship to the other satellite skills

`anatomy-gate` does the same underlying freshness check (each skill
vendors its own copy of the hashing logic in `scripts/_state_lite.py`,
so neither depends on locating the other's install path) but for a
different purpose: a hard pass/fail gate over the whole repo, not a
caveat on one answer. If the user's actual need is "block a PR until
docs are current" rather than "answer my question now," point them at
`anatomy-gate` instead.

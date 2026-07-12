# P2 -- trigger eval notes

## The bug this found

Before writing any eval queries, `quick_validate.py` was run against the
skill as it stood (SKILL.md description had grown across two rounds of P1
edits -- health signals, architecture narrative, CI config, the
docs/system-trace migration clause, the fast-path clause). Result:

```
Description is too long (2106 characters). Maximum is 1024 characters.
```

This is a hard spec limit (`quick_validate.py` line ~125), not a soft
"prefer shorter" guideline -- a description over 1024 characters fails
validation outright. This was the actual highest-priority P2 finding: no
amount of eval-query tuning matters if the description doesn't load in the
first place. The description has been rewritten from scratch at **998
characters** (`python quick_validate.py <skill-path>` now prints `Skill is
valid!`), keeping every phrase that the reasoning pass below identified as
load-bearing for a specific eval query, and cutting everything else
(exhaustive output-file itemization, restated framing sentences) since that
detail already lives in the body's "Output contract" section, which loads
once the skill is actually invoked.

## What's in `trigger-eval.json`

20 queries in skill-creator's eval schema (`query` / `should_trigger`), plus
a `note` field per entry recording the reasoning -- not part of the schema
`run_loop.py` expects, so strip that field (or leave it; extra JSON keys are
harmless, `run_loop.py` only reads `query`/`should_trigger`) before a real
run if you want a clean diff against its own output.

10 should-trigger, 10 should-not-trigger, built per skill-creator's own
guidance (`references/schemas.md` doesn't cover this eval type --
description optimization's step 1 in skill-creator's SKILL.md does):
concrete/specific rather than abstract, mixed formality and length, two
queries lifted directly from the risks flagged before starting this pass
(a Vietnamese single-function explain as the over-trigger risk, an Express
architecture-diagram request as the under-trigger risk), and the rest
chosen as genuine near-misses rather than easy negatives -- sharing a
keyword or concept with the skill (`diagram`, `trace`, `circular
dependency`, `monorepo`, `orphan module`) while actually needing something
else.

The former narrow read-only impact question was moved out of this set.
`anatomy` now owns create/refresh/migrate/re-trace work; `anatomy-ask` owns
questions answered from an existing trace. The positive slot remains an
incremental documentation-refresh request, while `anatomy-ask/evals/` carries
the routing regression for the read-only question.

## What this pass could and couldn't do

This environment can't run `skill-creator`'s `run_loop.py` -- it shells out
to the Claude Code SDK to actually execute each query against a live model
and check whether the skill gets consulted, which needs Claude Code, not
claude.ai. What's here instead is a manual reasoning pass: each query was
checked by hand against the description's literal text (does a phrase in
the query map to a phrase in the description, and is that mapping the
*right* call). That's a reasonable proxy but not a substitute for actually
running it -- the real test is what a model does, not what a human predicts
it'll do.

Two queries are flagged in their `note` as worth specifically watching in a
real run, because the by-hand reasoning was genuinely uncertain rather than
confident:

- **#10** (Word-doc onboarding request) -- competes with the `docx` skill
  on the word "Word doc." Predicted should_trigger: true (there's nothing
  for `docx` to format until this skill's tracing happens), but this is
  exactly the kind of multi-skill composition case that's hard to reason
  about statically.
- **#15** (CI pipeline diagram for a README) -- shares "diagram" and a CI
  reference with the description, but is a build-process diagram, not a
  module/service diagram. Predicted should_trigger: false, moderate
  confidence.

## Running the real loop later, in Claude Code

```bash
cd /path/to/skill-creator
python -m scripts.run_loop \
  --eval-set /path/to/anatomy/evals/trigger-eval.json \
  --skill-path /path/to/anatomy \
  --model <model-id-powering-the-session> \
  --max-iterations 5 \
  --verbose
```

This splits the set 60/40 train/test, runs each query 3x for a reliable
trigger rate, and iterates on the description up to 5 times, picking the
best version by held-out test score. If it proposes a shorter or
differently-worded description, re-run `quick_validate.py` on the result
before adopting it -- there's no guarantee an automated rewrite stays under
the 1024-character limit either.

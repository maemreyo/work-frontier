# ADR template for a drift-watch finding

Write to `docs/anatomy/decisions/<date>-<slug>.md`, one file per finding
(or per closely-related group of findings from the same run -- don't
split "new cycle involving A, B, C" and "A jumped to #1" into two files
if they're actually the same underlying change).

`<date>` is `YYYY-MM-DD`. `<slug>` is a short kebab-case description of
the finding (e.g. `2026-07-10-legacy-module-central`,
`2026-07-10-new-cycle-services-db-api`).

```markdown
# <date>: <short title>

**Trigger:** <what diff_health_signals.py actually found -- one of:
  - "`<module>` entered most_connected at rank <N> (degree <D>), wasn't
    ranked in the prior snapshot (<old_generated_at>)"
  - "`<module>` moved from rank <old> to rank <new> in most_connected
    (degree <old_degree> -> <new_degree>)"
  - "New dependency cycle: `<a>` -> `<b>` -> ... -> `<a>`"
  - "`<module>` is no longer an orphan candidate -- something now depends
    on it" (only worth an ADR if this is surprising, not routine)
  Quote the actual finding from the script's JSON output, don't
  paraphrase loosely -- the point of this line is a precise record.>

**Assessment:** <2-3 sentences, written after actually looking at what
changed -- not just restating the trigger. Is this expected given recent
work (a deliberate refactor, a new integration)? Is it a sign a module
boundary needs to be reconsidered? Is the new cycle intentional
(bidirectional event pub/sub, a shared registry -- see
anatomy/references/output-templates.md's own note that a cycle isn't
automatically a bug) or does it want breaking?>

**Decision:** <one of, plus 1 sentence of reasoning:
  - "Accepted as-is -- <why>"
  - "Needs follow-up -- <link to an issue/ticket if one exists, or a
    concrete next step if not yet filed>"
  - "Reverted -- <what change undid it, and where>"
  This is a human judgment call. If the person hasn't given you enough to
  fill this in confidently, leave it as a clearly-marked open question
  rather than picking one on their behalf.>
```

Keep it to roughly this length -- 2-3 lines per section. An ADR that
turns into a full incident writeup belongs somewhere else (a postmortem
doc, a linked issue); this file's job is to be a fast, permanent,
searchable record of "we saw this, here's the call," not the full
analysis.

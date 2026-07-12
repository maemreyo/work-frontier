# CLAUDE.md

`AGENTS.md` is the canonical repository instruction set. Read and follow it before changing code.

## Claude-specific workflow

1. Inspect the active todo and source before proposing edits.
2. Use repository skills under `.agents/skills/` when applicable; follow each skill’s own output
   contract.
3. Prefer small, reviewable patches and repository `make` targets.
4. Keep a running checklist for multi-file work, but do not substitute a checklist for executable
   verification.
5. Before finishing, inspect the complete diff and report the exact commands run.

## Repository reminders

- Current executable scope is the foundation toolchain, not the full target product.
- Do not hand-edit generated contracts or harness registry output.
- Do not weaken preflight, architecture, strict typing, mutation fixtures, or evidence validation to
  obtain a pass.
- Never claim a todo, harness, or certification state without evidence for the exact subject
  revision.
- Local and CI golden paths are documented in `docs/development.md`.

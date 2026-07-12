# Tracing methodology: verify, don't summarize docs

This is the part of the skill that matters most. It's easy to produce
something that _looks_ like a system trace by paraphrasing the README and
skimming file names. That is not what this skill is for, and it's actively
worse than no documentation, because it looks authoritative while carrying
forward whatever's already stale or wrong.

## The rule

Existing README files, docstrings, code comments, and any prior
`docs/anatomy` output are **claims to verify, not facts to report.**
Before a sentence goes into a module doc, it should pass this test: _did I
just confirm this by reading the function body / route table / schema
myself, or am I repeating something a comment or README said?_ If it's the
second one, go open the actual code before writing the sentence.

This isn't paranoia for its own sake -- comments and READMEs drift from
reality constantly (the feature described was changed, the TODO was finished
two years ago and never removed, the docstring was copy-pasted from a
similar-but-different function). Code doesn't drift from itself. It's always
telling the truth about what it currently does, even when that truth is
messy.

**When docs and code disagree, the code wins -- and say so.** Add a line to
that module's "Notes / discrepancies" section describing what the old docs
claimed versus what the code actually does. This is often the single most
useful thing the output tells the user: it's the reason "trace the real
thing" beats "summarize what's already written."

## Reading order per module

Working in this order avoids both missing things and wasting effort:

1. **Public surface first.** Exported functions/classes, route or controller
   definitions, registered CLI commands, event/message handler
   registrations. This is what the module promises to the rest of the
   system -- everything else is implementation detail in service of this
   surface.
2. **Trace inward from each public entry point.** Read far enough into the
   function body to know what it actually does: what it calls (helpers,
   other modules, external services, the database, the filesystem, the
   network), what it returns, what side effects and error paths it has.
   Don't stop at the signature.
3. **Check hypothesized edges against reality.** `scripts/import_graph.py`
   told you module A imports module B -- now open the call site in A and
   read what it's actually used for. `import db_client` and then calling
   `db_client.execute()` on every request is a very different relationship
   from importing a single shared constant. Describe the real relationship
   in the module doc ("calls X's `save()` on every write to persist orders"),
   not just the fact that an edge exists.
4. **Note configuration and environment dependence.** Env vars read, config
   files loaded, feature flags checked -- these often explain _why_ a module
   behaves differently across environments, which is exactly the kind of
   thing that's easy to get wrong from docs alone.
5. **Tests are excellent evidence, not a replacement for reading the code.**
   A module's test file is often the fastest way to confirm a real behavior
   or an edge case (what happens on empty input, what error is raised and
   when). Use it to corroborate what you read in the implementation, and
   flag it if a test's assumptions don't match what the implementation
   actually does.
6. **`Used by` is derived from the complete current `Depends on` graph, not from reading the target module.** Confirm outbound relationships while tracing each caller. After all changed/added docs are written, removed docs are deleted, and narrow outbound edges from unchanged modules into changed modules have been revalidated, run `scripts/sync_reverse_edges.py <output_root> --write` followed by `--check`. The script transposes every current internal edge, including newly created edges into unchanged modules, while preserving external bullets, prose, later sections, and coverage footers. Never infer "who uses me" from the callee's own files, and never update only reverse lines that already happened to exist.

## Choosing a trace depth: deep vs quick-scan

Everything above describes **deep mode**, the default: every module gets
Phase 4's full discipline, every edge gets individually confirmed before it
goes in a doc or diagram, and the only concession to scale is _reading
order_ (prioritize by traffic/size) -- not skipping verification of
anything that ends up in the output.

For a genuinely huge codebase, deep mode on every module can take a long
time, and earlier versions of this skill handled that by silently sampling
the smaller/less-referenced modules and noting it in a single footer
sentence -- a real behavior, but one the user had no way to opt into or out
of; it just happened. **Ask explicitly instead**, once you have a rough
sense of scale from Phase 1's `inventory.py` output (module count,
file/line totals) -- don't guess at the user's preference or default
silently to one mode for a large repo:

- **Deep** -- keep the discipline described everywhere else in this file.
  Every module traced, every edge confirmed, nothing marked "unconfirmed."
  Slower, but every claim in the output carries the same weight.
- **Quick-scan** -- trace hotspots (highest edge-count and largest-by-line
  modules, per `scripts/inventory.py`'s `largest_files_by_line_count` and
  `scripts/import_graph.py`'s edge counts) at full deep-mode discipline, and
  for the remainder: infer module role/edges from public
  signatures/route tables and the Phase 3 hypothesis scripts' output
  without opening every call site, marking every module and edge you didn't
  individually confirm as **unconfirmed** -- explicitly, in both the module
  doc and the diagram, not just implied by silence:
  - Module doc: add a one-line flag near the top, e.g. "**Coverage:**
    unconfirmed -- quick-scan mode; role/edges inferred from public
    signatures and Phase 3 hypotheses, not individually traced." Any
    "Depends on"/"Used by" line that's inferred rather than confirmed
    should say so inline rather than reading identically to a confirmed one
    -- e.g. "**`payments`** -- _unconfirmed_, hypothesized from
    `import_graph.py` edge count; not opened this run."
  - Diagram: use the dashed/dotted "unconfirmed" convention described in
    `references/output-templates.md`'s `system-diagram.md` and
    `system-diagram.html` sections -- a reader should be able to tell
    confirmed from unconfirmed at a glance, without opening every module
    doc to check.

  This is a different thing from the honest-sampling language elsewhere in
  this file ("sampled M of N files, see coverage note") -- that's still
  about _how much of one module's own files_ got read. Quick-scan mode is
  about _which modules_ get full Phase 4 treatment at all versus inference
  from signatures and hypotheses. The two compose: a hotspot module traced
  in quick-scan mode still follows the normal "sampled M of N" honesty
  about its own internals if it's also individually huge.

  Default to suggesting quick-scan only when the repo is large enough that
  deep mode would be noticeably slow (tens of modules, hundreds of files) --
  for anything smaller, deep mode is the better default and there's no need
  to ask. When you do ask, state the tradeoff plainly rather than a bare
  "deep or quick?": quick-scan trades completeness for speed, and every
  unconfirmed edge is a real gap in the output's trustworthiness, not a
  cosmetic footnote.

  The user can always ask to upgrade specific unconfirmed modules to deep
  mode later, including in a subsequent incremental run -- an "unconfirmed"
  module isn't in the manifest's `changed`/`added`/`unchanged` sense at all
  (its hash is real, its _trace depth_ is what's provisional), so re-running
  deep mode against it later is just an ordinary re-trace of that module.

## Scaling to large codebases

Reading every line of a 500-file module by hand doesn't scale, and this
skill would rather you trace 20 modules honestly at appropriate depth than
claim false completeness over all of them. This section is about _reading
strategy within a module you're tracing at full (deep-mode) discipline_ --
see "Choosing a trace depth" above for the separate, coarser decision of
whether every module gets that treatment at all. Some ways to scale within
a module:

- **Prioritize by traffic, not by alphabetical order.** Use
  `scripts/import_graph.py --group-by-top-level`'s edge counts and
  `scripts/inventory.py`'s `largest_files_by_line_count` to find the files
  that are heavily referenced or unusually large -- read those in full first.
  Rarely-referenced leaf files can be skimmed (signature + docstring + a
  representative chunk of the body) unless skimming reveals they're more
  central than the heuristic suggested.
- **Use grep to jump straight to definitions and call sites** (e.g.
  `grep -rn "def handle_payment" .` or `grep -rn "PaymentGateway(" .`) rather
  than reading files top to bottom in sequence. `rg` (ripgrep) if it's
  installed, plain `grep -rn` otherwise -- both work fine for this.
- **State your confidence and coverage honestly.** It's fine for a module doc
  to say "this module has 40 files; the following N were read in depth
  because they were the most-referenced or largest; the remainder follow the
  same repository/handler pattern based on a sample of 5." That's an honest,
  useful claim. Don't imply exhaustive coverage you didn't actually do.
- **A module that's too big to trace at once can be split** into a couple of
  sub-module docs (see module-detection.md's sizing guidance) rather than
  either skipping it or writing something too shallow to be useful.

## Wiring that's resolved at runtime, not at import time

`scripts/import_graph.py` and `scripts/external_calls.py` both work by
pattern-matching static text -- an import statement, a decorator, a client
call. Some real edges never appear as static text anywhere: a dependency-
injection container that wires implementations to interfaces at startup, a
plugin registry that loads whatever's dropped into a directory, Python's
`importlib.import_module(some_variable)` with a name built at runtime, Java
`@Autowired` fields, a service locator, a config-driven "which handler runs"
switch. No amount of regex sophistication fixes this category -- it's not a
gap in the scripts' pattern lists, it's a fundamental limit of reading text
without running it.

The risk isn't that you'll never find these -- reading a module's actual
code will usually surface them. The risk is _silently_ missing one and
having no record that you were even looking: unlike a hypothesis edge from
Phase 3 that you either confirm or correct, a runtime-wired edge with no
static trace doesn't prompt you to go check anything. So treat "does this
module use DI, a plugin/registry pattern, or reflection-based loading?" as
an active question to ask while reading, not something you'll stumble into.
Signs to watch for: a constructor or config that takes an interface/abstract
type rather than a concrete one, a directory that's scanned/globbed for
plugins at startup, a string-keyed dispatch table, an ORM or framework
that's known for heavy DI (Spring, Angular, NestJS, ASP.NET Core all
default to it).

When you find one, write it up explicitly rather than describing it the
same way as an ordinary call -- e.g. "**`payment-plugins`** -- resolved at
runtime via the plugin registry in `plugins/registry.py`; not visible to
static analysis, confirmed by reading the registration call, not an import."
That sentence itself is valuable: it tells a future reader (and a future run
of this skill, which will hash-diff `plugins/registry.py` but has no way to
know it should re-check every plugin module when that file changes) that
this edge needs a human's attention if the registry logic ever moves.

## When static reading isn't enough

Everything above is static analysis: reading source without running it,
which is what makes this skill safe to run against any codebase with no
setup and no side effects. Occasionally that's genuinely insufficient to
resolve a real ambiguity -- e.g. two plausible interpretations of a dynamic
dispatch that only diverge at runtime. If the user explicitly asks for
stronger verification ("run the test suite to confirm this," "trace what
actually happens on a real request"), that's a legitimate way to
corroborate what static reading found, and existing test suites in
particular are still safe, already-sanctioned code to execute. But this
should stay something the user opts into for a specific ambiguity, not a
default step -- running arbitrary code from an unfamiliar codebase has
side-effect and environment-setup implications this skill doesn't take on
by default, and it would compromise the "runs anywhere, read-only, no setup"
property that makes it usable on a codebase you've never touched before.

## What "how they interact" means concretely

The point of this skill isn't just a static dependency arrow between two
module names -- a real engineer wants to know the _nature_ of the
interaction. For every significant edge between modules, try to capture:

- **Direction and trigger**: who calls whom, and when (on every request?
  once at startup? on a schedule? in response to an event?).
- **Synchronous vs asynchronous**: a direct function call blocks; a published
  event or queued job doesn't -- this materially changes how a system
  behaves under failure.
- **What crosses the boundary**: which data/parameters go across, and what
  comes back (or doesn't, for fire-and-forget interactions).
- **Failure behavior**: what happens if the callee errors or is unavailable
  -- is it caught, retried, propagated, ignored?

This level of detail is what makes the sequence-diagram flows in
`system-diagram.md` (see `references/output-templates.md`) worth having,
instead of a diagram that just repeats the import graph with boxes and
arrows.

**Cite where you confirmed it.** Every "Depends on"/"Used by" line should
end with the file and line number of the call site you actually opened
(`src/services/order.py:88`) -- not only when something's wrong enough to
land in "Notes / discrepancies." A citation is what turns "trust me, I read
it" into something the next reader (or the next incremental run's
"edges into a changed module" check) can jump straight to and verify in
seconds instead of re-grepping the module from scratch. See
`references/output-templates.md`'s module-file template for the exact
placement.

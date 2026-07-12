# Output templates

Contents: [module file](#module-file-modulesslugmd) · [index.md](#indexmd) ·
[system-diagram.md](#system-diagrammd) · [entry-points.md](#entry-pointsmd) ·
[_diagram-data.json](#_diagram-datajson) ·
[data-model.md](#data-modelmd-conditional) ·
[deployment.md](#deploymentmd-conditional) ·
[system-diagram.html](#system-diagramhtml) ·
[_graph.json](#_graphjson) · [_modules.json](#_modulesjson)

Several kinds of file get written under the output root (default
`docs/anatomy/`, see SKILL.md for how that root is chosen):

```
docs/anatomy/
├── index.md              <- entry point, tech stack, table of modules, links out
├── system-diagram.md     <- Mermaid: optional system-context + module graph + flows
├── system-diagram.html   <- same content, standalone + interactive (see its own section below)
├── entry-points.md       <- confirmed route/CLI/consumer/cron inventory, grouping disclosed
├── data-model.md         <- ERD-style data model -- only if the project has a real datastore
├── deployment.md         <- deployment/infra topology -- only if compose/k8s manifests exist
├── modules/
│   ├── <module-slug>.md  <- one per module
│   └── ...
├── _diagram-data.json    <- canonical data rendered into system-diagram.md and .html
├── _entrypoint-scan.json <- reviewed source hypotheses from entrypoint_scan.py
├── _manifest.json        <- internal state for incremental updates (see
│                             references/incremental-updates.md). Not meant
│                             for humans to read, but it's plain JSON and
│                             plain-text if a human opens it. Mention in
│                             index.md that deleting it forces a full
│                             re-trace next time, as an escape hatch.
├── _modules.json         <- internal state: Phase 2's slug -> relative-path
│                             mapping, persisted verbatim (see "_modules.json"
│                             section below). Also internal, same
│                             not-for-humans-but-plain-JSON status as
│                             _manifest.json.
└── _graph.json           <- machine-readable snapshot of the whole module/
                              edge/entry-point graph, for another tool (or a
                              future/multi-repo run of this skill) to consume
                              without re-parsing Markdown (see "_graph.json"
                              section below and scripts/graph_export.py)
```

`data-model.md` and `deployment.md` are conditional -- see their own
sections below for exactly when to write them versus skip them.

Every file should link to the others it relates to: `index.md` links out to
all of them, module docs link to each other (via "Depends on"/"Used by") and
are linked from `system-diagram.md`/`.html`/`entry-points.md`, and
`data-model.md` entities link back to the module that owns them. Nothing in
`docs/anatomy/` should be a dead end -- if you're writing a fact in one file
that a reader would want to follow up on elsewhere, link it.

Use `scripts/_common.py`'s `stable_slug_map()` over the complete candidate
module set. It uses `slugify()` internally, then deterministically resolves
normalization collisions. Reuse `_modules.json` for paths that already have a
slug; filenames and graph join keys must not churn between runs.

## Module file: `modules/<slug>.md`

```markdown
# Module: <Module Name>

**Path:** `<relative/path/from/repo/root>`
**Role:** <one sentence, in your own words, verified from code -- not copied from a comment>

## Public interface

<!-- Functions/classes/routes/CLI commands/event handlers this module exposes -->

- `functionOrClass(...)` -- what it does (confirmed by reading the implementation)
- `POST /api/x` -> handled by `name()` in `file.py` -- what it does

## Internal structure

<!-- Key files and what each is responsible for. Skip this section for
     single-file modules. -->

- `file_a.py` -- ...
- `file_b.py` -- ...

## Depends on

<!-- Other modules and external libraries this module actually calls into,
     with the real nature of the relationship -- not just "imports X".
     See tracing-methodology.md's "what interaction means concretely."
     Cite the call site (`path/to/file.py:line`) on every line here, not
     just on discrepancies -- see the citation note below.
     What scripts/rollup.py, scripts/verify_diagram.py, and
     scripts/graph_export.py all key on is the "**`module-slug`**" or
     "external:`name`" prefix at the start of the bullet -- keep that
     exact bold/backtick shape. The separator after it (shown below as
     an em dash, matching what these bullets actually get written with)
     isn't itself load-bearing; write it however reads naturally. -->

- **`other-module`** — calls `OtherModule.save()` on every write, synchronously; propagates its errors (`src/services/order.py:88`)
- external: `library-name` — used for Y (`src/services/payments.py:12`)

## Used by

<!-- Reverse dependency: who calls into this module, and for what. Cite the
     call site the same way as "Depends on" -- it's the same edge, just
     read from the other module's "Depends on" line when you transpose it
     (see SKILL.md's Phase 4/5 transition), so the citation carries over
     directly rather than needing to be re-found. -->

- **`caller-module`** — calls this on every incoming request to ... (`src/api/routes.py:44`)

## Data & side effects

- Reads/writes: <tables, files, caches>
- Network calls: <external services, and whether sync/async>
- Config/env vars read: <...>

## Notes / discrepancies vs existing docs

<!-- Omit this section entirely if there's nothing to flag. When there is,
     this is often the most valuable part of the file -- say plainly what
     the old docs/comments claimed and what the code actually does. -->

- README claims X; the code actually does Y (see `path/to/file.py:line`)

---

_Traced from source on <date>. Files examined in depth: <list, or "all N
files" for small modules, or "sampled M of N -- see coverage note above" for
large ones>._
```

Adapt section names/labels to fit the module's actual nature (a pure-data
`models` module may not need "Data & side effects"; a CLI tool's "Public
interface" should list commands, not routes). The goal is a document a new
engineer could read to understand the module without opening the code --
don't force sections that don't apply, but don't silently drop something
just because it's inconvenient to describe either.

**Cite a file:line on every "Depends on"/"Used by" entry, not only on
discrepancies.** Earlier drafts of this skill only asked for a citation in
the "Notes / discrepancies" section -- but an ordinary "Depends on" claim is
just as checkable a fact as a discrepancy, and a reader (or a future
incremental run doing the "edges into a changed module" check in
`references/incremental-updates.md`) benefits from being able to jump
straight to the call site instead of re-grepping for it. Append the
relative path and line number in parentheses at the end of the bullet, as
in the template above. If a single relationship is confirmed across several
call sites, cite the most representative one or two rather than every
occurrence -- the point is "here's where to look first," not an exhaustive
index.

If a "Depends on" or "Used by" edge is resolved at runtime rather than
visible as a static import -- a DI container, a plugin registry, dynamic
`importlib`/reflection loading -- say so explicitly rather than describing
it the same way as a normal call: e.g. "**`payment-plugins`** -- resolved at
runtime via the plugin registry in `plugins/registry.py`; not visible to
static analysis, confirmed by reading the registration call." This is the
one category of edge that `references/tracing-methodology.md` calls out
specifically, because it's the one a reader (and a future run of this
skill) can't rediscover just by grepping imports.

Every route, CLI command, queue consumer, and cron job listed under "Public
interface" is also a candidate row for the system-wide `entry-points.md` --
keep that in mind while writing this section so Phase 5's rollup can lift
these directly rather than needing you to re-derive them.

## `index.md`

```markdown
# System Trace: <Project Name>

<2-4 sentences: what the project does, primary language/stack -- written from
what you actually found, not copied from an existing README>

**Generated:** <date> · **Mode:** <full trace | incremental update> · **Source commit:** <hash, or "not a git repo">

## Tech stack & key dependencies

<Derived from scripts/inventory.py's manifest parsing (package.json,
pyproject.toml, go.mod, Cargo.toml, pom.xml, docker-compose.yml, etc.), but
only include a framework/library here if you actually confirmed it's used
somewhere in Phase 4 -- a dependency that's declared but never imported
doesn't belong in an accurate picture of the stack.>

- **Language(s):** <from the inventory language histogram>
- **Framework(s):** <e.g. "Express 4 (confirmed in `api`)">
- **Datastore(s):** <if any -- see data-model.md>
- **Message broker / queue:** <if any>
- **Key third-party libraries:** <3-8 that actually matter architecturally,
  not a full dependency dump>
- **Infra / deployment:** <Docker, docker-compose, k8s, serverless -- see
  deployment.md if written>

## Modules

| Module     | Responsibility               | Depends on                      | File                                       |
| ---------- | ---------------------------- | ------------------------------- | ------------------------------------------ |
| `api`      | HTTP layer, composition root | `services`                      | [modules/api.md](modules/api.md)           |
| `services` | Order business logic         | `models`, `db`, `notifications` | [modules/services.md](modules/services.md) |
| ...        | ...                          | ...                             | ...                                        |

## Entry points

- How to run: <command, verified against actual scripts/manifests>
- How to build/test: <command(s) -- prefer scripts/inventory.py's `ci_config`
  output when CI config was found, since that's what actually runs on every
  push, not just what's declared; fall back to package.json
  scripts/Makefile targets when there's no CI config, and say plainly which
  source this came from -- "per `.github/workflows/ci.yml`" reads
  differently than "per package.json scripts, unverified against CI">
- Composition root: `<path>` -- wires <modules> together
- Full inventory of every route/CLI command/consumer/cron job: [entry-points.md](entry-points.md)

## Architecture at a glance

See [system-diagram.md](system-diagram.md) (or
[system-diagram.html](system-diagram.html) for the interactive version) for
the full interaction diagram and key flows.
<If written:> [data-model.md](data-model.md) covers the data model.
<If written:> [deployment.md](deployment.md) covers deployment topology.

<3-6 sentences of prose, distinct from the tech-stack bullets and the module
table above: how the system is actually shaped and why, in your own words.
This is the "what would a senior engineer tell a new hire in five minutes at
a whiteboard" version -- the dominant architectural pattern (layered
monolith, event-driven microservices, plugin-based, etc.), the one or two
decisions that most explain the module boundaries you drew, where the real
complexity/risk concentrates (the most-connected module below, a gnarly
runtime-wired integration, a module with unusually wide "Used by"), and
anything surprising relative to what the project's own docs/README claim
about its own shape. Write this only after Phase 4/5's module docs and the
diagram exist -- it's a synthesis of what you found, not something to draft
speculatively beforehand.>

## Codebase health signals

<Derived by running `scripts/rollup.py <output_root>` after modules/\*.md are
written (same point in Phase 5 as `verify_diagram.py` and
`verify_entry_points.py`) -- don't hand-count any of this.>

**Most-connected modules** (by combined Depends-on + Used-by count):

1. `<module>` -- <N> connections
2. `<module>` -- <N> connections
   <3-10 rows from rollup.py's `most_connected`, most useful for a new reader
   deciding where to start.>

**Possible dead code / orphan modules:** <list from `orphan_candidates`, or
"none found." Frame as candidates, not verdicts -- e.g. "`legacy-importer`
has no confirmed Depends-on or Used-by edges; likely dead code, but could
also be a standalone entry point invoked outside this repo's own call
graph -- worth confirming with the team.">

**Dependency cycles:** <list from `cycles` as `A -> B -> ... -> A` chains,
or "none found." A cycle isn't automatically a problem (see rollup.py's own
note) -- say so, but still surface it; a reader deciding whether to split a
module benefits from knowing this exists.>

**Trace coverage:** <one or two sentences from `trace_coverage.counts` --
e.g. "18 of 22 modules were traced in full; 4 large modules were sampled
(see each module's own footer for exactly what was covered)." If
`unstated_modules` is non-empty, that's a gap in this run's own output, not
the codebase -- fix those modules' footer lines before finishing rather
than reporting the gap here.>

## How this was generated

This documentation was generated by tracing the actual source code, not by
summarizing existing README/comments. See individual module files' "Notes /
discrepancies" sections for anywhere the prior docs and the code disagreed.
`_manifest.json` in this folder tracks what was traced, so a future run of
this skill can update only what changed -- delete it if you ever want to
force a full re-trace instead. `_graph.json` in this folder is a
machine-readable snapshot of the same module/edge/entry-point graph, for
tooling that wants to consume it directly instead of parsing this Markdown.
```

## `system-diagram.md`

This file is generated by `scripts/render_diagrams.py` from
`_diagram-data.json`; do not author its Mermaid independently from the HTML
diagram. The template below describes the resulting shape and the semantic data
you must put into the canonical JSON.

Use Mermaid (renders natively in GitHub, GitLab, and most Markdown viewers).
Keep node IDs simple/slugified; put the human-readable module name as the
node label.

```markdown
# System Diagram: <Project Name>

## System context

<!-- Optional -- see criteria below. Omit this whole section (not just the
     diagram) for a small project or a library with no meaningful external
     surface. -->

\`\`\`mermaid
graph LR
user((End user)) --> sys[<Project Name>]
sys --> pay[Payment Gateway]
sys --> mail[Email Provider]
\`\`\`

## Module dependency graph

\`\`\`mermaid
graph TD
api[api] --> services[services]
services --> models[models]
services --> db[(db)]
services --> notifications[notifications]
\`\`\`

Modules: [api](modules/api.md) · [services](modules/services.md) ·
[models](modules/models.md) · [db](modules/db.md) ·
[notifications](modules/notifications.md)

## Key flows

### <Flow name, e.g. "Order shipped notification">

\`\`\`mermaid
sequenceDiagram
participant Client
participant api
participant services
participant db
participant notifications
Client->>api: POST /orders/:id/ship
api->>services: ship_order(id)
services->>db: save(order)
services->>notifications: notify_shipped(order)
notifications-->>services: (fire-and-forget)
services-->>api: order
api-->>Client: 200 OK
\`\`\`

Modules involved: [services](modules/services.md),
[db](modules/db.md), [notifications](modules/notifications.md)

### <Another key flow>

...
```

**When to include "System context":** this is a zoomed-out view borrowed
from the C4 model's "Context" layer -- just your system as a single box,
plus the actors and external systems it talks to, with zero internal module
detail. Include it when the project has a real external surface worth
orienting a reader to (end users, other internal systems, third-party
APIs/services it calls) -- typically anything beyond a small single-package
library. For a 30-40-module system, this is often the more useful "first
diagram" precisely because the full module graph below is a hairball at
that size; the context diagram gives a reader something legible before they
descend into it. Skip it outright for small projects or libraries with
nothing external to show -- an empty or trivial context diagram (just one
box, nothing around it) isn't worth the section.

Pick 2-6 "key flows" that represent the most important or most illustrative
things the system does end-to-end (a request lifecycle, a background job, a
startup sequence) -- not every possible call path. Each flow's participants
should be modules (or, when useful, specific external systems like "Database"
or "Payment Gateway"), not individual functions -- the module docs are where
function-level detail belongs.

Every edge and every flow in this file should be something you can trace
back to a specific place in a specific module doc. If a diagram edge has no
corresponding "Depends on" / "Used by" entry anywhere, that's a sign either
the diagram or the module doc is missing something -- reconcile them before
finishing. Don't rely on eyeballing this: `scripts/verify_diagram.py
<output_root>`, run once module docs and this file both exist, checks it
mechanically and lists exactly which edges don't have a corresponding
module-doc entry (see SKILL.md's Phase 5 for when to run it).

**Quick-scan mode only** (see `references/tracing-methodology.md`'s
"Choosing a trace depth"): a module or edge that wasn't individually
confirmed this run -- because quick-scan mode prioritized hotspots and left
the rest sampled/inferred -- gets marked visually rather than presented the
same as a confirmed one. Use Mermaid's dotted-line syntax (`-.->` instead of
`-->`) for an unconfirmed edge in the module dependency graph, and add
`:::unconfirmed` to an unconfirmed node's line with a
`classDef unconfirmed stroke-dasharray: 3 2` declared once near the top of
that diagram's code block. Don't use this convention in deep-mode output --
in deep mode every edge is confirmed by definition, so there should be
nothing to mark.

## `entry-points.md`

```markdown
# Entry Points: <Project Name>

Every confirmed route, CLI command, queue consumer, and cron/scheduled job
found by the trace, rolled up in one place from each module's `Public
interface`. Run `entrypoint_scan.py` as an independent source-hypothesis pass
and reconcile its hits before claiming coverage. Because framework registration
can be dynamic, describe this as a source-verified inventory, not as a formal
proof that an unrecognized framework exposes nothing else.

## HTTP routes

| Method | Path               | Module | Handler        | File                     |
| ------ | ------------------ | ------ | -------------- | ------------------------ |
| POST   | `/orders/:id/ship` | `api`  | `ship_order()` | [api.md](modules/api.md) |
| ...    | ...                | ...    | ...            | ...                      |

## CLI commands

| Command | Module | What it does                                     | File                     |
| ------- | ------ | ------------------------------------------------ | ------------------------ |
| `ship`  | `cli`  | Marks an order shipped and triggers notification | [cli.md](modules/cli.md) |

## Queue / event consumers

| Topic / event    | Module          | Triggered by                    | File                                         |
| ---------------- | --------------- | ------------------------------- | -------------------------------------------- |
| `orders.shipped` | `notifications` | Published by `services` on ship | [notifications.md](modules/notifications.md) |

## Scheduled / cron jobs

| Schedule    | Module    | What it does                  | File                             |
| ----------- | --------- | ----------------------------- | -------------------------------- |
| `0 2 * * *` | `reports` | Nightly reconciliation report | [reports.md](modules/reports.md) |
```

Omit any of the four sections entirely if the project genuinely has none of
that kind -- don't write empty tables just to keep the shape uniform.

Every row here should be traceable back to the module doc it was lifted
from, same discipline as `system-diagram.md`'s edges: `scripts/verify_entry_points.py
<output_root>`, run once module docs and this file both exist (same point
in Phase 5 as `verify_diagram.py`), checks this mechanically instead of
relying on an eyeballed cross-check -- see SKILL.md's Phase 5 for when to
run it.

For a large system where one category runs into the hundreds of
near-identical entries (dozens of CRUD routes following the same generated
pattern, for instance), it's fine to collapse the repetitive ones into a
single row with a count and a pointer to a representative sample --
`"38 routes under /api/v1/resources/* -- standard REST CRUD via the generic
resource controller, see api.md"` -- rather than listing all 38 individually.
State plainly that you did this. This is the same honesty-about-coverage
standard as sampling a large module in Phase 4: say what you covered versus
what you grouped, don't imply exhaustive detail you don't actually have.

`verify_entry_points.py` understands these explicit grouped rows and does not
require each representative row to contain every literal endpoint. Review
`_entrypoint-scan.json` too: confirm each hit, or mark a false positive with
`"disposition": "false_positive"` and a `review_note`; then run the verifier
with `--strict-source`. Rows not recognized by the scanner are reported for
review but are not automatically failures, because the scanner is not
exhaustive.

This file (along with `index.md`, `system-diagram.md`, and
`system-diagram.html`) is always regenerated in full regardless of mode --
see `references/incremental-updates.md` for how to carry forward the rows
belonging to unchanged modules without re-deriving them.

## `data-model.md` (conditional)

Write this file only if the project has a real datastore -- confirmed by
actual ORM models, migration files, a `schema.sql`, or module docs whose
"Data & side effects" sections name persistent tables/collections, not just
"reads a config file" or "writes to a log." Skip it outright otherwise; a
`data-model.md` that says "this project has no database" is not worth a
file.

```markdown
# Data Model: <Project Name>

\`\`\`mermaid
erDiagram
ORDER ||--o{ LINE_ITEM : contains
ORDER }o--|| CUSTOMER : belongs_to
\`\`\`

## Order

**Owned by:** [models](modules/models.md)

- `id`, `status`, `total`, ...
- Relations: belongs to `Customer`; has many `LineItem`

## Customer

**Owned by:** [models](modules/models.md)

- `id`, `email`, ...
```

Derive entities/fields/relations from the actual migrations/ORM
models/schema, not from a stale ERD image or wiki page if one exists --
same verify-from-source discipline as everything else this skill writes.
Only list fields that matter for understanding the shape of the data
(primary/foreign keys, anything referenced elsewhere in the docs) rather
than reproducing every column of a wide table. Link every entity back to
the module that owns/primarily touches it.

## `deployment.md` (conditional)

Write this file only if the project has container/orchestration manifests
to draw from -- a `docker-compose.yml`/`.yaml` (parsed structurally by
`scripts/inventory.py`), Dockerfiles, or Kubernetes manifests. Skip it
outright for a project with none of these (a bare script, a library, a
single-process app with no deployment config in the repo).

```markdown
# Deployment: <Project Name>

\`\`\`mermaid
graph LR
api[api service] --> db[(postgres)]
api --> redis[(redis)]
worker[worker service] --> redis
worker --> db
\`\`\`

## Services

| Service  | Module(s)                  | Ports       | Depends on    | File                     |
| -------- | -------------------------- | ----------- | ------------- | ------------------------ |
| `api`    | `api`                      | `8080:8080` | `db`, `redis` | [api.md](modules/api.md) |
| `worker` | `notifications`, `reports` | --          | `redis`, `db` | ...                      |
```

A deployable service and a code module aren't always the same thing -- one
container can bundle several modules, or one module's code can be split
across services (rare, but note it if so). If the project has Kubernetes
manifests in addition to (or instead of) `docker-compose.yml`,
`inventory.py` doesn't parse those structurally, but they're already
visible in the Phase 1 file tree -- read them directly (`kind: Deployment`/
`Service`/`Ingress`/`CronJob` are the ones worth pulling into this file) the
same way you'd read any other source file, rather than skipping this
section for lack of automated parsing.

## `system-diagram.html`

A standalone, interactive rendering of the same information in
`system-diagram.md`, built by filling in `assets/diagram-template.html` --
never improvised as new HTML/CSS/JS from scratch. Two reasons both formats
exist: Mermaid in `system-diagram.md` only renders as a diagram on
GitHub/GitLab and a handful of Markdown viewers that support it -- open the
same file in a plain text editor, paste it into Slack, or open it directly
in a browser, and it's just a fenced code block. The `.html` file has no
such dependency: it's fully self-contained (no CDN, no external fonts, no
network access required) and renders and is interactive in any browser the
moment it's opened. And because it's a fixed template rather than something
regenerated freehand each run, output stays visually consistent across
every codebase this skill ever runs against, rather than drifting in
quality run to run.

**Canonical render workflow:**

1. Write the following object to `<output_root>/_diagram-data.json`. It is the
   single source for both diagram formats, not an HTML-only payload. Validate
   that `modules[]` exactly matches `_modules.json`; omitting a module from both
   rendered outputs must be a hard error. Schema:

   ```json
   {
     "project_name": "Acme Order Service",
     "generated_at": "2026-07-10",
     "mode": "full trace",
     "source_commit": "abc123def4567890",
     "modules": [
       {
         "slug": "api",
         "name": "api",
         "role": "HTTP layer, composition root",
         "path": "src/api",
         "doc": "modules/api.md"
       }
     ],
     "edges": [
       {
         "from": "api",
         "to": "services",
         "label": "calls ship_order() synchronously",
         "kind": "sync"
       }
     ],
     "context": {
       "actors": ["End user"],
       "external_systems": ["Payment Gateway"],
       "edges": [
         { "from": "End user", "to": "Acme Order Service", "label": "HTTPS" }
       ]
     },
     "flows": [
       {
         "name": "Order shipped notification",
         "steps": [
           { "from": "Client", "to": "api", "label": "POST /orders/:id/ship" }
         ]
       }
     ],
     "data_model": {
       "entities": [
         { "name": "Order", "fields": ["id", "status"], "module": "models" }
       ],
       "relations": [
         { "from": "Order", "to": "Customer", "label": "belongs_to" }
       ]
     },
     "deployment": {
       "services": [
         {
           "name": "api",
           "module": "api",
           "ports": ["8080:8080"],
           "depends_on": ["db"]
         }
       ]
     }
   }
   ```

   `context`, `data_model`, and `deployment` should be `null` (not omitted,
   not an empty-but-present object) whenever you didn't write the
   corresponding `.md` file for this project -- the template uses their
   presence to decide which tabs to show, and a present-but-empty object
   will render an empty tab instead of hiding it. `edges[].kind` is
   `"sync"` unless you know otherwise; use `"async"` for fire-and-forget/
   event-driven/queued interactions, which the template renders as a dashed
   line instead of solid, matching `system-diagram.md`'s own sync/async
   convention.

   **Quick-scan mode only:** set `"confirmed": false` on a `modules[]` entry
   or `edges[]` entry that wasn't individually confirmed this run (see
   `references/tracing-methodology.md`'s "Choosing a trace depth"). The
   template renders these with a distinct dotted style and a legend entry,
   separate from the sync/async distinction -- same purpose as
   `system-diagram.md`'s `-.->`/`:::unconfirmed` convention, just in the
   JSON the HTML template consumes instead of Mermaid syntax. Omit the
   field entirely (don't write `"confirmed": true`) for anything that was
   confirmed normally -- that's the default and doesn't need stating. In
   deep mode, don't set this field on anything.

2. Render and validate with the skill scripts rather than performing ad-hoc string replacement:

   ```bash
   python3 scripts/render_diagrams.py <output_root>
   python3 scripts/render_diagrams.py <output_root> --check
   python3 scripts/verify_html.py <output_root>
   ```

   The renderer reads the real `assets/diagram-template.html`, requires exactly
   one data placeholder, escapes Mermaid labels and unsafe `</script>` content,
   and writes `system-diagram.md` plus `system-diagram.html` deterministically from the
   same validated object. `verify_html.py` decodes the embedded JSON and checks
   both files against the canonical input. It verifies parity/currentness; it
   does not execute browser JavaScript.

Don't add a new tab, remove the pan/zoom/search behavior, or otherwise
restructure the template's HTML/CSS/JS as part of a normal run -- the
template is meant to be filled in with data, not redesigned per project.
If a genuine improvement to the template itself would help future runs,
that's a change to make to `assets/diagram-template.html` in the skill
itself, not a one-off tweak to a single project's generated output.

## `_diagram-data.json`

The canonical, validated input for both diagram formats. It uses the schema in
the `system-diagram.html` section above. Keep the full current module set here,
including unchanged modules during incremental runs. `render_diagrams.py`
rejects duplicate/unsafe slugs, unknown edge targets, duplicate edges, unsafe
doc paths, malformed flows/context, and any mismatch with `_modules.json`.
This is generated state for reproducible rendering, but unlike the HTML it is
plain JSON and suitable for review.

## `_graph.json`

The machine-readable counterpart to everything else in `docs/anatomy/`.
Every other file is prose (or Mermaid/HTML) for a human to read;
`_graph.json` is the same module/edge/entry-point/health-signal information
as a single structured artifact another tool -- a CI freshness check, a
different repo's run of this skill doing multi-repo stitching, an
unrelated agent -- can consume without re-parsing five different Markdown
files by hand. Written by `scripts/graph_export.py <output_root> --source-root <repo_root> --write` at the end of
Phase 5, after `modules/*.md`, `entry-points.md`, `verify_diagram.py`, and
`verify_entry_points.py` have all run (it re-parses their already-written
output, so it must run after them, not instead of them -- see the script's
own docstring). Regenerated in full every run, same as `index.md` and the
diagrams, regardless of full vs incremental mode.

It is purely a re-parse of already-written output -- it does not re-read
source code or re-verify anything against it. Everything in it is only as
correct as the module docs and `entry-points.md` it was extracted from,
which is what Phase 4's discipline and the two verify scripts are for.
Don't hand-edit it; if something in it looks wrong, the fix belongs in the
module doc or `entry-points.md` it was derived from, then re-run
`graph_export.py`.

Schema (version 1):

```json
{
  "version": 1,
  "generated_at": "<ISO8601>",
  "source_root": "<abs path at export time>",
  "modules": {
    "<slug>": {
      "path": "<relative path from the required _modules.json mapping>",
      "depends_on": [
        {
          "target": "other-module",
          "kind": "internal" | "external",
          "detail": "<bullet text minus the citation>",
          "citation": "<path:line, or null if not present on that line>"
        }
      ],
      "used_by": [ "<same shape as depends_on>" ],
      "trace_coverage": {
        "status": "full" | "sampled" | "listed" | "unstated",
        "detail": "<raw matched fragment, or null>"
      }
    }
  },
  "entry_points": {
    "http_routes": [{ "module": "...", "detail": "<path>", "raw": "<full row>" }],
    "cli_commands": [ "<same shape>" ],
    "queue_consumers": [
      "<same shape -- 'detail' is the topic/event name, the join key a future multi-repo run would match a publisher in one repo to a consumer in another>"
    ],
    "cron_jobs": [ "<same shape>" ]
  },
  "health_signals": {
    "most_connected": ["..."],
    "orphan_candidates": ["..."],
    "cycles": ["..."],
    "trace_coverage_counts": { "full": 0, "sampled": 0, "listed": 0, "unstated": 0 }
  }
}
```

Known limitations (v1, worth knowing before leaning on this for something
load-bearing -- both are noted here rather than only in the script's
docstring, since this is the file whoever consumes `_graph.json` is most
likely to actually read):

- `depends_on`/`used_by` internal/external classification is a convention
  check against the module template's bullet *prefix* (`**\`slug\`**` for
  internal, `external:\`name\`` for external). A module doc that doesn't
  start each bullet that way won't be captured here -- the same
  brittleness `rollup.py` already has against the same convention. The
  separator between that prefix and the rest of the bullet is not part of
  this check (any of `--`, an em dash, an en dash, a hyphen, or a colon is
  recognized and stripped), so writing style there doesn't affect
  extraction.
- Outbound cross-service calls (an HTTP client hitting another service, a
  gRPC stub) don't have a guaranteed structured field the way queue topics
  do -- they show up as prose inside a "Depends on" bullet's `detail` if
  written as an external dependency, or inside "Data & side effects" ->
  "Network calls" if not, and this script doesn't further parse either
  into a URL. `queue_consumers`' topic names are the one entry-point kind
  with a clean, already-tabular join key today; HTTP routes only capture
  the path this repo *serves*, not URLs it *calls*. A future multi-repo
  pass will likely need `external_calls.py`'s own hypothesis output
  (URLs/topics it detects) folded in here directly, not just what
  survived into module-doc prose.

## `_modules.json`

The persisted copy of Phase 2's slug -> relative-path mapping (the same
content as the `modules.json` file Phase 3's scripts take via `--modules`),
written into `<output_root>/_modules.json` at the *start* of Phase 5 --
before `_manifest.json`, which waits for Phase 6's fresh hashes, because
`graph_export.py` needs `_modules.json` on disk by the end of Phase 5:

```json
{ "api": "src/api", "services": "src/services", "...": "..." }
```

The set of slugs must match `modules/*.md` and `_diagram-data.json` exactly.
Generate new slugs with `stable_slug_map()` so normalized names cannot silently
collide, and reject duplicate source paths/JSON keys.

Two things read it back: `graph_export.py`, to fill in each module's
`path` field in `_graph.json` (a module slug alone doesn't tell an outside
tool where in the repo it lives); and Phase 2 itself on a later run, as a
starting point for slug continuity -- if a path Phase 1/2 rediscovers this
run already has a slug recorded here, reuse that slug rather than deriving
a new one, so a module's identity (its filename, its `_graph.json` key, its
join key for multi-repo stitching) doesn't drift between runs just because
nothing about the module actually changed. Like `_manifest.json`, this is
internal state -- not meant for a human to read, but plain JSON if one
opens it anyway.

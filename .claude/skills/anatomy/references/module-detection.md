# Identifying module boundaries

A "module" here means: a unit of the system that would reasonably get its own
page in an engineer's mental map of the codebase -- it has a cohesive
responsibility, and other parts of the code depend on it as a unit.

There's no universal rule for where module lines fall -- it depends on how the
project is organized. Use `scripts/inventory.py`'s output (top-level
directories, manifests, ambiguous_dirs_found) as your starting evidence, then
apply the shape that fits:

## Recognizing the project's shape

**Monorepo with workspaces.** Look for `package.json` with a `workspaces`
field, `pnpm-workspace.yaml`, `lerna.json`, a Cargo workspace (`Cargo.toml`
with `[workspace]` and `members`), or a Go multi-module setup (`go.work`).
Each workspace member is a module, regardless of how deep it's nested.

**Microservices / multi-app repo.** Multiple sibling directories (often
`services/*`, `apps/*`, or repo-root siblings) each with their own manifest
and/or `Dockerfile`. Each service is a module. If services share a `libs/` or
`common/` directory, that's also its own module (frequently an important one,
since everything depends on it).

**Layered monolith.** A single app with `src/` (or `app/`, `lib/`) containing
folders like `api`, `controllers`, `services`, `models`, `db`, `repositories`,
`utils`. Each top-level layer is a module. Framework conventions to know:
- Django: each `INSTALLED_APPS` entry (a directory with `models.py`/`views.py`)
  is a module.
- Rails: `app/{models,controllers,services,jobs,mailers}` are natural module
  lines.
- Spring/Java: packages under `src/main/java/.../` grouped by feature (not
  necessarily by layer) are usually the intended module boundary -- check
  `pom.xml`/`build.gradle` module declarations first.
- Next.js / similar: `app/` or `pages/` (+ `api/` routes), `lib/`,
  `components/` are reasonable module lines; a large `components/` folder may
  deserve splitting by feature area if it's genuinely large.
- Go: `cmd/*` are entry-point binaries (document as entry points, not full
  modules); `internal/*` and `pkg/*` subdirectories are modules.

**Library / single package.** If the whole thing is one cohesive package with
internal subpackages, the subpackages are modules -- unless the entire thing
is small (rule of thumb: under ~10 source files total), in which case treat
the whole package as a single module rather than fragmenting it into
one-file "modules."

## General sizing heuristic

Prefer coarser, fewer modules over many tiny ones. A good target for a
typical project is somewhere around 5-40 module files -- enough to be useful,
not so many that `index.md` becomes a wall of links nobody reads.

- If a directory has only one or two trivial files (a single constants file,
  a barrel/index re-export file), fold it into a sibling or into the module
  that consumes it most, rather than giving it its own doc.
- If a single directory is enormous (100+ files covering clearly distinct
  concerns), it's fine to split it into a few sub-module docs -- just don't
  over-fragment down to one doc per file.
- `scripts/inventory.py`'s `ambiguous_dirs_found` field flags directory names
  like `packages`, `vendor`, `third_party`, or `bin` that could be either "real modules
  in this monorepo" or "vendored dependencies we don't own." Open one or two
  files inside before deciding -- if it's someone else's code (has its own
  unrelated license/changelog, or matches a known open-source project), treat
  it as external and don't write a module doc for it; just note it as a
  dependency where relevant.

## Stable, collision-free module identity

Module slugs are persistent IDs: they become filenames, Mermaid node IDs, and
`_graph.json` join keys. Use `scripts/_common.py`'s `stable_slug_map()` over the
whole candidate set, not one independent `slugify()` call per module. The
helper normalizes names to ASCII-safe slugs and deterministically disambiguates
collisions caused by spaces, underscores, separators, or non-ASCII-only names.
Reuse `_modules.json` for unchanged paths on later runs. Treat duplicate JSON
keys, duplicate source paths, and post-normalization collisions as errors to
resolve before Phase 3.

## Entry points and composition roots

Every project has one or more files that wire modules together at startup
(`main.py`, `index.js`, `cmd/*/main.go`, `Program.cs`, a Spring
`@SpringBootApplication` class). These are worth identifying even when they
live in a directory too small to be its own module -- but rather than giving
a two-line entry point its own module file, document it in `index.md`'s
"Entry points" section, with a pointer to whichever module doc covers where
it lives.

## Infrastructure-as-code and non-application components

Don't forget things that aren't "app code" but are still real components of
the system: database migrations/schemas, background job or worker
definitions, message-queue consumers, Terraform/Kubernetes/Docker configs.
These deserve at least a mention -- either as their own module (if
substantial) or folded into the notes of the module they support (e.g.
migrations folded into the module covering persistence).

## When still unsure

State your module list explicitly before you start tracing content (a simple
slug -> path mapping), and sanity check it against the interaction graph from
`scripts/import_graph.py --group-by-top-level`: if two "modules" you picked
have such dense mutual edges that they're really one thing pretending to be
two, consider merging them. If a "module" has zero edges to or from anything
else, it might be dead code, a truly standalone utility, or a boundary you
drew in the wrong place -- worth a second look before writing it up.

# Interactive Onboarding and Setup Center Design

## 1. Purpose

Work Frontier must replace its command-heavy first-run and certification preparation flow with a guided, resumable setup experience. A user should not need to remember environment variable names, construct signing keys with one-off scripts, infer whether a value is a placeholder, or know the ordering between bootstrap, verification, commit, certification, and final approval.

The product will provide a hybrid onboarding flow:

1. a small CLI bootstrap starts a loopback-only setup server and opens the browser;
2. the Control Room provides a persistent Setup Center;
3. one application workflow powers first-run setup, later repair, reconfiguration, and headless automation;
4. secrets are stored behind references and are never written to normal configuration files;
5. release certification and production cutover remain explicit optional capabilities rather than blockers for local development.

This design covers onboarding and configuration orchestration only. It does not weaken existing exact-revision certification, approval, security, or cutover gates.

## 2. Decisions

The approved product decisions are:

- **Hybrid entry point:** CLI bootstrap plus browser-based Setup Center.
- **Two profiles:** Development and Production / Self-hosted, implemented by one workflow engine with profile-specific requirements.
- **Hybrid secret storage:** OS keychain for interactive workstations, externally managed providers or injected environment references for production and CI.
- **Detect → Plan → Apply:** detection is side-effect free; every change is shown before execution; execution is journaled, resumable, and compensates reversible actions on failure.
- **Persistent Setup Center:** first-run onboarding becomes an operational configuration and repair surface after setup.
- **Progressive capability readiness:** runtime, GitHub integration, release certification, and production cutover are reported independently.

## 3. User outcomes

### 3.1 Development outcome

After cloning the repository, a developer with `uv` installed runs:

```sh
uv run work-frontier setup
```

`uv run` resolves the bootstrap paradox: the project CLI does not need to be globally installed before its first invocation. Once installed as a tool or used inside an activated project environment, `work-frontier setup` is also valid.

The developer can then:

- inspect prerequisite checks;
- choose or create a safe GitHub sandbox connection;
- start local PostgreSQL and MinIO when Docker is available;
- apply migrations and storage initialization;
- run fast verification;
- enter the Control Room without manually exporting setup variables.

Release signing, the 72-hour soak, and production cutover are visible as later capabilities but do not block the local runtime.

### 3.2 Production / self-hosted outcome

An operator can:

- configure external PostgreSQL and object storage;
- configure a GitHub App machine identity separately from human OAuth/OIDC identity;
- select an OS or external secret provider;
- test connectivity and permissions before applying configuration;
- review every planned filesystem, service, database, and remote-system change;
- stop and resume setup safely;
- prepare release-certification and cutover inputs without copying private secrets into shell history.

### 3.3 Ongoing operations outcome

After initial setup, the same `/setup` experience becomes the Setup Center. It reports:

- runtime readiness;
- GitHub integration readiness;
- secret-reference health and known expiry;
- database and object-storage health;
- configuration drift;
- migration state;
- release-certification readiness;
- production-cutover readiness;
- repair or reconfiguration actions.

The product never collapses these into a misleading single “setup complete” state.

## 4. Capability model

Setup readiness is divided into four independent capabilities.

| Capability | Required for | Example gates |
| --- | --- | --- |
| Local Runtime Ready | Running and developing Work Frontier | toolchain, config, database, object storage, migrations, fast checks |
| GitHub Integration Ready | Syncing a repository | identity, repository access, installation scope, webhook or polling configuration |
| Release Certification Ready | Starting Standard ReleaseCertification | clean revision, signing key, sandbox, harness dependencies, soak policy |
| Production Cutover Ready | Activating the controlled writer cutover | approved change, exact source revision, parity evidence, rollback readiness |

Each capability has one of these states:

- `ready`
- `repairable`
- `needs_input`
- `blocked`
- `not_required`

A capability report includes the reason, impact, next safe action, and supporting checks. It never exposes a secret value.

## 5. Entry points and bootstrap asset delivery

### 5.1 Interactive CLI

The Typer application exposes:

```text
work-frontier setup
work-frontier setup status
work-frontier setup repair
work-frontier setup plan --json
work-frontier setup apply --plan setup-plan.json --non-interactive
work-frontier config show --redacted
```

From an unbootstrapped repository, documentation uses `uv run work-frontier ...`.

`work-frontier setup` performs only bootstrap responsibilities:

1. locate and validate the repository or installed package context;
2. run the minimal Python-level checks needed to start the setup experience;
3. bind a setup-only FastAPI process to `127.0.0.1` on an ephemeral port;
4. create a one-time setup session;
5. open the default browser with a fragment-held one-time token;
6. display a short Rich status table and a recovery URL without printing secrets;
7. remain attached to the setup process until completion or explicit detach.

The CLI must not embed the complete setup workflow. It delegates detection, planning, execution, and readiness to the application service.

### 5.2 Bootstrap UI assets

The first-run browser experience must work before Node, pnpm, or the normal frontend build is available. The React Setup Center therefore has a dedicated production build whose static assets are packaged with the Python distribution and committed/generated in the source checkout.

The build flow is:

```text
frontend/src/setup/
    ↓ dedicated Vite entry
backend/src/work_frontier/interfaces/setup_static/
    ↓ packaged by Hatch
setup-only FastAPI process
```

A deterministic asset-build script and drift check ensure the packaged bootstrap bundle matches the frontend source. The normal Control Room and the bootstrap bundle reuse the same generated setup contracts and UI components; there is no second handwritten HTML wizard.

Node and pnpm are still detected and configured for normal frontend development, but they are not prerequisites for rendering first-run guidance.

### 5.3 Setup-only web process

First-run setup uses a separate setup application factory rather than adding unauthenticated setup routes to the normal control-plane API.

The setup process:

- binds only to loopback by default;
- rejects non-loopback forwarded-host and origin combinations;
- accepts a one-time, short-lived setup session;
- serves only packaged setup assets and setup APIs;
- has no normal tenant/workspace data-plane routes;
- shuts down when the session completes, expires, or is explicitly closed.

### 5.4 Authenticated persistent Setup Center

After initialization, the normal Control Room exposes Setup Center APIs through an authenticated operator/admin session. The same application use cases and contracts are reused, but authorization is supplied by the normal identity and tenancy boundary rather than the one-time bootstrap session.

## 6. User flow

### 6.1 Step 1 — Choose profile

The user chooses:

- **Development**
- **Production / Self-hosted**

The profile determines defaults and required checks. It does not create separate configuration formats or separate workflow implementations. The user can change profile later through a reviewed migration plan.

### 6.2 Step 2 — Detect environment

Detection is read-only and covers:

- repository root, branch, revision, and dirty-tree state;
- Python, `uv`, Node, pnpm, Git, Docker, and Compose availability and versions;
- occupied ports and existing Work Frontier processes;
- current config files and schema versions;
- OS keychain backend availability;
- GitHub CLI authentication and account identity;
- reachable PostgreSQL and object-storage endpoints;
- existing setup journal and interrupted runs;
- relevant legacy environment variables, reported by name and presence only.

Every detector returns a typed result with state, summary, evidence metadata, remediation options, and redacted diagnostics.

### 6.3 Step 3 — Configure GitHub

#### Development

The preferred development credential source is the user’s existing GitHub CLI authentication. Work Frontier invokes `gh` through a process adapter and stores a reference such as:

```text
gh-cli://github.com/account-name
```

It does not duplicate the token into the Work Frontier keychain when GitHub CLI already owns it.

The wizard lists accessible candidate repositories, requires an explicit sandbox selection, and tests the permissions required by the selected development workflow. It distinguishes read-only checks from any test that would create or mutate remote content and asks for confirmation before the latter.

#### Production / self-hosted

The wizard configures GitHub App machine identity using App ID, installation, private-key secret reference, and webhook-secret reference. It validates token exchange and installation repository permissions.

Human OAuth/OIDC identity is configured separately for approval and attribution workflows. Machine credentials may not be reused as a human approval identity, and human tokens may not be used for automated sync or reconciliation.

### 6.4 Step 4 — Configure data services

#### Development

The planner may propose local PostgreSQL and MinIO through the repository’s supported Compose profile. The review page shows ports, containers, volumes, and cleanup behavior before apply.

Apply starts the services, runs migration and object-store smoke checks, and records verified service identities. Port conflicts produce a repair choice instead of silently changing shared repository defaults.

#### Production / self-hosted

The wizard accepts external PostgreSQL and S3-compatible object storage configuration through non-secret fields plus secret references. It tests TLS, authentication, required database capabilities, migration compatibility, bucket access, and object lifecycle assumptions.

The wizard does not create or destroy production databases, buckets, or cloud resources unless a future provider-specific action explicitly declares that behavior and receives separate confirmation.

### 6.5 Step 5 — Configure secret storage

The default interactive workstation provider is `keyring`, backed by macOS Keychain, Windows Credential Manager, or Linux Secret Service when available.

Headless and production flows support references such as:

```text
env://WF_DATABASE_PASSWORD
keyring://work-frontier/installations/local/github-app-private-key
keyring://work-frontier/release/standard-signing-key
```

Provider adapters may later add Vault or 1Password without changing application contracts. The first implementation includes keyring and environment-reference providers.

Normal configuration stores only secret references, fingerprints, provider metadata, and optional expiry. It never stores plaintext secret values.

### 6.6 Step 6 — Prepare optional release and cutover capabilities

Release and cutover preparation is not part of the minimum Development path.

When selected, the Setup Center can:

- generate or import a raw Ed25519 signing key;
- store the private key directly in the selected secret provider;
- display only the public key, key ID, and fingerprint;
- configure and validate the isolated GitHub sandbox;
- detect external harness tools and services;
- explain the clean-tree and exact-revision requirement;
- configure the real soak duration policy without simulating elapsed time;
- collect a cutover approval reference and exact source revision;
- prepare a certification plan.

The Setup Center invokes the existing certification workflow with a process-local resolved environment. It does not write a `.env` file and does not weaken placeholder rejection, exact-revision checks, soak duration, signature verification, parity, approval, or rollback gates.

### 6.7 Step 7 — Review plan

Before execution, the user receives a deterministic plan grouped by effects:

- files to create or update;
- secret references to create;
- services to start or stop;
- database migrations or checks;
- remote API checks or mutations;
- commands to run;
- explicitly excluded operations.

Each action declares:

- stable action ID;
- description and reason;
- risk level;
- dependencies;
- whether it is reversible;
- apply operation;
- verification operation;
- compensation operation when reversible;
- expected redacted evidence.

The serialized plan contains no secret values and is bound to a detection snapshot and config revision. Apply rejects a stale plan when relevant inputs have changed.

### 6.8 Step 8 — Apply, verify, and resume

Actions execute in dependency order and transition through:

- `pending`
- `running`
- `applied`
- `verified`
- `failed`
- `compensating`
- `compensated`
- `manual_recovery_required`

The executor journals state before and after every side effect. Re-running apply is idempotent: already verified actions are not repeated unless their verification has become stale.

If a run fails, reversible actions applied by that run are compensated in reverse dependency order where safe. Irreversible or externally owned changes are never described as rolled back; they enter `manual_recovery_required` with exact recovery guidance.

Closing the browser or restarting the machine does not lose progress. A later `work-frontier setup` discovers the journal and offers resume, inspect, compensate, or abandon-with-record options.

## 7. Architecture

The design follows the repository’s dependency direction: Interfaces call Application use cases; Application owns outbound ports; Platform implements local technical capabilities; concrete external integrations remain adapters; contracts are canonical Pydantic models.

### 7.1 Proposed modules

```text
backend/src/work_frontier/
  contracts/
    setup.py
  application/
    setup/
      detection.py
      planning.py
      execution.py
      readiness.py
      service.py
    ports/
      configuration.py
      secrets.py
      system_probe.py
      setup_actions.py
  platform/
    configuration/
      toml_store.py
      sqlite_journal.py
    secrets/
      keyring_store.py
      environment_store.py
    setup/
      local_system_probe.py
      process_actions.py
      docker_actions.py
  adapters/
    github/
      gh_cli_credentials.py
      github_app_setup.py
  interfaces/
    cli.py
    api/
      setup_app.py
      setup_routes.py
      setup_models.py
    setup_static/

frontend/src/setup/
  setup-center.tsx
  api.ts
  profile-step.tsx
  environment-step.tsx
  github-step.tsx
  services-step.tsx
  secrets-step.tsx
  certification-step.tsx
  review-step.tsx
  execution-step.tsx
```

The existing composition-root exemption wires concrete platform and adapter implementations into the setup application service. Interfaces do not construct concrete dependencies inside route handlers or React components.

### 7.2 Core application responsibilities

- `detection`: invokes read-only probes and produces a canonical snapshot.
- `planning`: deterministically converts profile, desired configuration, current configuration, and detection snapshot into an ordered plan.
- `execution`: applies one reviewed plan with journaling, idempotency, verification, and compensation.
- `readiness`: derives independent capability states from verified facts.
- `service`: exposes stable use cases to CLI and HTTP interfaces.

### 7.3 Core ports

- `ConfigurationStore`: versioned read, compare-and-swap write, and migration support.
- `SetupJournal`: durable session and action-state persistence.
- `SecretStore`: create, resolve, inspect metadata, rotate, and delete by reference.
- `SystemProbe`: read-only inspection of tools, processes, ports, filesystem, and services.
- `SetupActionRunner`: controlled side effects for processes, Docker, files, migrations, and verification commands.
- `GitHubSetupPort`: identity discovery, repository listing, permission checks, installation checks, and explicitly approved sandbox mutations.

No application use case returns a reusable plaintext secret after the initial store operation. Secret-bearing requests are excluded from journals, logs, audit payloads, and serialized action evidence; after storage, the workflow passes only secret references.

## 8. Contracts

Canonical Pydantic contracts include:

- `SetupProfile`
- `SetupCapability`
- `SetupSession`
- `SetupStep`
- `DetectionSnapshot`
- `DetectionResult`
- `DesiredConfiguration`
- `ConfigurationSnapshot`
- `SetupPlan`
- `SetupAction`
- `ActionState`
- `ActionResult`
- `SecretReference`
- `ReadinessReport`
- `SetupError`

Generated JSON Schema and frontend Zod contracts remain derived outputs. The frontend does not maintain a competing handwritten validation schema for shared setup payloads.

Secret submission uses a dedicated write-only request contract. Responses contain a `SecretReference`, fingerprint where applicable, and status; they never echo the submitted value.

## 9. Storage and concurrency

`platformdirs` determines OS-appropriate locations.

- User configuration: versioned `config.toml`.
- User state: a local SQLite setup journal and non-secret execution metadata.
- User cache: disposable detector caches and downloaded metadata.
- User logs: redacted setup logs with retention limits.

SQLite is used from the Python standard library because setup must work before PostgreSQL exists. It provides transactional action journals, session locks, monotonic state transitions, and safe resume across process restarts.

Configuration supports multiple named installations. Each installation records profile, non-secret endpoints, selected providers, and secret references. A schema version enables explicit migrations. Config writes use compare-and-swap revision checks plus atomic replacement so concurrent sessions cannot silently overwrite one another.

`tomlkit` preserves readable TOML formatting while the Pydantic settings model validates the resulting configuration. Environment settings remain a supported override and headless secret-reference source, not the default interactive storage mechanism.

Only one apply run may hold an installation lock. Other sessions remain read-only and can inspect progress.

## 10. API and progress transport

The first version uses normal JSON APIs plus short polling through TanStack Query. It does not introduce WebSockets or a new event-bus dependency.

Representative endpoints are:

```text
POST /setup/sessions
GET  /setup/sessions/{session_id}
POST /setup/sessions/{session_id}/detect
POST /setup/sessions/{session_id}/desired-configuration
POST /setup/sessions/{session_id}/plan
POST /setup/sessions/{session_id}/apply
GET  /setup/runs/{run_id}
POST /setup/runs/{run_id}/actions/{action_id}/retry
POST /setup/runs/{run_id}/compensate
POST /setup/secrets
POST /setup/sessions/{session_id}/verify
```

The setup-only app and authenticated Setup Center expose the same use cases under different authentication dependencies. The bootstrap token is never stored in browser `localStorage`; it is exchanged for an HttpOnly, SameSite-strict setup cookie and then removed from the browser-visible URL.

## 11. Security requirements

- First-run setup binds to loopback by default.
- A random one-time token has a short expiry and single exchange.
- Setup cookies are HttpOnly, Secure when applicable, SameSite strict, and protected by CSRF validation.
- Host, origin, and forwarded-header validation prevent DNS-rebinding and proxy confusion.
- The setup process has no data-plane routes.
- Production Setup Center requires an authorized operator/admin identity and workspace scope.
- Secret values never enter config, journals, audit events, URLs, frontend persistence, analytics, normal API responses, or exported diagnostics.
- Logs apply central redaction to credentials, private keys, authorization headers, connection strings, and submitted secret fields.
- Imported private-key source files are not automatically deleted; the UI explains the residual file risk and provides manual guidance.
- Remote mutations are separate plan actions and require explicit confirmation.
- Setup cannot approve its own authoritative changes, release certification, or production cutover.

## 12. Error model

All user-facing failures use one of these categories:

- `user_input`
- `missing_dependency`
- `permission_denied`
- `connection_failed`
- `conflict`
- `unsafe_state`
- `external_service`
- `internal_error`

A setup error includes:

- stable code;
- plain-language summary;
- affected capability;
- reason;
- impact;
- safe remediation actions;
- retryability;
- redacted diagnostic reference.

The UI does not show raw stack traces by default. Detailed logs remain accessible through an explicit diagnostics view and are redacted before storage and display.

## 13. Package choices

Backend additions:

- `pydantic-settings` for typed layered settings and custom providers;
- `keyring` for OS-backed workstation secret storage;
- `platformdirs` for portable config, state, cache, and log locations;
- `rich` for concise CLI progress and recovery output;
- `tomlkit` for readable, controlled TOML updates.

Typer, FastAPI, Pydantic, HTTPX, Uvicorn, Cryptography, and the standard-library SQLite and browser modules already cover the remaining CLI, API, validation, HTTP, local server, journal, Ed25519, and browser-launch requirements.

Frontend additions:

- `react-hook-form`;
- `@hookform/resolvers`.

Existing Zod contracts validate forms, and existing TanStack Query owns server state and polling. The design adds no separate global state-management framework.

All versions are pinned through the repository lockfiles during implementation.

## 14. Compatibility and migration

- Existing `make doctor`, `make bootstrap`, `make check`, and `make verify` remain deterministic and non-interactive for CI and advanced users.
- The interactive workflow is exposed through the Typer CLI, not hidden inside a Make target.
- Existing certification scripts remain authoritative.
- The Setup Center resolves configured secret references into a process-local environment only for the lifetime of a certification or cutover subprocess.
- Existing supported environment variables remain accepted for CI and migration.
- Legacy `.env` values are detected by name and may be imported through a reviewed migration that writes secrets to the selected provider and removes them from generated Work Frontier config. The wizard never deletes a user-owned `.env` automatically.
- The current frontend onboarding reducer is replaced by the Setup Center workflow rather than maintained as a second onboarding state machine.
- The packaged bootstrap asset bundle is generated and drift-checked; it is not an independent authoring surface.

## 15. Accessibility and UX requirements

- The complete Development flow is keyboard operable.
- Every progress indicator has text and ARIA status output.
- Focus moves to the first actionable error after failed validation.
- Color is never the sole readiness signal.
- Plan review has a table/list alternative and clear grouping by effect and risk.
- Destructive, irreversible, remote-mutating, and cutover actions require distinct confirmation language.
- Secret fields support paste and password-manager behavior, never reveal values by default, and clearly state storage destination before submission.
- The wizard provides explanatory empty states and does not expose implementation-oriented environment variable names unless the user opens advanced details.
- Closing and reopening the browser returns to the same durable run state.

## 16. Testing strategy

### 16.1 Application and platform tests

- detectors are side-effect free;
- planning is deterministic for identical inputs;
- stale plan hashes are rejected;
- apply is idempotent;
- interrupted runs resume correctly;
- compensation runs only for reversible actions owned by the current run;
- irreversible actions produce manual recovery state;
- configuration compare-and-swap prevents concurrent overwrite;
- installation locks prevent concurrent apply runs;
- config migrations preserve secret references;
- fake keyring and environment providers satisfy the same contract;
- secret values never appear in config, journals, logs, exceptions, or serialized responses;
- process-local environment materialization is removed after subprocess completion;
- GitHub machine and human identities cannot be interchanged;
- packaged setup assets match their source build.

### 16.2 API tests

- one-time token exchange and expiry;
- loopback, host, origin, cookie, and CSRF controls;
- authenticated Setup Center authorization;
- write-only secret request behavior;
- typed errors and redacted diagnostics;
- concurrent session and action-state handling;
- polling responses preserve monotonic action progress.

### 16.3 Frontend tests

- Development happy path;
- Production/self-hosted required fields and blockers;
- Docker unavailable and port-conflict recovery;
- GitHub permission mismatch;
- keychain unavailable fallback;
- dirty-tree certification explanation;
- signing-key generation shows only public fingerprint;
- resume after reload;
- keyboard-only completion;
- screen-reader status announcements;
- responsive behavior at supported viewports;
- no secrets in local/session storage or rendered diagnostics.

### 16.4 Headless tests

- `plan --json` is deterministic and redacted;
- non-interactive apply never prompts or opens a browser;
- missing required input fails before side effects;
- environment and external secret references work without workstation state;
- exit codes distinguish invalid input, unsafe state, failed action, and successful completion.

## 17. Non-goals

The first implementation does not:

- install Docker or system packages with elevated privileges;
- provision general-purpose cloud infrastructure;
- introduce a second release-certification implementation;
- shorten or simulate the required soak duration;
- automatically approve authoritative mutations or cutover;
- store plaintext secrets in `.env`, TOML, journals, browser storage, or logs;
- delete user-owned credential or private-key files automatically;
- support production trackers other than GitHub;
- add WebSockets, a new frontend state framework, Vault, or 1Password adapters before the keyring and environment-reference contracts are proven.

## 18. Acceptance criteria

The feature is complete when all of the following are true:

1. A new developer can move from clone to a verified local Control Room through `uv run work-frontier setup` without manually exporting Work Frontier setup variables.
2. The browser setup experience renders even when Node and pnpm are not yet installed.
3. Development setup requires only runtime and GitHub-integration capabilities; release and cutover preparation remain optional and visibly incomplete.
4. Production setup stores secrets only through references and never echoes a submitted secret.
5. Detect produces no side effects, Plan shows all intended effects, and Apply rejects stale plans.
6. An interrupted setup run can be resumed without repeating verified actions.
7. Failed reversible actions are compensated truthfully; irreversible changes receive explicit manual recovery guidance.
8. The persistent Setup Center reports independent readiness for runtime, GitHub integration, release certification, and cutover.
9. Existing CI Make targets and exact-revision certification behavior remain non-interactive and authoritative.
10. Both interactive and headless paths pass secret-leak, authorization, accessibility, configuration-migration, concurrency, and idempotency tests.
11. The existing command-heavy documentation is replaced by the guided golden path, while advanced command references remain available under troubleshooting and automation documentation.

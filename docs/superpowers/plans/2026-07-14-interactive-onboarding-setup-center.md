# Interactive Onboarding and Setup Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Work Frontier's command-heavy setup with one resumable `uv run work-frontier setup` flow backed by a persistent browser Setup Center, typed configuration, secret references, deterministic Detect → Plan → Apply execution, and independent capability readiness.

**Architecture:** A single Application-layer setup workflow owns detection, deterministic planning, journaled execution, compensation, and readiness. CLI, setup-only FastAPI, persistent Control Room routes, and headless JSON are Interfaces over that workflow; Platform and Adapter implementations own filesystem, SQLite, keyring, subprocess, Docker, and GitHub integration. Canonical Pydantic contracts generate JSON Schema and Zod artifacts consumed by the React Setup Center.

**Tech Stack:** Python 3.13, Typer, Rich 15.0.0, FastAPI, Pydantic 2.11+, pydantic-settings 2.14.2, keyring 25.7.0, platformdirs 4.10.0, tomlkit 0.15.0, SQLite, React 19, TanStack Query, Zod 4, React Hook Form, Vite, Vitest, Playwright, axe-core.

**Exact planning base:** `4e1df0afab9b764862cbe572e70183a3575ffad3`

**Design source:** `docs/superpowers/specs/2026-07-14-interactive-onboarding-setup-center-design.md`

## Global Constraints

- The first-run documented entry point is `uv run work-frontier setup`; globally installed `work-frontier setup` remains supported.
- Setup readiness is four independent capabilities: local runtime, GitHub integration, release certification, and production cutover.
- Detection is read-only. No detector may write files, launch services, mutate GitHub, or store secrets.
- Plans are deterministic, secret-free, bound to a detection snapshot and configuration revision, and rejected when stale.
- Every side effect is journaled before and after execution.
- Reversible actions compensate in reverse dependency order; irreversible actions become `manual_recovery_required`.
- Configuration stores secret references only. Plaintext secrets never enter TOML, SQLite, logs, evidence, JSON responses, URLs, browser storage, or fixtures.
- Development may use GitHub CLI credential references; production machine identity uses GitHub App credentials and remains separate from human OAuth/OIDC identity.
- The bootstrap setup server binds to loopback on an ephemeral port and is separate from the normal control-plane application.
- The setup browser bundle must render before Node or pnpm is available by serving checked-in packaged assets from the Python package.
- Existing certification, clean-tree, exact-revision, real soak, signature, parity, approval, and rollback gates remain unchanged.
- Existing Make targets remain deterministic and non-interactive. Interactive behavior belongs in the CLI and Setup Center.
- Pydantic is the canonical cross-language source. Generated JSON Schema and Zod files are never hand-edited.
- Strict TDD is mandatory: RED, verify RED, GREEN, verify GREEN, then commit.
- Do not tick `.omo/plans/full-product-implementation.md` items without exact executable evidence.

---

## File Map

### Canonical contracts

- Create `backend/src/work_frontier/contracts/setup.py` — setup enums and immutable request/response models.
- Modify `backend/src/work_frontier/contracts/__init__.py` — export public setup contracts.
- Modify `scripts/generate_contracts.py` — generate setup JSON Schema and Zod.
- Generate `contracts/generated/setup.schema.json`.
- Generate `frontend/src/contracts/setup.generated.ts`.

### Application workflow and ports

- Create `backend/src/work_frontier/application/setup/__init__.py`.
- Create `backend/src/work_frontier/application/setup/detection.py`.
- Create `backend/src/work_frontier/application/setup/planning.py`.
- Create `backend/src/work_frontier/application/setup/execution.py`.
- Create `backend/src/work_frontier/application/setup/readiness.py`.
- Create `backend/src/work_frontier/application/setup/service.py`.
- Create `backend/src/work_frontier/application/ports/configuration.py`.
- Create `backend/src/work_frontier/application/ports/secrets.py`.
- Create `backend/src/work_frontier/application/ports/system_probe.py`.
- Create `backend/src/work_frontier/application/ports/setup_actions.py`.
- Create `backend/src/work_frontier/application/ports/github_setup.py`.

### Platform and adapter implementations

- Create `backend/src/work_frontier/platform/configuration/__init__.py`.
- Create `backend/src/work_frontier/platform/configuration/paths.py`.
- Create `backend/src/work_frontier/platform/configuration/toml_store.py`.
- Create `backend/src/work_frontier/platform/configuration/sqlite_journal.py`.
- Create `backend/src/work_frontier/platform/secrets/__init__.py`.
- Create `backend/src/work_frontier/platform/secrets/keyring_store.py`.
- Create `backend/src/work_frontier/platform/secrets/environment_store.py`.
- Create `backend/src/work_frontier/platform/setup/__init__.py`.
- Create `backend/src/work_frontier/platform/setup/local_system_probe.py`.
- Create `backend/src/work_frontier/platform/setup/process_actions.py`.
- Create `backend/src/work_frontier/platform/setup/docker_actions.py`.
- Create `backend/src/work_frontier/adapters/github/gh_cli_credentials.py`.
- Create `backend/src/work_frontier/adapters/github/github_app_setup.py`.

### Composition and interfaces

- Replace the placeholder content of `backend/src/work_frontier/bootstrap.py` with setup composition functions while preserving `hello_contract()`.
- Create `backend/src/work_frontier/interfaces/cli.py`.
- Create `backend/src/work_frontier/interfaces/api/setup_app.py`.
- Create `backend/src/work_frontier/interfaces/api/setup_routes.py`.
- Create `backend/src/work_frontier/interfaces/api/setup_models.py`.
- Modify `backend/src/work_frontier/interfaces/api/app.py` — mount authenticated persistent Setup Center routes only.
- Create `backend/src/work_frontier/interfaces/setup_static/__init__.py`.
- Generate static files under `backend/src/work_frontier/interfaces/setup_static/assets/`.

### Frontend

- Create `frontend/setup.html`.
- Create `frontend/src/setup/main.tsx`.
- Create `frontend/src/setup/setup-center.tsx`.
- Create `frontend/src/setup/api.ts`.
- Create `frontend/src/setup/form-schema.ts`.
- Create `frontend/src/setup/profile-step.tsx`.
- Create `frontend/src/setup/environment-step.tsx`.
- Create `frontend/src/setup/github-step.tsx`.
- Create `frontend/src/setup/services-step.tsx`.
- Create `frontend/src/setup/secrets-step.tsx`.
- Create `frontend/src/setup/certification-step.tsx`.
- Create `frontend/src/setup/review-step.tsx`.
- Create `frontend/src/setup/execution-step.tsx`.
- Create `frontend/src/setup/setup-center.css`.
- Modify `frontend/src/control-room/app.tsx` — replace the seeded click-through onboarding gate with Setup Center readiness.
- Deprecate and delete `frontend/src/control-room/onboarding.ts` after migration.
- Modify `frontend/vite.config.ts`.
- Modify `frontend/package.json`.
- Modify `pnpm-lock.yaml`.

### Build, documentation, and verification

- Modify `pyproject.toml`.
- Modify `uv.lock`.
- Create `scripts/build_setup_assets.mjs`.
- Create `scripts/check_setup_assets.py`.
- Modify `Makefile`.
- Modify `README.md`.
- Modify `docs/development.md`.
- Create `docs/operations/setup-center.md`.

---

### Task 1: Add dependencies, CLI entry point, and setup contract skeleton

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `backend/src/work_frontier/contracts/setup.py`
- Modify: `backend/src/work_frontier/contracts/__init__.py`
- Test: `backend/tests/contracts/test_setup_contracts.py`

**Interfaces:**
- Produces: `SetupProfile`, `CapabilityName`, `CheckState`, `ActionState`, `SecretReference`, `DetectionCheck`, `DetectionSnapshot`, `SetupAction`, `SetupPlan`, `ActionResult`, `CapabilityReport`.
- Later tasks must import these exact names instead of creating parallel DTOs.

- [ ] **Step 1: Write the failing contract tests**

```python
from __future__ import annotations

from pydantic import ValidationError
import pytest

from work_frontier.contracts.setup import (
    ActionState,
    CapabilityName,
    CheckState,
    DetectionCheck,
    SecretReference,
    SetupAction,
    SetupPlan,
    SetupProfile,
)


def test_secret_reference_rejects_plaintext_and_accepts_supported_schemes() -> None:
    reference = SecretReference(uri="keyring://work-frontier/local/github-token")
    assert reference.scheme == "keyring"

    with pytest.raises(ValidationError):
        SecretReference(uri="plain-text-secret")


def test_setup_plan_is_secret_free_and_dependency_ordered() -> None:
    plan = SetupPlan(
        plan_id="plan-001",
        profile=SetupProfile.DEVELOPMENT,
        detection_snapshot_id="snapshot-001",
        config_revision="config-001",
        actions=(
            SetupAction(
                action_id="config.write",
                title="Write config",
                reason="Persist selected non-secret configuration",
                risk="low",
                reversible=True,
                depends_on=(),
                kind="write_config",
                parameters={"profile": "development"},
            ),
            SetupAction(
                action_id="services.start",
                title="Start local services",
                reason="Provide PostgreSQL and MinIO",
                risk="medium",
                reversible=True,
                depends_on=("config.write",),
                kind="docker_compose_up",
                parameters={"profile": "development"},
            ),
        ),
    )
    assert plan.actions[1].depends_on == ("config.write",)
    assert "secret" not in plan.model_dump_json().casefold()


def test_action_state_contains_manual_recovery_terminal_state() -> None:
    assert ActionState.MANUAL_RECOVERY_REQUIRED.value == "manual_recovery_required"
    assert CheckState.NOT_REQUIRED.value == "not_required"
    assert CapabilityName.PRODUCTION_CUTOVER.value == "production_cutover"
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
uv run pytest backend/tests/contracts/test_setup_contracts.py -v
```

Expected: collection fails because `work_frontier.contracts.setup` does not exist.

- [ ] **Step 3: Add runtime dependencies and CLI entry**

Add to `[project].dependencies`:

```toml
"keyring>=25.7.0",
"platformdirs>=4.10.0",
"pydantic-settings>=2.14.2",
"rich>=15.0.0",
"tomlkit>=0.15.0",
```

Add:

```toml
[project.scripts]
work-frontier = "work_frontier.interfaces.cli:main"
```

Run:

```bash
uv lock
uv sync --all-groups
```

- [ ] **Step 4: Implement the canonical setup contracts**

Create `backend/src/work_frontier/contracts/setup.py` with strict Pydantic models. The minimum public shape is:

```python
from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SetupProfile(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class CapabilityName(StrEnum):
    LOCAL_RUNTIME = "local_runtime"
    GITHUB_INTEGRATION = "github_integration"
    RELEASE_CERTIFICATION = "release_certification"
    PRODUCTION_CUTOVER = "production_cutover"


class CheckState(StrEnum):
    READY = "ready"
    REPAIRABLE = "repairable"
    NEEDS_INPUT = "needs_input"
    BLOCKED = "blocked"
    NOT_REQUIRED = "not_required"


class ActionState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    APPLIED = "applied"
    VERIFIED = "verified"
    FAILED = "failed"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    MANUAL_RECOVERY_REQUIRED = "manual_recovery_required"


class SecretReference(StrictModel):
    uri: Annotated[str, Field(min_length=8, max_length=512)]

    @field_validator("uri")
    @classmethod
    def validate_uri(cls, value: str) -> str:
        scheme, separator, remainder = value.partition("://")
        if separator != "://" or scheme not in {"keyring", "env", "gh-cli"}:
            raise ValueError("secret reference must use keyring://, env://, or gh-cli://")
        if not remainder or any(character.isspace() for character in value):
            raise ValueError("secret reference must contain a non-empty opaque path")
        return value

    @computed_field
    @property
    def scheme(self) -> str:
        return self.uri.partition("://")[0]


class DetectionCheck(StrictModel):
    check_id: str
    state: CheckState
    summary: str
    impact: str
    remediation: tuple[str, ...] = ()
    evidence: dict[str, str | int | bool | None] = Field(default_factory=dict)


class DetectionSnapshot(StrictModel):
    snapshot_id: str
    profile: SetupProfile
    config_revision: str
    checks: tuple[DetectionCheck, ...]


class SetupAction(StrictModel):
    action_id: str
    title: str
    reason: str
    risk: Literal["low", "medium", "high"]
    reversible: bool
    depends_on: tuple[str, ...]
    kind: str
    parameters: dict[str, str | int | bool | None]

    @model_validator(mode="after")
    def reject_self_dependency(self) -> "SetupAction":
        if self.action_id in self.depends_on:
            raise ValueError("action cannot depend on itself")
        return self


class SetupPlan(StrictModel):
    plan_id: str
    profile: SetupProfile
    detection_snapshot_id: str
    config_revision: str
    actions: tuple[SetupAction, ...]

    @model_validator(mode="after")
    def validate_graph_and_secrets(self) -> "SetupPlan":
        ids = [action.action_id for action in self.actions]
        if len(ids) != len(set(ids)):
            raise ValueError("setup action IDs must be unique")
        known: set[str] = set()
        for action in self.actions:
            if any(dependency not in known for dependency in action.depends_on):
                raise ValueError("actions must be serialized in dependency order")
            known.add(action.action_id)
        serialized = self.model_dump_json().casefold()
        forbidden = ("password", "private_key", "private-key", "token_value", "secret_value")
        if any(marker in serialized for marker in forbidden):
            raise ValueError("setup plan contains a secret-bearing field")
        return self


class ActionResult(StrictModel):
    action_id: str
    state: ActionState
    message: str
    redacted_evidence: dict[str, str | int | bool | None] = Field(default_factory=dict)


class CapabilityReport(StrictModel):
    capability: CapabilityName
    state: CheckState
    reason: str
    impact: str
    next_actions: tuple[str, ...]
    supporting_check_ids: tuple[str, ...]
```

Export these names from `contracts/__init__.py`.

- [ ] **Step 5: Verify GREEN and commit**

```bash
uv run pytest backend/tests/contracts/test_setup_contracts.py -v
uv run ruff check backend/src/work_frontier/contracts/setup.py backend/tests/contracts/test_setup_contracts.py
git add pyproject.toml uv.lock backend/src/work_frontier/contracts backend/tests/contracts/test_setup_contracts.py
git commit -m "feat(setup): add canonical onboarding contracts"
```

---

### Task 2: Generate Setup JSON Schema and Zod contracts

**Files:**
- Modify: `scripts/generate_contracts.py`
- Generate: `contracts/generated/setup.schema.json`
- Generate: `frontend/src/contracts/setup.generated.ts`
- Test: `backend/tests/contracts/test_setup_generated_contracts.py`

**Interfaces:**
- Consumes: `SetupPlan`, `DetectionSnapshot`, `CapabilityReport`.
- Produces: generated `SetupEnvelopeSchema` and TypeScript types for all setup HTTP payloads.

- [ ] **Step 1: Add a failing drift test**

```python
from pathlib import Path

from scripts.generate_contracts import artifacts_are_current, expected_artifacts


def test_setup_contract_is_part_of_generated_artifacts() -> None:
    paths = {path for path, _content in expected_artifacts()}
    assert Path("contracts/generated/setup.schema.json") in paths
    assert Path("frontend/src/contracts/setup.generated.ts") in paths
    assert artifacts_are_current()
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest backend/tests/contracts/test_setup_generated_contracts.py -v
```

Expected: setup artifact paths are absent.

- [ ] **Step 3: Add a stable envelope and generator entries**

Add to `contracts/setup.py`:

```python
class SetupEnvelope(StrictModel):
    detection: DetectionSnapshot | None = None
    plan: SetupPlan | None = None
    capabilities: tuple[CapabilityReport, ...] = ()
    results: tuple[ActionResult, ...] = ()
```

Update `scripts/generate_contracts.py` constants and `expected_artifacts()`:

```python
from work_frontier.contracts.setup import SetupEnvelope

SETUP_SCHEMA_PATH = CONTRACT_DIRECTORY / "setup.schema.json"
ZOD_SETUP_PATH = Path("frontend/src/contracts/setup.generated.ts")


def setup_schema() -> str:
    schema = SetupEnvelope.model_json_schema()
    return f"{json.dumps(schema, indent=2, sort_keys=True)}\n"


def setup_zod_source() -> str:
    return _zod_source(setup_schema(), SETUP_SCHEMA_PATH, "SetupEnvelopeSchema")
```

Append both artifacts to `expected_artifacts()`.

- [ ] **Step 4: Generate and verify**

```bash
make generate-contracts
make check-contracts
uv run pytest backend/tests/contracts/test_setup_generated_contracts.py -v
```

Expected: all pass; generated files contain the “Do not edit” header.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_contracts.py backend/src/work_frontier/contracts/setup.py \
  contracts/generated/setup.schema.json frontend/src/contracts/setup.generated.ts \
  backend/tests/contracts/test_setup_generated_contracts.py
git commit -m "feat(setup): generate cross-language setup contracts"
```

---

### Task 3: Define Application ports and deterministic in-memory fakes

**Files:**
- Create: `backend/src/work_frontier/application/ports/configuration.py`
- Create: `backend/src/work_frontier/application/ports/secrets.py`
- Create: `backend/src/work_frontier/application/ports/system_probe.py`
- Create: `backend/src/work_frontier/application/ports/setup_actions.py`
- Create: `backend/src/work_frontier/application/ports/github_setup.py`
- Create: `backend/tests/setup/fakes.py`
- Test: `backend/tests/application/setup/test_ports.py`

**Interfaces:**
- Produces exact protocols:
  - `ConfigurationStore.read() -> ConfigurationDocument`
  - `ConfigurationStore.compare_and_swap(expected_revision, document) -> str`
  - `SetupJournal.create_session(...)`, `record_transition(...)`, `load_session(...)`
  - `SecretStore.store()`, `resolve()`, `metadata()`, `delete()`
  - `SystemProbe.detect(profile) -> tuple[DetectionCheck, ...]`
  - `SetupActionRunner.apply()`, `verify()`, `compensate()`
  - `GitHubSetupPort.inspect_identity()`, `list_repositories()`, `check_permissions()`.

- [ ] **Step 1: Write failing protocol/fake tests**

```python
from backend.tests.setup.fakes import FakeConfigurationStore, FakeSecretStore
from work_frontier.contracts.setup import SecretReference


def test_fake_configuration_store_uses_compare_and_swap() -> None:
    store = FakeConfigurationStore()
    document, revision = store.read()
    next_revision = store.compare_and_swap(revision, document)
    assert next_revision != revision


def test_fake_secret_store_returns_reference_not_plaintext() -> None:
    store = FakeSecretStore()
    reference = store.store(
        namespace="local",
        name="github-token",
        value="sensitive",
    )
    assert reference == SecretReference(uri="keyring://work-frontier/local/github-token")
    assert store.resolve(reference) == "sensitive"
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest backend/tests/application/setup/test_ports.py -v
```

Expected: imports fail.

- [ ] **Step 3: Implement Protocol definitions**

Use `typing.Protocol`, immutable dataclasses for internal non-cross-language values, and exact signatures. Example:

```python
from typing import Protocol

from work_frontier.contracts.setup import DetectionCheck, SetupAction, SetupProfile


class SystemProbe(Protocol):
    def detect(self, profile: SetupProfile) -> tuple[DetectionCheck, ...]:
        """Return read-only environment facts."""


class SetupActionRunner(Protocol):
    def apply(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        """Apply one reviewed action."""

    def verify(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        """Verify one applied action."""

    def compensate(self, action: SetupAction) -> dict[str, str | int | bool | None]:
        """Compensate one reversible action."""
```

`SecretStore.resolve()` is allowed only inside Platform/Adapter execution paths; Application services never return its result.

- [ ] **Step 4: Add fakes and verify GREEN**

```bash
uv run pytest backend/tests/application/setup/test_ports.py -v
make check-architecture
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/work_frontier/application/ports backend/tests/setup backend/tests/application/setup/test_ports.py
git commit -m "feat(setup): define configuration and execution ports"
```

---

### Task 4: Implement platform paths and versioned TOML configuration

**Files:**
- Create: `backend/src/work_frontier/platform/configuration/__init__.py`
- Create: `backend/src/work_frontier/platform/configuration/paths.py`
- Create: `backend/src/work_frontier/platform/configuration/toml_store.py`
- Test: `backend/tests/platform/configuration/test_toml_store.py`

**Interfaces:**
- Produces `WorkFrontierPaths.for_user()`.
- Implements `ConfigurationStore`.
- Configuration schema version starts at `1`; writes use compare-and-swap and atomic replacement.

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path

import pytest

from work_frontier.platform.configuration.paths import WorkFrontierPaths
from work_frontier.platform.configuration.toml_store import (
    ConfigurationConflictError,
    TomlConfigurationStore,
)


def test_paths_keep_config_state_and_logs_separate(tmp_path: Path) -> None:
    paths = WorkFrontierPaths.from_root(tmp_path)
    assert paths.config_file == tmp_path / "config" / "config.toml"
    assert paths.journal_file == tmp_path / "state" / "setup.sqlite3"
    assert paths.log_directory == tmp_path / "logs"


def test_toml_store_is_atomic_and_rejects_stale_revision(tmp_path: Path) -> None:
    store = TomlConfigurationStore(WorkFrontierPaths.from_root(tmp_path))
    document, revision = store.read()
    new_revision = store.compare_and_swap(revision, document)
    with pytest.raises(ConfigurationConflictError):
        store.compare_and_swap(revision, document)
    assert new_revision != revision


def test_toml_store_rejects_plaintext_secret_keys(tmp_path: Path) -> None:
    store = TomlConfigurationStore(WorkFrontierPaths.from_root(tmp_path))
    document, revision = store.read()
    document["github_token"] = "plaintext"
    with pytest.raises(ValueError, match="secret reference"):
        store.compare_and_swap(revision, document)
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest backend/tests/platform/configuration/test_toml_store.py -v
```

- [ ] **Step 3: Implement paths and TOML store**

`WorkFrontierPaths.for_user()` uses:

```python
from platformdirs import PlatformDirs

directories = PlatformDirs("work-frontier", "Work Frontier")
```

`TomlConfigurationStore` must:

- default to `schema_version = 1`;
- calculate revision as SHA-256 of canonical UTF-8 bytes;
- use `tomlkit` to preserve comments and ordering;
- write to a sibling temporary file, `fsync`, then `replace`;
- reject keys matching `password`, `token`, `private_key`, or `secret` unless the value is a supported `SecretReference.uri`.

- [ ] **Step 4: Verify GREEN**

```bash
uv run pytest backend/tests/platform/configuration/test_toml_store.py -v
uv run basedpyright backend/src/work_frontier/platform/configuration
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/work_frontier/platform/configuration backend/tests/platform/configuration
git commit -m "feat(setup): add versioned local configuration store"
```

---

### Task 5: Implement environment and OS-keyring secret providers

**Files:**
- Create: `backend/src/work_frontier/platform/secrets/__init__.py`
- Create: `backend/src/work_frontier/platform/secrets/environment_store.py`
- Create: `backend/src/work_frontier/platform/secrets/keyring_store.py`
- Test: `backend/tests/platform/secrets/test_secret_stores.py`

**Interfaces:**
- Implements `SecretStore`.
- Keyring references use `keyring://work-frontier/{namespace}/{name}`.
- Environment references use `env://VARIABLE_NAME` and are read-only.

- [ ] **Step 1: Write failing tests with an injected keyring backend**

```python
import os

import pytest

from work_frontier.contracts.setup import SecretReference
from work_frontier.platform.secrets.environment_store import EnvironmentSecretStore
from work_frontier.platform.secrets.keyring_store import KeyringSecretStore


class MemoryBackend:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        del self.values[(service, username)]


def test_keyring_store_never_returns_secret_from_store() -> None:
    backend = MemoryBackend()
    store = KeyringSecretStore(backend)
    reference = store.store(namespace="release", name="signing-key", value="raw-key")
    assert reference.uri == "keyring://work-frontier/release/signing-key"
    assert store.resolve(reference) == "raw-key"


def test_environment_store_is_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WF_DATABASE_PASSWORD", "db-secret")
    store = EnvironmentSecretStore(os.environ)
    reference = SecretReference(uri="env://WF_DATABASE_PASSWORD")
    assert store.resolve(reference) == "db-secret"
    with pytest.raises(PermissionError):
        store.store(namespace="x", name="y", value="z")
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest backend/tests/platform/secrets/test_secret_stores.py -v
```

- [ ] **Step 3: Implement providers with fail-closed metadata**

`KeyringSecretStore` catches `keyring.errors.KeyringError` and raises typed `SecretStoreUnavailableError` without including the secret value.

Metadata includes only:

```python
{
    "provider": "keyring",
    "reference": reference.uri,
    "present": True,
    "fingerprint": hashlib.sha256(value.encode()).hexdigest()[:16],
}
```

- [ ] **Step 4: Add redaction regression and verify**

Add a test that serializes every exception and metadata payload and asserts the secret string is absent.

```bash
uv run pytest backend/tests/platform/secrets/test_secret_stores.py -v
make check-architecture
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/work_frontier/platform/secrets backend/tests/platform/secrets
git commit -m "feat(setup): add secret reference providers"
```

---

### Task 6: Implement transactional SQLite setup journal

**Files:**
- Create: `backend/src/work_frontier/platform/configuration/sqlite_journal.py`
- Test: `backend/tests/platform/configuration/test_sqlite_journal.py`

**Interfaces:**
- Implements `SetupJournal`.
- Exposes one active writer per setup session.
- Stores no secret values or secret-bearing request bodies.

- [ ] **Step 1: Write failing concurrency and resume tests**

```python
from pathlib import Path

import pytest

from work_frontier.contracts.setup import ActionState
from work_frontier.platform.configuration.sqlite_journal import (
    JournalConflictError,
    SqliteSetupJournal,
)


def test_journal_resumes_verified_and_failed_actions(tmp_path: Path) -> None:
    journal = SqliteSetupJournal(tmp_path / "setup.sqlite3")
    journal.create_session("session-1", "plan-1")
    journal.record_transition("session-1", "config.write", ActionState.RUNNING, {})
    journal.record_transition("session-1", "config.write", ActionState.VERIFIED, {"path": "config.toml"})
    journal.record_transition("session-1", "services.start", ActionState.FAILED, {"error": "port conflict"})

    session = journal.load_session("session-1")
    assert session.actions["config.write"].state is ActionState.VERIFIED
    assert session.actions["services.start"].state is ActionState.FAILED


def test_journal_rejects_second_writer(tmp_path: Path) -> None:
    first = SqliteSetupJournal(tmp_path / "setup.sqlite3")
    second = SqliteSetupJournal(tmp_path / "setup.sqlite3")
    first.acquire_writer("session-1", "writer-a")
    with pytest.raises(JournalConflictError):
        second.acquire_writer("session-1", "writer-b")
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest backend/tests/platform/configuration/test_sqlite_journal.py -v
```

- [ ] **Step 3: Implement schema and transitions**

SQLite tables:

```sql
CREATE TABLE setup_sessions (
  session_id TEXT PRIMARY KEY,
  plan_id TEXT NOT NULL,
  status TEXT NOT NULL,
  writer_id TEXT,
  writer_lease_expires_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE setup_action_transitions (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  action_id TEXT NOT NULL,
  state TEXT NOT NULL,
  redacted_payload_json TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES setup_sessions(session_id)
);
```

Use `BEGIN IMMEDIATE`, WAL mode, foreign keys, and allowed transition validation.

- [ ] **Step 4: Verify GREEN**

```bash
uv run pytest backend/tests/platform/configuration/test_sqlite_journal.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/work_frontier/platform/configuration/sqlite_journal.py \
  backend/tests/platform/configuration/test_sqlite_journal.py
git commit -m "feat(setup): journal resumable setup execution"
```

---

### Task 7: Implement read-only environment detection

**Files:**
- Create: `backend/src/work_frontier/application/setup/__init__.py`
- Create: `backend/src/work_frontier/application/setup/detection.py`
- Create: `backend/src/work_frontier/platform/setup/__init__.py`
- Create: `backend/src/work_frontier/platform/setup/local_system_probe.py`
- Test: `backend/tests/application/setup/test_detection.py`
- Test: `backend/tests/platform/setup/test_local_system_probe.py`

**Interfaces:**
- Produces `detect_environment(profile, config_revision, probe) -> DetectionSnapshot`.
- `LocalSystemProbe` inspects Git, Python, uv, Node, pnpm, Docker, Compose, ports, processes, config, keyring, GitHub CLI, database, object storage, and legacy env variable presence.

- [ ] **Step 1: Write failing deterministic snapshot test**

```python
from backend.tests.setup.fakes import FakeSystemProbe
from work_frontier.application.setup.detection import detect_environment
from work_frontier.contracts.setup import CheckState, DetectionCheck, SetupProfile


def test_detection_snapshot_is_deterministic_and_read_only() -> None:
    probe = FakeSystemProbe(
        checks=(
            DetectionCheck(
                check_id="tool.uv",
                state=CheckState.READY,
                summary="uv 0.8.0",
                impact="Python dependencies can be resolved",
                evidence={"version": "0.8.0"},
            ),
        )
    )
    first = detect_environment(SetupProfile.DEVELOPMENT, "config-1", probe)
    second = detect_environment(SetupProfile.DEVELOPMENT, "config-1", probe)
    assert first == second
    assert probe.side_effect_count == 0
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest backend/tests/application/setup/test_detection.py -v
```

- [ ] **Step 3: Implement application detection hashing**

The snapshot ID is SHA-256 over canonical JSON of profile, config revision, and sorted checks. Sort checks by `check_id`; sort evidence keys.

- [ ] **Step 4: Implement local probes**

Use injected wrappers for filesystem, environment, sockets, and process execution. Every subprocess uses:

```python
subprocess.run(
    command,
    check=False,
    capture_output=True,
    text=True,
    timeout=10,
    env=safe_environment,
)
```

Never invoke mutation commands. Git status uses `git status --porcelain`; legacy environment detection records only `{name: present}`.

- [ ] **Step 5: Verify failure paths**

```bash
uv run pytest backend/tests/application/setup/test_detection.py \
  backend/tests/platform/setup/test_local_system_probe.py -v
```

Cover missing Docker, occupied port, locked keyring, unauthenticated `gh`, unreachable PostgreSQL, and malformed tool version output.

- [ ] **Step 6: Commit**

```bash
git add backend/src/work_frontier/application/setup \
  backend/src/work_frontier/platform/setup \
  backend/tests/application/setup/test_detection.py \
  backend/tests/platform/setup/test_local_system_probe.py
git commit -m "feat(setup): detect onboarding environment safely"
```

---

### Task 8: Implement deterministic planning and stale-plan rejection

**Files:**
- Create: `backend/src/work_frontier/application/setup/planning.py`
- Test: `backend/tests/application/setup/test_planning.py`

**Interfaces:**
- Produces `build_setup_plan(profile, desired, current, snapshot) -> SetupPlan`.
- Produces `assert_plan_current(plan, snapshot, config_revision) -> None`.
- Action IDs and ordering are stable across equivalent inputs.

- [ ] **Step 1: Write failing plan tests**

```python
import pytest

from work_frontier.application.setup.planning import (
    StaleSetupPlanError,
    assert_plan_current,
    build_setup_plan,
)
from work_frontier.contracts.setup import SetupProfile


def test_development_plan_orders_config_before_services_and_verification(
    development_inputs,
) -> None:
    plan = build_setup_plan(
        profile=SetupProfile.DEVELOPMENT,
        desired=development_inputs.desired,
        current=development_inputs.current,
        snapshot=development_inputs.snapshot,
    )
    assert [action.action_id for action in plan.actions] == [
        "config.write",
        "secrets.github.reference",
        "services.local.start",
        "database.migrate",
        "storage.verify",
        "checks.fast",
    ]


def test_plan_rejects_changed_detection_snapshot(development_inputs) -> None:
    plan = build_setup_plan(
        profile=SetupProfile.DEVELOPMENT,
        desired=development_inputs.desired,
        current=development_inputs.current,
        snapshot=development_inputs.snapshot,
    )
    with pytest.raises(StaleSetupPlanError):
        assert_plan_current(
            plan,
            development_inputs.changed_snapshot,
            development_inputs.current_revision,
        )
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest backend/tests/application/setup/test_planning.py -v
```

- [ ] **Step 3: Implement explicit action factories**

Do not construct untyped dictionaries inline throughout the planner. Provide focused factories:

```python
def write_config_action(...) -> SetupAction: ...
def store_secret_reference_action(...) -> SetupAction: ...
def start_local_services_action(...) -> SetupAction: ...
def migrate_database_action(...) -> SetupAction: ...
def verify_storage_action(...) -> SetupAction: ...
def run_fast_checks_action(...) -> SetupAction: ...
def prepare_release_action(...) -> SetupAction: ...
```

Action `parameters` contain references and non-secret values only.

- [ ] **Step 4: Add production and no-op plan coverage**

Production plans must not contain local Compose actions. An already-ready environment produces an empty plan and readiness reports, not fake actions.

```bash
uv run pytest backend/tests/application/setup/test_planning.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/work_frontier/application/setup/planning.py \
  backend/tests/application/setup/test_planning.py
git commit -m "feat(setup): plan reviewed setup changes deterministically"
```

---

### Task 9: Implement journaled execution, verification, compensation, and resume

**Files:**
- Create: `backend/src/work_frontier/application/setup/execution.py`
- Test: `backend/tests/application/setup/test_execution.py`

**Interfaces:**
- Produces `execute_plan(plan, snapshot, config_revision, journal, runner) -> tuple[ActionResult, ...]`.
- Produces `resume_session(session_id, plan, journal, runner)`.
- Never repeats a still-valid `verified` action.

- [ ] **Step 1: Write failing execution tests**

```python
from work_frontier.application.setup.execution import execute_plan
from work_frontier.contracts.setup import ActionState


def test_executor_verifies_each_action_before_advancing(execution_fixture) -> None:
    results = execute_plan(**execution_fixture.arguments)
    assert [result.state for result in results] == [
        ActionState.VERIFIED,
        ActionState.VERIFIED,
    ]
    assert execution_fixture.runner.calls == [
        ("apply", "config.write"),
        ("verify", "config.write"),
        ("apply", "services.start"),
        ("verify", "services.start"),
    ]


def test_executor_compensates_reversible_actions_in_reverse_order(failing_fixture) -> None:
    results = execute_plan(**failing_fixture.arguments)
    assert failing_fixture.runner.calls[-2:] == [
        ("compensate", "services.start"),
        ("compensate", "config.write"),
    ]
    assert results[-1].state is ActionState.FAILED


def test_resume_skips_verified_action(resume_fixture) -> None:
    execute_plan(**resume_fixture.arguments)
    assert ("apply", "config.write") not in resume_fixture.runner.calls
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest backend/tests/application/setup/test_execution.py -v
```

- [ ] **Step 3: Implement the executor state machine**

Before each side effect:

1. acquire/renew writer lease;
2. record `running`;
3. call `apply`;
4. record `applied`;
5. call `verify`;
6. record `verified`.

On failure:

- record `failed`;
- compensate reversible actions from this run in reverse topological order;
- record `compensating` then `compensated`;
- mark irreversible affected actions `manual_recovery_required`.

- [ ] **Step 4: Add secret leakage regression**

Inject a fake runner exception containing a secret and require the executor redactor to replace it with `[REDACTED]` before journaling.

```bash
uv run pytest backend/tests/application/setup/test_execution.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/work_frontier/application/setup/execution.py \
  backend/tests/application/setup/test_execution.py
git commit -m "feat(setup): execute and resume reviewed setup plans"
```

---

### Task 10: Implement independent capability readiness

**Files:**
- Create: `backend/src/work_frontier/application/setup/readiness.py`
- Test: `backend/tests/application/setup/test_readiness.py`

**Interfaces:**
- Produces `derive_capability_reports(profile, checks, action_results) -> tuple[CapabilityReport, ...]`.
- Always returns all four capabilities in fixed order.

- [ ] **Step 1: Write failing readiness tests**

```python
from work_frontier.application.setup.readiness import derive_capability_reports
from work_frontier.contracts.setup import CapabilityName, CheckState, SetupProfile


def test_development_can_be_runtime_ready_while_release_is_not_required(readiness_checks) -> None:
    reports = derive_capability_reports(
        SetupProfile.DEVELOPMENT,
        readiness_checks,
        (),
    )
    by_name = {report.capability: report for report in reports}
    assert by_name[CapabilityName.LOCAL_RUNTIME].state is CheckState.READY
    assert by_name[CapabilityName.GITHUB_INTEGRATION].state is CheckState.READY
    assert by_name[CapabilityName.RELEASE_CERTIFICATION].state is CheckState.NOT_REQUIRED
    assert by_name[CapabilityName.PRODUCTION_CUTOVER].state is CheckState.NOT_REQUIRED
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest backend/tests/application/setup/test_readiness.py -v
```

- [ ] **Step 3: Implement explicit check ownership**

Define fixed mappings from check IDs to capabilities. Use worst-state precedence:

```python
BLOCKED > NEEDS_INPUT > REPAIRABLE > READY > NOT_REQUIRED
```

Do not derive readiness from whether a button was clicked or a plan exists.

- [ ] **Step 4: Verify GREEN and commit**

```bash
uv run pytest backend/tests/application/setup/test_readiness.py -v
git add backend/src/work_frontier/application/setup/readiness.py \
  backend/tests/application/setup/test_readiness.py
git commit -m "feat(setup): report capability readiness independently"
```

---

### Task 11: Implement GitHub CLI and GitHub App setup adapters

**Files:**
- Create: `backend/src/work_frontier/adapters/github/gh_cli_credentials.py`
- Create: `backend/src/work_frontier/adapters/github/github_app_setup.py`
- Test: `backend/tests/adapters/github/test_gh_cli_credentials.py`
- Test: `backend/tests/adapters/github/test_github_app_setup.py`

**Interfaces:**
- Implements `GitHubSetupPort`.
- Development returns `gh-cli://github.com/{login}` references.
- Production validates App ID, installation, private-key reference, webhook-secret reference, and permissions.
- No adapter returns a reusable access token to Application.

- [ ] **Step 1: Write failing GitHub CLI tests**

```python
def test_gh_cli_identity_uses_reference_without_copying_token(fake_process) -> None:
    fake_process.add_json(
        ["gh", "auth", "status", "--hostname", "github.com", "--json", "hosts"],
        {"hosts": {"github.com": [{"login": "octocat", "active": True}]}}
    )
    adapter = GhCliCredentials(fake_process)
    identity = adapter.inspect_identity()
    assert identity.credential_reference.uri == "gh-cli://github.com/octocat"
    assert "token" not in identity.model_dump_json().casefold()
```

- [ ] **Step 2: Write failing GitHub App tests**

Use a fake HTTP transport to assert:

- JWT exchange succeeds;
- installation token remains local to adapter call;
- required repository permissions are reported;
- machine identity cannot satisfy a human approval identity request.

- [ ] **Step 3: Verify RED**

```bash
uv run pytest backend/tests/adapters/github/test_gh_cli_credentials.py \
  backend/tests/adapters/github/test_github_app_setup.py -v
```

- [ ] **Step 4: Implement adapters with typed error translation**

Use `httpx.Client` with injected transport, fixed timeout, GitHub API version header, and redacted exceptions.

- [ ] **Step 5: Verify GREEN and architecture**

```bash
uv run pytest backend/tests/adapters/github/test_gh_cli_credentials.py \
  backend/tests/adapters/github/test_github_app_setup.py -v
make check-architecture
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/work_frontier/adapters/github \
  backend/tests/adapters/github
git commit -m "feat(setup): configure GitHub identities interactively"
```

---

### Task 12: Implement process, Docker, migration, storage, and verification actions

**Files:**
- Create: `backend/src/work_frontier/platform/setup/process_actions.py`
- Create: `backend/src/work_frontier/platform/setup/docker_actions.py`
- Test: `backend/tests/platform/setup/test_process_actions.py`
- Test: `backend/tests/platform/setup/test_docker_actions.py`

**Interfaces:**
- Implements `SetupActionRunner`.
- Reuses supported repository commands rather than reproducing their internals.
- Recognized kinds: `write_config`, `docker_compose_up`, `database_migrate`, `storage_verify`, `run_fast_checks`, `certify_standard`.

- [ ] **Step 1: Write failing command mapping tests**

```python
def test_supported_actions_map_to_repository_commands(runner) -> None:
    assert runner.command_for(action("docker_compose_up")) == ["make", "infra-up"]
    assert runner.command_for(action("database_migrate")) == ["make", "migration-smoke"]
    assert runner.command_for(action("storage_verify")) == ["make", "storage-smoke"]
    assert runner.command_for(action("run_fast_checks")) == ["make", "check"]


def test_unknown_action_kind_fails_closed(runner) -> None:
    with pytest.raises(UnsupportedSetupActionError):
        runner.apply(action("shell"))
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest backend/tests/platform/setup/test_process_actions.py \
  backend/tests/platform/setup/test_docker_actions.py -v
```

- [ ] **Step 3: Implement controlled process execution**

Requirements:

- no `shell=True`;
- explicit command allowlist;
- timeout per action;
- process group termination on timeout;
- stdout/stderr streamed to redacted log files;
- returned evidence contains log paths, exit code, duration, and command ID, not raw secrets;
- Compose compensation uses `make infra-down` only for services started by this run.

- [ ] **Step 4: Add port-conflict and timeout coverage**

```bash
uv run pytest backend/tests/platform/setup/test_process_actions.py \
  backend/tests/platform/setup/test_docker_actions.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/work_frontier/platform/setup \
  backend/tests/platform/setup
git commit -m "feat(setup): apply supported local setup actions"
```

---

### Task 13: Compose the SetupService and process-local certification environment

**Files:**
- Create: `backend/src/work_frontier/application/setup/service.py`
- Modify: `backend/src/work_frontier/bootstrap.py`
- Test: `backend/tests/application/setup/test_service.py`
- Test: `backend/tests/test_bootstrap.py`

**Interfaces:**
- `SetupService.detect(profile)`.
- `SetupService.plan(profile, desired)`.
- `SetupService.apply(plan_id)`.
- `SetupService.resume(session_id)`.
- `SetupService.status()`.
- `SetupService.resolve_process_environment(action)`.
- Composition functions:
  - `build_setup_service(paths: WorkFrontierPaths) -> SetupService`
  - `build_setup_application(paths: WorkFrontierPaths) -> FastAPI`.

- [ ] **Step 1: Write failing orchestration tests**

```python
def test_service_detect_plan_apply_round_trip(setup_service) -> None:
    detection = setup_service.detect(SetupProfile.DEVELOPMENT)
    plan = setup_service.plan(
        SetupProfile.DEVELOPMENT,
        desired={"github_repository": "acme/sandbox"},
        expected_snapshot_id=detection.snapshot_id,
    )
    session = setup_service.apply(plan.plan_id)
    assert session.capabilities[0].capability is CapabilityName.LOCAL_RUNTIME


def test_certification_environment_is_process_local_and_not_written(
    setup_service,
    tmp_path,
) -> None:
    environment = setup_service.resolve_process_environment("certify-standard")
    assert "WF_RELEASE_SIGNING_KEY_B64" in environment
    assert not list(tmp_path.rglob(".env"))
    assert "WF_RELEASE_SIGNING_KEY_B64" not in setup_service.config_store.read()[0]
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest backend/tests/application/setup/test_service.py backend/tests/test_bootstrap.py -v
```

- [ ] **Step 3: Implement service orchestration**

The service stores plan records by ID in the journal, revalidates snapshot/config revision immediately before apply, and returns only contract models.

Resolve certification inputs immediately before invoking the existing script and pass them as a child process environment. Do not mutate `os.environ` globally.

- [ ] **Step 4: Replace bootstrap placeholder without breaking its public contract**

Preserve:

```python
HELLO_CONTRACT = "work-frontier"

def hello_contract() -> str:
    return HELLO_CONTRACT
```

Add composition functions beneath it.

- [ ] **Step 5: Verify GREEN and commit**

```bash
uv run pytest backend/tests/application/setup/test_service.py backend/tests/test_bootstrap.py -v
make check-architecture
git add backend/src/work_frontier/application/setup/service.py \
  backend/src/work_frontier/bootstrap.py \
  backend/tests/application/setup/test_service.py backend/tests/test_bootstrap.py
git commit -m "feat(setup): compose the onboarding workflow"
```

---

### Task 14: Implement loopback-only setup FastAPI and one-time sessions

**Files:**
- Create: `backend/src/work_frontier/interfaces/api/setup_models.py`
- Create: `backend/src/work_frontier/interfaces/api/setup_routes.py`
- Create: `backend/src/work_frontier/interfaces/api/setup_app.py`
- Create: `backend/src/work_frontier/interfaces/setup_static/__init__.py`
- Test: `backend/tests/interfaces/api/test_setup_app.py`
- Test: `backend/tests/security/test_setup_session_security.py`

**Interfaces:**
- Setup-only routes:
  - `POST /api/setup/session/exchange`
  - `GET /api/setup/status`
  - `POST /api/setup/detect`
  - `POST /api/setup/plan`
  - `POST /api/setup/apply`
  - `POST /api/setup/resume/{session_id}`
  - `POST /api/setup/secrets`
  - `POST /api/setup/session/close`
- Browser fragment token is exchanged once for an HttpOnly, SameSite=Strict session cookie.

- [ ] **Step 1: Write failing security tests**

```python
def test_setup_app_binds_loopback_and_rejects_remote_forwarding(client) -> None:
    response = client.get(
        "/api/setup/status",
        headers={"Forwarded": "for=203.0.113.8;host=evil.example"},
    )
    assert response.status_code == 403


def test_fragment_token_is_single_use(setup_app_factory) -> None:
    token, client = setup_app_factory()
    first = client.post("/api/setup/session/exchange", json={"token": token})
    second = client.post("/api/setup/session/exchange", json={"token": token})
    assert first.status_code == 204
    assert second.status_code == 401


def test_secret_submission_response_contains_reference_only(authenticated_client) -> None:
    response = authenticated_client.post(
        "/api/setup/secrets",
        json={"namespace": "release", "name": "signing-key", "value": "private-value"},
    )
    assert response.status_code == 201
    assert response.json()["reference"].startswith("keyring://")
    assert "private-value" not in response.text
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest backend/tests/interfaces/api/test_setup_app.py \
  backend/tests/security/test_setup_session_security.py -v
```

- [ ] **Step 3: Implement setup app factory**

`create_setup_app(service, session_manager, static_directory)`:

- excludes normal control-plane routes;
- validates Host, Origin, and forwarded headers;
- sets no-store headers;
- uses synchronizer CSRF token after cookie exchange;
- serves `setup.html` and hashed assets;
- never puts the one-time token into query parameters, logs, or response bodies.

- [ ] **Step 4: Verify GREEN**

```bash
uv run pytest backend/tests/interfaces/api/test_setup_app.py \
  backend/tests/security/test_setup_session_security.py -v
uv run ruff check backend/src/work_frontier/interfaces/api/setup_*.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/work_frontier/interfaces/api/setup_* \
  backend/src/work_frontier/interfaces/setup_static \
  backend/tests/interfaces/api/test_setup_app.py \
  backend/tests/security/test_setup_session_security.py
git commit -m "feat(setup): expose a secure bootstrap API"
```

---

### Task 15: Implement Typer/Rich CLI bootstrap and headless commands

**Files:**
- Create: `backend/src/work_frontier/interfaces/cli.py`
- Test: `backend/tests/interfaces/test_cli.py`

**Interfaces:**
- `main() -> None`.
- Commands:
  - `setup`
  - `setup status`
  - `setup repair`
  - `setup plan --json`
  - `setup apply --plan PATH --non-interactive`
  - `config show --redacted`.

- [ ] **Step 1: Write failing CLI tests with `CliRunner`**

```python
from typer.testing import CliRunner

from work_frontier.interfaces.cli import app

runner = CliRunner()


def test_setup_prints_recovery_url_and_opens_browser(monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", opened.append)
    result = runner.invoke(app, ["setup", "--detach"])
    assert result.exit_code == 0
    assert "http://127.0.0.1:" in result.stdout
    assert opened and opened[0].startswith("http://127.0.0.1:")


def test_headless_status_is_machine_readable_and_redacted() -> None:
    result = runner.invoke(app, ["setup", "status", "--json"])
    assert result.exit_code == 0
    assert '"capabilities"' in result.stdout
    assert "password" not in result.stdout.casefold()
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest backend/tests/interfaces/test_cli.py -v
```

- [ ] **Step 3: Implement CLI**

Use Typer sub-apps and Rich tables. `setup`:

1. creates service and setup app;
2. binds `127.0.0.1` port `0`;
3. creates one-time token;
4. starts Uvicorn in-process;
5. opens `http://127.0.0.1:{port}/setup.html#{token}`;
6. prints only the URL without the fragment as recovery URL;
7. handles Ctrl+C and shutdown cleanly.

`--no-open` suppresses browser launch. `--detach` returns after writing a PID/session record.

- [ ] **Step 4: Verify fish/bash-safe behavior**

Tests must assert no shell syntax is printed as a required step and no environment exports are necessary for Development.

```bash
uv run pytest backend/tests/interfaces/test_cli.py -v
uv run work-frontier --help
uv run work-frontier setup --help
```

- [ ] **Step 5: Commit**

```bash
git add backend/src/work_frontier/interfaces/cli.py backend/tests/interfaces/test_cli.py
git commit -m "feat(setup): add one-command onboarding CLI"
```

---

### Task 16: Build the Setup Center frontend shell and API client

**Files:**
- Modify: `frontend/package.json`
- Modify: `pnpm-lock.yaml`
- Create: `frontend/setup.html`
- Create: `frontend/src/setup/main.tsx`
- Create: `frontend/src/setup/api.ts`
- Create: `frontend/src/setup/form-schema.ts`
- Create: `frontend/src/setup/setup-center.tsx`
- Create: `frontend/src/setup/setup-center.css`
- Test: `frontend/tests/setup/setup-center.test.tsx`
- Test: `frontend/tests/setup/api.test.ts`

**Interfaces:**
- Uses generated `SetupEnvelopeSchema`.
- `SetupApi` methods mirror Task 14 route names.
- No secret value is retained in React Query cache after successful storage.

- [ ] **Step 1: Add frontend dependencies**

Run:

```bash
pnpm --dir frontend add --save-exact react-hook-form @hookform/resolvers
```

- [ ] **Step 2: Write failing shell tests**

```tsx
import { render, screen } from "@testing-library/react"
import { SetupCenter } from "../../src/setup/setup-center"

test("shows four independent capability cards", async () => {
  render(<SetupCenter api={fakeSetupApi.readyDevelopment()} />)
  expect(await screen.findByText("Local runtime")).toBeVisible()
  expect(screen.getByText("GitHub integration")).toBeVisible()
  expect(screen.getByText("Release certification")).toBeVisible()
  expect(screen.getByText("Production cutover")).toBeVisible()
})

test("never renders submitted secret value", async () => {
  const api = fakeSetupApi.withSecretReference()
  render(<SetupCenter api={api} />)
  await userEvent.type(screen.getByLabelText("Signing key"), "private-value")
  await userEvent.click(screen.getByRole("button", { name: "Store securely" }))
  expect(screen.queryByDisplayValue("private-value")).not.toBeInTheDocument()
  expect(document.body.textContent).not.toContain("private-value")
})
```

Add Testing Library only if it is not already present:

```bash
pnpm --dir frontend add --save-dev --save-exact \
  @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom
```

- [ ] **Step 3: Verify RED**

```bash
pnpm --dir frontend vitest run tests/setup/setup-center.test.tsx tests/setup/api.test.ts
```

- [ ] **Step 4: Implement shell and API parsing**

Every API response is parsed through generated Zod. Build an explicit screen state:

```ts
export type SetupScreen =
  | "profile"
  | "environment"
  | "github"
  | "services"
  | "secrets"
  | "certification"
  | "review"
  | "execution"
  | "status"
```

Do not put the one-time token in React state after exchange; read it from `location.hash`, exchange it, then call `history.replaceState` to remove the fragment.

- [ ] **Step 5: Verify GREEN and commit**

```bash
pnpm --dir frontend run typecheck
pnpm --dir frontend vitest run tests/setup
git add frontend/package.json pnpm-lock.yaml frontend/setup.html frontend/src/setup frontend/tests/setup
git commit -m "feat(setup): add Setup Center frontend shell"
```

---

### Task 17: Implement profile, detection, GitHub, services, secrets, release, review, and execution steps

**Files:**
- Create: `frontend/src/setup/profile-step.tsx`
- Create: `frontend/src/setup/environment-step.tsx`
- Create: `frontend/src/setup/github-step.tsx`
- Create: `frontend/src/setup/services-step.tsx`
- Create: `frontend/src/setup/secrets-step.tsx`
- Create: `frontend/src/setup/certification-step.tsx`
- Create: `frontend/src/setup/review-step.tsx`
- Create: `frontend/src/setup/execution-step.tsx`
- Test: `frontend/tests/setup/steps.test.tsx`
- Test: `frontend/tests/setup/plan-review.test.tsx`

**Interfaces:**
- Form submissions send desired non-secret config and secret values separately.
- Review displays `will create`, `will start`, `will run`, and `will not do`.
- Apply requires explicit confirmation for high-risk and remote mutation actions.

- [ ] **Step 1: Write failing user-flow tests**

Cover:

- Development profile hides release/cutover requirements.
- Production shows GitHub App and external service fields.
- `repairable`, `needs_input`, and `blocked` checks have distinct copy and actions.
- Remote GitHub mutation test requires confirmation.
- Plan review shows reversibility and dependencies.
- Execution resume does not re-run verified steps.

- [ ] **Step 2: Verify RED**

```bash
pnpm --dir frontend vitest run tests/setup/steps.test.tsx tests/setup/plan-review.test.tsx
```

- [ ] **Step 3: Implement forms with React Hook Form and Zod resolver**

Use one schema per step in `form-schema.ts`; do not duplicate backend constraints manually when generated Zod already owns them.

After secret submit:

```ts
resetField("value", { defaultValue: "" })
queryClient.removeQueries({ queryKey: ["setup-secret-draft"] })
```

- [ ] **Step 4: Add accessibility behavior**

- one `<h1>`;
- step navigation with `aria-current="step"`;
- status changes in a polite live region;
- error summary links to fields;
- focus moves to the first invalid field;
- no color-only status communication;
- all actions keyboard reachable.

- [ ] **Step 5: Verify GREEN and commit**

```bash
pnpm --dir frontend vitest run tests/setup
pnpm --dir frontend run check
git add frontend/src/setup frontend/tests/setup
git commit -m "feat(setup): implement guided onboarding steps"
```

---

### Task 18: Package bootstrap UI assets and enforce drift

**Files:**
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/package.json`
- Create: `scripts/build_setup_assets.mjs`
- Create: `scripts/check_setup_assets.py`
- Generate: `backend/src/work_frontier/interfaces/setup_static/setup.html`
- Generate: `backend/src/work_frontier/interfaces/setup_static/assets/*`
- Modify: `pyproject.toml`
- Modify: `Makefile`
- Test: `backend/tests/test_setup_asset_drift.py`

**Interfaces:**
- `pnpm --dir frontend run build:setup`.
- `python scripts/check_setup_assets.py`.
- `make check-setup-assets`.
- Setup-only FastAPI resolves assets through `importlib.resources`.

- [ ] **Step 1: Write failing drift test**

```python
from scripts.check_setup_assets import assets_are_current


def test_packaged_setup_assets_match_frontend_source() -> None:
    assert assets_are_current()
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest backend/tests/test_setup_asset_drift.py -v
```

- [ ] **Step 3: Configure dedicated Vite input and deterministic output**

`vite.config.ts` must include a `setup` build entry. Output names use content hashes. `build_setup_assets.mjs` builds into a temporary directory, normalizes the HTML entry path, and atomically replaces `interfaces/setup_static`.

Add package scripts:

```json
"build:setup": "vite build --mode setup",
"check:setup-assets": "python ../scripts/check_setup_assets.py"
```

- [ ] **Step 4: Add Make targets**

```make
build-setup-assets: ## Build packaged browser setup assets
	pnpm --dir frontend run build:setup

check-setup-assets: ## Fail when packaged setup assets drift
	uv run python scripts/check_setup_assets.py
```

Add `check-setup-assets` to `check-static`.

- [ ] **Step 5: Build and verify without a frontend dev server**

```bash
make build-setup-assets
make check-setup-assets
uv build
python -c 'from importlib.resources import files; print(files("work_frontier.interfaces.setup_static").joinpath("setup.html").is_file())'
```

Expected: `True`.

- [ ] **Step 6: Commit**

```bash
git add frontend/vite.config.ts frontend/package.json scripts/build_setup_assets.mjs \
  scripts/check_setup_assets.py backend/src/work_frontier/interfaces/setup_static \
  pyproject.toml Makefile backend/tests/test_setup_asset_drift.py
git commit -m "build(setup): package first-run browser assets"
```

---

### Task 19: Integrate persistent Setup Center into authenticated Control Room

**Files:**
- Modify: `backend/src/work_frontier/interfaces/api/app.py`
- Modify: `backend/src/work_frontier/interfaces/api/setup_routes.py`
- Modify: `frontend/src/control-room/app.tsx`
- Delete: `frontend/src/control-room/onboarding.ts`
- Modify: `frontend/src/control-room/shell.tsx`
- Test: `backend/tests/interfaces/api/test_persistent_setup_routes.py`
- Test: `frontend/tests/control-room/setup-center-navigation.test.tsx`

**Interfaces:**
- Normal API routes require operator/admin authorization and tenant/workspace context.
- Reuses `SetupService`; does not reuse one-time bootstrap session auth.
- Control Room navigation includes `setup`.

- [ ] **Step 1: Write failing authorization tests**

```python
def test_viewer_cannot_apply_setup_plan(viewer_client) -> None:
    response = viewer_client.post("/setup/plans/plan-1/apply")
    assert response.status_code == 403


def test_operator_can_read_setup_status(operator_client) -> None:
    response = operator_client.get("/setup/status")
    assert response.status_code == 200
```

- [ ] **Step 2: Write failing frontend navigation test**

Assert Setup Center remains available after runtime readiness and the old seeded three-button onboarding gate is absent.

- [ ] **Step 3: Verify RED**

```bash
uv run pytest backend/tests/interfaces/api/test_persistent_setup_routes.py -v
pnpm --dir frontend vitest run tests/control-room/setup-center-navigation.test.tsx
```

- [ ] **Step 4: Implement persistent routes and navigation**

Mount authenticated setup routes under `/setup`. Keep setup bootstrap routes in the separate app factory.

Replace `isAuthoritative(onboarding)` with server-derived readiness; Control Room can render when Local Runtime is ready even when Release Certification and Cutover are pending.

- [ ] **Step 5: Verify GREEN and commit**

```bash
uv run pytest backend/tests/interfaces/api/test_persistent_setup_routes.py -v
pnpm --dir frontend vitest run tests/control-room/setup-center-navigation.test.tsx
make check-architecture
git add backend/src/work_frontier/interfaces/api frontend/src/control-room frontend/tests/control-room
git commit -m "feat(setup): keep Setup Center available after onboarding"
```

---

### Task 20: Add end-to-end, security, accessibility, resume, and headless certification

**Files:**
- Create: `frontend/tests/product/setup-development.spec.ts`
- Create: `frontend/tests/product/setup-production.spec.ts`
- Create: `frontend/tests/accessibility/setup-center.spec.ts`
- Create: `backend/tests/product/test_setup_resume.py`
- Create: `backend/tests/security/test_setup_secret_leakage.py`
- Create: `backend/tests/interfaces/test_setup_headless.py`
- Modify: `frontend/package.json`
- Modify: `Makefile`

**Interfaces:**
- Adds `test:setup`.
- Adds `make test-setup`.
- All browser tests use fake GitHub and controlled local process adapters; no real credentials.

- [ ] **Step 1: Add RED end-to-end scenarios**

Development happy path:

1. run bootstrap setup app;
2. choose Development;
3. detect environment;
4. choose sandbox;
5. review plan;
6. apply;
7. verify Local Runtime and GitHub Integration ready;
8. verify Release and Cutover not required.

Failure paths:

- Docker unavailable;
- port conflict;
- `gh` unauthenticated;
- GitHub write permission absent;
- browser closes during apply and resumes;
- stale plan rejected;
- secret never appears in DOM, API capture, logs, config, or SQLite;
- keyboard-only completion;
- axe has zero WCAG 2.2 AA violations.

- [ ] **Step 2: Add scripts**

```json
"test:setup": "vitest run tests/setup && playwright test tests/product/setup-*.spec.ts tests/accessibility/setup-center.spec.ts"
```

```make
test-setup: ## Run setup unit, product, security, and accessibility suites
	uv run pytest backend/tests/application/setup backend/tests/platform/configuration \
	  backend/tests/platform/secrets backend/tests/platform/setup \
	  backend/tests/interfaces/test_cli.py backend/tests/interfaces/test_setup_headless.py \
	  backend/tests/product/test_setup_resume.py \
	  backend/tests/security/test_setup_session_security.py \
	  backend/tests/security/test_setup_secret_leakage.py
	pnpm --dir frontend run test:setup
```

- [ ] **Step 3: Run RED and implement only missing seams**

```bash
make test-setup
```

Expected: failures identify unfinished product seams, not missing test infrastructure.

- [ ] **Step 4: Reach GREEN**

```bash
make test-setup
```

Expected: all setup suites pass.

- [ ] **Step 5: Commit**

```bash
git add backend/tests frontend/tests frontend/package.json Makefile
git commit -m "test(setup): certify onboarding and repair journeys"
```

---

### Task 21: Update golden-path documentation and redacted diagnostics

**Files:**
- Modify: `README.md`
- Modify: `docs/development.md`
- Create: `docs/operations/setup-center.md`
- Test: `backend/tests/docs/test_setup_documentation.py`

**Interfaces:**
- Development quick start becomes `uv run work-frontier setup`.
- Advanced manual Make commands remain documented.
- Production docs explain secret references, process-local certification inputs, resume, repair, diagnostics, and non-goals.

- [ ] **Step 1: Write failing documentation assertions**

```python
from pathlib import Path


def test_quick_start_uses_interactive_setup_without_exports() -> None:
    readme = Path("README.md").read_text()
    assert "uv run work-frontier setup" in readme
    assert "export WF_RELEASE_SIGNING_KEY_B64" not in readme


def test_setup_operations_doc_explains_independent_readiness() -> None:
    content = Path("docs/operations/setup-center.md").read_text()
    for heading in (
        "Local Runtime Ready",
        "GitHub Integration Ready",
        "Release Certification Ready",
        "Production Cutover Ready",
    ):
        assert heading in content
```

- [ ] **Step 2: Verify RED**

```bash
uv run pytest backend/tests/docs/test_setup_documentation.py -v
```

- [ ] **Step 3: Update docs**

Include:

```bash
uv run work-frontier setup
uv run work-frontier setup status
uv run work-frontier setup repair
```

Manual paths remain:

```bash
make doctor
make bootstrap
make check
make verify
```

Explain that certification remains long-running and exact-revision; Setup Center prepares and invokes it but does not shorten the soak or approve cutover.

- [ ] **Step 4: Verify GREEN and commit**

```bash
uv run pytest backend/tests/docs/test_setup_documentation.py -v
git add README.md docs/development.md docs/operations/setup-center.md \
  backend/tests/docs/test_setup_documentation.py
git commit -m "docs(setup): document the interactive golden path"
```

---

### Task 22: Final repository verification and implementation evidence

**Files:**
- Modify only if required by deterministic generators:
  - `docs/anatomy/_manifest.json`
  - generated contracts
  - packaged setup assets
  - lockfiles

**Interfaces:**
- No new product behavior.
- Produces a clean implementation commit suitable for later exact-revision certification.

- [ ] **Step 1: Regenerate deterministic outputs**

```bash
make generate-contracts
make build-setup-assets
make generate-harness-registry
```

Expected: only intended generated artifacts change.

- [ ] **Step 2: Run focused setup verification**

```bash
make test-setup
make check-setup-assets
make check-contracts
make check-architecture
```

Expected: pass.

- [ ] **Step 3: Run full fast verification**

```bash
make check
```

Expected: pass with Ruff, formatting, basedpyright, Biome, TypeScript, Vitest, contracts, registry, architecture, anatomy, and setup asset drift green.

- [ ] **Step 4: Run infrastructure verification**

```bash
make verify
```

Expected: pass; PostgreSQL and MinIO are always cleaned up by the Make trap.

- [ ] **Step 5: Build and inspect distribution**

```bash
uv build
python -m zipfile -l dist/*.whl | grep work_frontier/interfaces/setup_static/setup.html
```

Expected: packaged setup HTML and hashed assets are in the wheel.

- [ ] **Step 6: Verify clean diff and commit any deterministic output**

```bash
git diff --check
git status --short
git add -A
git commit -m "chore(setup): finalize generated onboarding artifacts"
```

Skip the commit if there are no changes.

- [ ] **Step 7: Record truthful final status**

Report:

- exact implementation SHA;
- commands actually run;
- tests not run;
- no claim that Standard ReleaseCertification, 72-hour soak, or production cutover completed unless their registered exact-revision harnesses actually passed.

---

## Dependency Order

```text
1 contracts/dependencies
  → 2 generated contracts
  → 3 ports/fakes
  → 4 config store
  → 5 secrets
  → 6 journal
  → 7 detection
  → 8 planning
  → 9 execution
  → 10 readiness
  → 11 GitHub adapters
  → 12 action runners
  → 13 service/composition
  → 14 setup API
  → 15 CLI
  → 16 frontend shell
  → 17 frontend steps
  → 18 static packaging
  → 19 persistent Control Room
  → 20 end-to-end certification
  → 21 docs
  → 22 final verification
```

Tasks 4, 5, and 6 may run in parallel after Task 3. Tasks 10, 11, and 12 may run in parallel after Tasks 7–9 establish their consumed contracts. Frontend Tasks 16–17 may begin after Task 2 and use a fake API, but Task 20 must wait for Tasks 13–19.

## Narrow Iteration Commands

```bash
uv run pytest backend/tests/contracts/test_setup_contracts.py -v
uv run pytest backend/tests/application/setup -v
uv run pytest backend/tests/platform/configuration -v
uv run pytest backend/tests/platform/secrets -v
uv run pytest backend/tests/platform/setup -v
uv run pytest backend/tests/interfaces/test_cli.py -v
pnpm --dir frontend vitest run tests/setup
pnpm --dir frontend run typecheck
make check-architecture
make check-contracts
make check-setup-assets
```

## Final Verification Profile

```bash
make test-setup
make check
make verify
uv build
git diff --check
git status --short
```

For later release certification only, after committing and obtaining a clean exact revision:

```bash
uv run work-frontier setup
# Prepare Release Certification in Setup Center.
make certify-standard
```

The Setup Center may invoke this final command with a process-local resolved environment, but it must not make a dirty tree certifiable or substitute placeholders for real credentials and approvals.

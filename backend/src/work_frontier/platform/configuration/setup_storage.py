"""Atomic local setup configuration and transactional SQLite journal."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, cast

import tomlkit
from platformdirs import PlatformDirs

from work_frontier.application.ports.setup import JournalAction, JournalSession

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Mapping
from work_frontier.contracts.setup import ActionState, SetupPlan

_EMPTY_CONFIG: Final = "schema_version = 1\n"
_SECRET_MARKERS: Final = ("password", "token", "private_key", "private-key", "secret")


class ConfigurationConflictError(RuntimeError):
    """Signal a compare-and-swap conflict."""


class SetupLockConflictError(RuntimeError):
    """Signal another setup session holding the installation writer lock."""


@dataclass(frozen=True, slots=True)
class SetupPaths:
    """OS-resolved setup paths."""

    config_file: Path
    journal_file: Path
    log_directory: Path

    @classmethod
    def from_root(cls, root: Path) -> SetupPaths:
        """Create deterministic paths beneath an injected root."""
        return cls(
            config_file=root / "config" / "config.toml",
            journal_file=root / "state" / "setup.sqlite3",
            log_directory=root / "logs",
        )

    @classmethod
    def for_user(cls) -> SetupPaths:
        """Return platform-appropriate per-user paths."""
        directories = PlatformDirs("work-frontier", "Work Frontier")
        return cls(
            config_file=directories.user_config_path / "config.toml",
            journal_file=directories.user_state_path / "setup.sqlite3",
            log_directory=directories.user_log_path,
        )


class TomlConfigurationStore:
    """Small versioned TOML store with atomic compare-and-swap writes."""

    _paths: SetupPaths

    def __init__(self, paths: SetupPaths) -> None:
        """Bind resolved configuration paths."""
        self._paths = paths

    def read(self) -> tuple[dict[str, str | int | bool], str]:
        """Read current non-secret configuration and its content revision."""
        content = self._read_content()
        return _parse_simple_toml(content), _revision(content)

    def compare_and_swap(
        self,
        expected_revision: str,
        document: dict[str, str | int | bool],
    ) -> str:
        """Atomically replace configuration when the expected revision matches."""
        current = self._read_content()
        if _revision(current) != expected_revision:
            message = "configuration changed after it was read"
            raise ConfigurationConflictError(message)
        _validate_document(document)
        content = _render_simple_toml(document)
        self._paths.config_file.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=self._paths.config_file.parent,
            prefix=".config.toml.",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                _ = handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            _ = temporary.replace(self._paths.config_file)
        finally:
            temporary.unlink(missing_ok=True)
        return _revision(content)

    def _read_content(self) -> str:
        if not self._paths.config_file.exists():
            return _EMPTY_CONFIG
        return self._paths.config_file.read_text(encoding="utf-8")


class SqliteSetupJournal:
    """Durable append-only setup action journal."""

    _path: Path

    def __init__(self, path: Path) -> None:
        """Initialize the journal schema at the injected path."""
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            _ = connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS setup_plans (
                    plan_id TEXT PRIMARY KEY,
                    plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS setup_sessions (
                    session_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS setup_installation_locks (
                    installation_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    acquired_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS setup_action_transitions (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    redacted_payload_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES setup_sessions(session_id)
                );
                """
            )

    def acquire_installation_lock(
        self,
        installation_id: str,
        session_id: str,
    ) -> None:
        """Acquire the single-writer installation lock idempotently."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT session_id FROM setup_installation_locks "
                "WHERE installation_id = ?",
                (installation_id,),
            ).fetchone()
            if row is not None and str(row[0]) != session_id:
                message = "another setup session holds the installation writer lock"
                raise SetupLockConflictError(message)
            _ = connection.execute(
                "INSERT OR REPLACE INTO setup_installation_locks VALUES (?, ?, ?)",
                (installation_id, session_id, now),
            )

    def release_installation_lock(
        self,
        installation_id: str,
        session_id: str,
    ) -> None:
        """Release an installation lock only for its owning session."""
        with self._connect() as connection:
            _ = connection.execute(
                "DELETE FROM setup_installation_locks "
                "WHERE installation_id = ? AND session_id = ?",
                (installation_id, session_id),
            )

    def save_plan(self, plan: SetupPlan) -> None:
        """Persist a reviewed secret-free plan for cross-process resume."""
        serialized = plan.model_dump_json()
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            _ = connection.execute(
                "INSERT OR REPLACE INTO setup_plans VALUES (?, ?, ?)",
                (plan.plan_id, serialized, now),
            )

    def load_plan(self, plan_id: str) -> SetupPlan:
        """Load a reviewed plan by stable identifier."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT plan_json FROM setup_plans WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
        if row is None:
            raise KeyError(plan_id)
        return SetupPlan.model_validate_json(str(row[0]))

    def latest_session_id(self) -> str | None:
        """Return the most recently updated setup session, when one exists."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT session_id FROM setup_sessions ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        return None if row is None else str(row[0])

    def create_session(self, session_id: str, plan_id: str) -> None:
        """Create a setup session idempotently."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            _ = connection.execute(
                "INSERT OR IGNORE INTO setup_sessions VALUES (?, ?, ?, ?)",
                (session_id, plan_id, now, now),
            )

    def record_transition(
        self,
        session_id: str,
        action_id: str,
        state: ActionState,
        payload: dict[str, str | int | bool | None],
    ) -> None:
        """Append one redacted state transition."""
        _validate_document(payload)
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            _ = connection.execute(
                """INSERT INTO setup_action_transitions
                (session_id, action_id, state, redacted_payload_json, recorded_at)
                VALUES (?, ?, ?, ?, ?)""",
                (session_id, action_id, state.value, serialized, now),
            )
            _ = connection.execute(
                "UPDATE setup_sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )

    def load_session(self, session_id: str) -> JournalSession:
        """Rebuild latest action states for a setup session."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT plan_id FROM setup_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if row is None:
                raise KeyError(session_id)
            transitions = connection.execute(
                """SELECT action_id, state, redacted_payload_json
                FROM setup_action_transitions
                WHERE session_id = ? ORDER BY sequence""",
                (session_id,),
            ).fetchall()
        actions: dict[str, JournalAction] = {}
        for action_id, state, payload_json in transitions:
            raw = json.loads(payload_json)
            actions[str(action_id)] = JournalAction(
                state=ActionState(str(state)),
                payload=MappingProxyType(dict(raw)),
            )
        return JournalSession(
            session_id=session_id,
            plan_id=str(row[0]),
            actions=MappingProxyType(actions),
        )

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path)
        try:
            _ = connection.execute("PRAGMA foreign_keys = ON")
            _ = connection.execute("PRAGMA journal_mode = WAL").fetchone()
            yield connection
            connection.commit()
        finally:
            connection.close()


def _revision(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _validate_document(document: Mapping[str, object]) -> None:
    for key, value in document.items():
        normalized = key.casefold().replace("-", "_")
        if any(marker.replace("-", "_") in normalized for marker in _SECRET_MARKERS):
            if isinstance(value, str) and value.startswith(
                ("keyring://", "env://", "gh-cli://")
            ):
                continue
            message = (
                f"secret-bearing field {key} must be a secret reference, not plaintext"
            )
            raise ValueError(message)


def _parse_simple_toml(content: str) -> dict[str, str | int | bool]:
    parsed = cast("Mapping[str, object]", tomlkit.parse(content).unwrap())
    return {
        str(key): value
        for key, value in parsed.items()
        if isinstance(value, (str, int, bool))
    }


def _render_simple_toml(document: dict[str, str | int | bool]) -> str:
    normalized: dict[str, object] = {"schema_version": 1, **document}
    ordered = {key: normalized[key] for key in sorted(normalized)}
    dumps = cast("Callable[[Mapping[str, object]], str]", tomlkit.dumps)
    return dumps(ordered)

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from work_frontier.contracts.setup import ActionState
from work_frontier.platform.configuration.setup_storage import (
    ConfigurationConflictError,
    SetupLockConflictError,
    SetupPaths,
    SqliteSetupJournal,
    TomlConfigurationStore,
)


def test_paths_separate_config_state_and_logs(tmp_path: Path) -> None:
    paths = SetupPaths.from_root(tmp_path)
    assert paths.config_file == tmp_path / "config" / "config.toml"
    assert paths.journal_file == tmp_path / "state" / "setup.sqlite3"
    assert paths.log_directory == tmp_path / "logs"


def test_configuration_store_is_atomic_and_compare_and_swap(tmp_path: Path) -> None:
    store = TomlConfigurationStore(SetupPaths.from_root(tmp_path))
    document, revision = store.read()
    document["profile"] = "development"
    new_revision = store.compare_and_swap(revision, document)
    assert new_revision != revision
    with pytest.raises(ConfigurationConflictError):
        _ = store.compare_and_swap(revision, document)


def test_configuration_store_rejects_plaintext_secrets(tmp_path: Path) -> None:
    store = TomlConfigurationStore(SetupPaths.from_root(tmp_path))
    document, revision = store.read()
    document["github_token"] = "plain" + "text"
    with pytest.raises(ValueError, match="secret reference"):
        _ = store.compare_and_swap(revision, document)


def test_journal_resumes_transitions_and_rejects_secret_payloads(
    tmp_path: Path,
) -> None:
    journal = SqliteSetupJournal(tmp_path / "setup.sqlite3")
    journal.create_session("session-1", "plan-1")
    journal.record_transition("session-1", "config.write", ActionState.RUNNING, {})
    journal.record_transition(
        "session-1",
        "config.write",
        ActionState.VERIFIED,
        {"path": "config.toml"},
    )
    session = journal.load_session("session-1")
    assert session.actions["config.write"].state is ActionState.VERIFIED
    with pytest.raises(ValueError, match="secret-bearing"):
        journal.record_transition(
            "session-1", "bad", ActionState.FAILED, {"password": "leak"}
        )


def test_setup_journal_allows_only_one_installation_writer(tmp_path: Path) -> None:
    journal = SqliteSetupJournal(tmp_path / "setup.sqlite3")
    journal.acquire_installation_lock("default", "session-a")
    with pytest.raises(SetupLockConflictError):
        journal.acquire_installation_lock("default", "session-b")
    journal.release_installation_lock("default", "session-a")
    journal.acquire_installation_lock("default", "session-b")


def test_runtime_settings_accept_injected_state_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WF_SETUP_STATE_ROOT", str(tmp_path / "custom-state"))
    from work_frontier.platform.configuration.settings import SetupRuntimeSettings

    settings = SetupRuntimeSettings()

    assert settings.state_root == tmp_path / "custom-state"
    assert str(settings.github_api_url) == "https://api.github.com/"

from __future__ import annotations

import os

import pytest

from work_frontier.contracts.setup import SecretReference
from work_frontier.platform.secrets.stores import (
    EnvironmentSecretStore,
    KeyringSecretStore,
)


class MemoryBackend:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        _ = self.values.pop((service, username), None)


def test_keyring_store_returns_reference_and_redacted_metadata() -> None:
    store = KeyringSecretStore(MemoryBackend())
    reference = store.store(namespace="release", name="signing-key", value="raw-key")
    assert reference.uri == "keyring://work-frontier/release/signing-key"
    assert store.resolve(reference) == "raw-key"
    metadata = store.metadata(reference)
    assert metadata["present"] is True
    assert "raw-key" not in repr(metadata)


def test_environment_store_is_read_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WF_DATABASE_PASSWORD", "db-secret")
    store = EnvironmentSecretStore(os.environ)
    reference = SecretReference(uri="env://WF_DATABASE_PASSWORD")
    assert store.resolve(reference) == "db-secret"
    with pytest.raises(PermissionError):
        _ = store.store(namespace="x", name="y", value="z")

"""OS-keyring and environment-backed secret reference providers."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, ClassVar, Protocol

import keyring

if TYPE_CHECKING:
    from collections.abc import Mapping

from work_frontier.contracts.setup import SecretReference


class KeyringBackend(Protocol):
    """Minimal keyring-compatible backend contract."""

    def set_password(self, service: str, username: str, password: str) -> None:
        """Store a password in the active backend."""
        ...

    def get_password(self, service: str, username: str) -> str | None:
        """Return a stored password when present."""
        ...

    def delete_password(self, service: str, username: str) -> None:
        """Delete one stored password."""
        ...


class _SystemKeyringBackend:
    """Adapt the keyring module to the internal protocol."""

    def set_password(self, service: str, username: str, password: str) -> None:
        """Store one secret in the active OS keyring."""
        keyring.set_password(service, username, password)

    def get_password(self, service: str, username: str) -> str | None:
        """Read one secret from the active OS keyring."""
        return keyring.get_password(service, username)

    def delete_password(self, service: str, username: str) -> None:
        """Delete one secret from the active OS keyring."""
        keyring.delete_password(service, username)


class SecretStoreUnavailableError(RuntimeError):
    """Signal that the configured secret provider is unavailable."""


class KeyringSecretStore:
    """Store secrets behind opaque keyring references."""

    _SERVICE: ClassVar[str] = "work-frontier"

    def __init__(self, backend: KeyringBackend) -> None:
        """Bind a keyring-compatible backend."""
        self._backend: KeyringBackend = backend

    @classmethod
    def from_system(cls) -> KeyringSecretStore:
        """Create a keyring store when the optional package is installed."""
        return cls(_SystemKeyringBackend())

    def store(self, *, namespace: str, name: str, value: str) -> SecretReference:
        """Store a value and return only its opaque reference."""
        username = _username(namespace, name)
        try:
            self._backend.set_password(self._SERVICE, username, value)
        except Exception as exc:
            message = "OS keyring could not store the requested secret"
            raise SecretStoreUnavailableError(message) from exc
        return SecretReference(uri=f"keyring://{self._SERVICE}/{username}")

    def resolve(self, reference: SecretReference) -> str:
        """Resolve a keyring reference inside an execution boundary."""
        username = _keyring_username(reference)
        try:
            value = self._backend.get_password(self._SERVICE, username)
        except Exception as exc:
            message = "OS keyring could not resolve the requested secret"
            raise SecretStoreUnavailableError(message) from exc
        if value is None:
            raise KeyError(reference.uri)
        return value

    def metadata(self, reference: SecretReference) -> dict[str, str | bool]:
        """Return redacted provider metadata."""
        value = self.resolve(reference)
        return {
            "provider": "keyring",
            "reference": reference.uri,
            "present": True,
            "fingerprint": hashlib.sha256(value.encode()).hexdigest()[:16],
        }

    def delete(self, reference: SecretReference) -> None:
        """Delete a keyring entry."""
        self._backend.delete_password(self._SERVICE, _keyring_username(reference))


class EnvironmentSecretStore:
    """Read-only secret references resolved from an injected environment."""

    def __init__(self, environment: Mapping[str, str]) -> None:
        """Bind an externally owned environment mapping."""
        self._environment: Mapping[str, str] = environment

    def store(self, *, namespace: str, name: str, value: str) -> SecretReference:
        """Reject writes because environment ownership is external."""
        del namespace, name, value
        message = "environment secret references are read-only"
        raise PermissionError(message)

    def resolve(self, reference: SecretReference) -> str:
        """Resolve an environment reference."""
        if reference.scheme != "env":
            raise ValueError(reference.uri)
        name = reference.uri.removeprefix("env://")
        value = self._environment.get(name)
        if value is None:
            raise KeyError(name)
        return value

    def metadata(self, reference: SecretReference) -> dict[str, str | bool]:
        """Return presence metadata without reading a reusable value."""
        name = reference.uri.removeprefix("env://")
        return {
            "provider": "environment",
            "reference": reference.uri,
            "present": name in self._environment,
        }

    def delete(self, reference: SecretReference) -> None:
        """Reject deletion because environment ownership is external."""
        del reference
        message = "environment secret references are read-only"
        raise PermissionError(message)


def _username(namespace: str, name: str) -> str:
    normalized = f"{namespace.strip('/')}/{name.strip('/')}"
    if not normalized or ".." in normalized.split("/"):
        message = "invalid keyring namespace or name"
        raise ValueError(message)
    return normalized


def _keyring_username(reference: SecretReference) -> str:
    prefix = "keyring://work-frontier/"
    if not reference.uri.startswith(prefix):
        raise ValueError(reference.uri)
    return reference.uri.removeprefix(prefix)


class CompositeSecretResolver:
    """Resolve environment and OS-keyring references without exposing values."""

    def __init__(self, environment: Mapping[str, str]) -> None:
        """Bind an externally owned environment mapping."""
        self._environment: EnvironmentSecretStore = EnvironmentSecretStore(environment)
        self._keyring: KeyringSecretStore | None = None

    def resolve(self, reference: SecretReference) -> str:
        """Resolve a supported reference only at an execution boundary."""
        if reference.scheme == "env":
            return self._environment.resolve(reference)
        if reference.scheme == "keyring":
            if self._keyring is None:
                self._keyring = KeyringSecretStore.from_system()
            return self._keyring.resolve(reference)
        message = f"unsupported executable secret reference: {reference.scheme}"
        raise ValueError(message)

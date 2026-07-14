"""Executable composition root for Work Frontier command-line interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING

from work_frontier.bootstrap import build_setup_service
from work_frontier.interfaces.cli.setup import app, configure
from work_frontier.platform.secrets.stores import (
    KeyringSecretStore,
    SecretStoreUnavailableError,
)

if TYPE_CHECKING:
    from work_frontier.interfaces.api.setup_app import SecretWriter


def main() -> None:
    """Compose CLI dependencies and execute the command surface."""
    configure(
        setup_service_factory=build_setup_service,
        secret_store_factory=_create_secret_store,
    )
    app()


def _create_secret_store() -> SecretWriter | None:
    """Create the optional OS keyring writer without exposing it to interfaces."""
    try:
        return KeyringSecretStore.from_system()
    except SecretStoreUnavailableError:
        return None

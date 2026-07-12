"""Unit tests for ``scripts.migration_smoke`` failure classification.

These tests guard against false-pass scenarios where the upgrade fails for a
reason unrelated to the injected failing revision. The smoke script is
exercised end-to-end only inside CI against a real Postgres, so we test the
classification helper directly to keep the regression coverage hermetic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
MODULE_PATH = SCRIPTS_DIR / "migration_smoke.py"

_SPEC = importlib.util.spec_from_file_location("migration_smoke", MODULE_PATH)
assert _SPEC is not None
assert _SPEC.loader is not None
migration_smoke = importlib.util.module_from_spec(_SPEC)  # type: ignore[assignment]
sys.modules["migration_smoke"] = migration_smoke
_ = _SPEC.loader.exec_module(migration_smoke)

FailingRevisionUnexpectedError = migration_smoke.FailingRevisionUnexpectedError
MigrationSmokeError = migration_smoke.MigrationSmokeError
_is_failing_revision_error = migration_smoke._is_failing_revision_error  # noqa: SLF001
install_failing_revision = migration_smoke.install_failing_revision
remove_failing_revision = migration_smoke.remove_failing_revision


def test_failing_revision_error_classifier_when_revision_message_present() -> None:
    # Given an exception whose message includes the injected marker and a
    # PostgreSQL syntax error in the cause chain
    inner = RuntimeError(
        '(psycopg.errors.SyntaxError) syntax error at or near "THIS"\n'
        "LINE 1: THIS IS INVALID SQL FROM ALEMBIC REVISION\n"
    )
    outer = Exception("alembic.util.exc.CommandError: upgrade head failed")
    outer.__cause__ = inner

    # When the classifier inspects it
    classified = _is_failing_revision_error(outer)

    # Then it confirms the failure traces back to the injected revision
    assert classified is True


def test_failing_revision_error_classifier_rejects_unrelated_failure() -> None:
    # Given an Alembic config error that has nothing to do with the injected
    # SQL (e.g. bad connection string or revision import)
    unrelated = Exception(
        "alembic.util.exc.CommandError: No module named '0002_failing_revision_probe'"
    )

    # When the classifier inspects it
    classified = _is_failing_revision_error(unrelated)

    # Then it returns False so the smoke script can fail loudly
    assert classified is False


def test_failing_revision_error_classifier_rejects_empty_message() -> None:
    # Given an exception with no message (should never happen but guard anyway)
    empty = Exception("")

    # When the classifier inspects it
    classified = _is_failing_revision_error(empty)

    # Then it returns False
    assert classified is False


def test_failing_revision_install_round_trip(tmp_path: Path) -> None:
    # Given a clean versions directory
    original_versions_dir = migration_smoke.VERSIONS_DIR
    original_failing_path = migration_smoke.FAILING_REVISION_PATH
    new_failing_path = tmp_path / f"{migration_smoke.FAILING_REVISION_ID}.py"
    object.__setattr__(migration_smoke, "VERSIONS_DIR", tmp_path)
    object.__setattr__(migration_smoke, "FAILING_REVISION_PATH", new_failing_path)
    try:
        # When the failing revision is installed
        installed: Path = install_failing_revision()

        # Then the file exists with the expected marker
        assert installed.exists()
        content = installed.read_text(encoding="utf-8")
        assert "INVALID SQL FROM ALEMBIC REVISION" in content

        # And removing it cleans up
        remove_failing_revision()
        assert not installed.exists()
    finally:
        object.__setattr__(migration_smoke, "VERSIONS_DIR", original_versions_dir)
        object.__setattr__(
            migration_smoke, "FAILING_REVISION_PATH", original_failing_path
        )


def test_failing_revision_unexpected_error_inherits_migration_error() -> None:
    # Given the unexpected-error class
    # When it is instantiated with a captured cause
    err: FailingRevisionUnexpectedError = FailingRevisionUnexpectedError(
        RuntimeError("boom")
    )

    # Then it remains catchable as a MigrationSmokeError so the main flow
    # can produce a fail record and clean evidence output
    assert isinstance(err, MigrationSmokeError)
    assert "non-revision error" in str(err)


def test_failing_revision_unexpected_error_preserves_cause() -> None:
    # Given a wrapping migration smoke error and an underlying cause
    cause = RuntimeError("connection refused")
    with pytest.raises(FailingRevisionUnexpectedError) as excinfo:
        raise FailingRevisionUnexpectedError(cause) from cause

    # When __cause__ is read
    # Then it is preserved for evidence and debugging
    caught: FailingRevisionUnexpectedError = excinfo.value
    assert caught.__cause__ is cause
    # And the cause attribute exposes the original for callers
    assert caught.cause is cause

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from work_frontier.domain.emergency import (
    BreakGlassError,
    BreakGlassRequest,
    RetentionSubject,
    anonymize_subject,
    authorize_break_glass,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _request(  # noqa: PLR0913 - explicit safety inputs are independently tested
    *,
    permission: str = "credential.rotate",
    reason: str = "production credential compromise response",
    reauthenticated: bool = True,
    mfa_verified: bool = True,
    confirmed: bool = True,
    prior_invocations: tuple[datetime, ...] = (),
) -> BreakGlassRequest:
    base = BreakGlassRequest(
        actor="admin-1",
        permission="credential.rotate",
        reason="production credential compromise response",
        reauthenticated=True,
        mfa_verified=True,
        confirmed=True,
        requested_at=NOW,
        prior_invocations=(),
    )
    return replace(
        base,
        permission=permission,
        reason=reason,
        reauthenticated=reauthenticated,
        mfa_verified=mfa_verified,
        confirmed=confirmed,
        prior_invocations=prior_invocations,
    )


def test_break_glass_requires_strong_reauth_reason_and_confirmation() -> None:
    with pytest.raises(BreakGlassError, match="strong reauthentication"):
        _ = authorize_break_glass(_request(mfa_verified=False))
    with pytest.raises(BreakGlassError, match="at least 20"):
        _ = authorize_break_glass(_request(reason="too short"))
    with pytest.raises(BreakGlassError, match="confirmation"):
        _ = authorize_break_glass(_request(confirmed=False))


def test_third_daily_invocation_and_forbidden_operations_are_rejected() -> None:
    prior = (NOW - timedelta(hours=1), NOW - timedelta(hours=2))
    with pytest.raises(BreakGlassError, match="two invocations"):
        _ = authorize_break_glass(_request(prior_invocations=prior))
    with pytest.raises(BreakGlassError, match="forbidden"):
        _ = authorize_break_glass(_request(permission="role.assign"))


def test_grant_expires_in_two_hours_and_review_due_in_48_hours() -> None:
    grant = authorize_break_glass(_request())
    assert grant.expires_at == NOW + timedelta(hours=2)
    assert grant.review_due_at == NOW + timedelta(hours=48)
    assert grant.permissions == ("read:workspace", "credential.rotate")


def test_retention_proof_contains_no_subject_pii() -> None:
    subject = RetentionSubject(
        subject_id="person-1",
        email="person@example.com",
        display_name="Person One",
        metadata=(("department", "engineering"),),
    )
    proof = anonymize_subject(
        subject,
        policy_id="retention-7y",
        authorized_by="privacy-1",
        anonymized_at=NOW,
    )
    rendered = proof.canonical_json()
    assert "person@example.com" not in rendered
    assert "Person One" not in rendered
    assert proof.subject_fingerprint

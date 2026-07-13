from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from work_frontier.application.identity import (
    derive_password_record,
    hash_session_token,
    validate_session,
    verify_password,
    verify_totp,
)
from work_frontier.application.ports.identity import IdentityError, SessionRecord
from work_frontier.domain.authorization import (
    AccessRequest,
    ApprovalContext,
    BreakGlassGrant,
    DenyRule,
    Permission,
    ResourceScope,
    Role,
    RoleGrant,
    ScopeKind,
    ScopeSegment,
    authorize,
    evaluate_separation_of_duties,
    permissions_for_role,
)
from work_frontier.platform.crypto import AesGcmCredentialCipher, EnvelopeKey


class MemorySessions:
    record: SessionRecord

    def __init__(self, record: SessionRecord) -> None:
        self.record = record

    def put(self, session: SessionRecord) -> None:
        self.record = session

    def get(self, session_id: str) -> SessionRecord | None:
        return self.record if self.record.session_id == session_id else None

    def revoke(self, session_id: str, revoked_at: datetime) -> None:
        if session_id == self.record.session_id:
            self.record = replace(self.record, revoked_at=revoked_at)


def scope() -> ResourceScope:
    return ResourceScope(
        (
            ScopeSegment(ScopeKind.TENANT, "tenant"),
            ScopeSegment(ScopeKind.WORKSPACE, "workspace"),
            ScopeSegment(ScopeKind.PROGRAM, "program"),
        )
    )


def test_permission_matrix_is_deny_by_default_and_explicit_deny_wins() -> None:
    grant = RoleGrant("actor", Role.BUILDER, scope(), "grant", 1)
    claim = AccessRequest("actor", Permission.WORK_ITEM_CLAIM, scope())
    assert authorize(claim, (grant,)).allowed
    assert not authorize(
        claim,
        (grant,),
        (DenyRule("actor", Permission.WORK_ITEM_CLAIM, scope(), "suspended"),),
    ).allowed
    assert not authorize(
        AccessRequest("actor", Permission.CONNECTION_CONFIGURE, scope()),
        (grant,),
    ).allowed
    assert Permission.USER_ASSIGN_ROLE in permissions_for_role(
        Role.TENANT_ADMINISTRATOR
    )
    assert Permission.USER_ASSIGN_ROLE not in permissions_for_role(
        Role.POLICY_ADMINISTRATOR
    )


def test_separation_of_duties_blocks_self_approval_and_requires_four_eyes() -> None:
    self_approval = evaluate_separation_of_duties(
        Permission.DECISION_CREATE,
        ApprovalContext("builder", ("builder",), claimant_id="builder"),
    )
    assert not self_approval.allowed
    four_eyes = evaluate_separation_of_duties(
        Permission.CONNECTION_CONFIGURE,
        ApprovalContext("admin-a", ("admin-a",)),
    )
    assert not four_eyes.allowed
    assert evaluate_separation_of_duties(
        Permission.CONNECTION_CONFIGURE,
        ApprovalContext("admin-a", ("admin-b",)),
    ).allowed


def test_break_glass_is_narrow_time_bounded_and_strongly_authenticated() -> None:
    grant = BreakGlassGrant(
        actor_id="operator",
        permission=Permission.AUDIT_VIEW,
        scope=scope(),
        reason="Investigate an active production security incident",
        strong_reauthenticated=True,
        second_factor_verified=True,
        duration=timedelta(minutes=30),
    )
    assert grant.permission is Permission.AUDIT_VIEW
    with pytest.raises(ValueError, match="cannot grant"):
        _ = replace(grant, permission=Permission.USER_ASSIGN_ROLE)


def test_session_role_revision_is_checked_on_every_request() -> None:
    token = "x" * 40
    issued = datetime(2026, 7, 13, tzinfo=UTC)
    record = SessionRecord(
        session_id="session",
        actor_id="actor",
        token_hash=hash_session_token(token),
        scope=scope(),
        issued_at=issued,
        expires_at=issued + timedelta(hours=1),
        revoked_at=None,
        role_revision=7,
    )
    store = MemorySessions(record)
    principal = validate_session(
        store,
        session_id="session",
        token=token,
        now=issued + timedelta(minutes=1),
        current_role_revision=7,
    )
    assert principal.actor_id == "actor"
    with pytest.raises(IdentityError, match="role grants changed"):
        _ = validate_session(
            store,
            session_id="session",
            token=token,
            now=issued + timedelta(minutes=2),
            current_role_revision=8,
        )


def test_local_password_totp_and_aes_gcm_credentials_do_not_store_plaintext() -> None:
    password = "p" * 20
    record = derive_password_record(password, b"0123456789abcdef")
    assert verify_password(password, record)
    assert not verify_password("different-password", record)
    assert verify_totp("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", "287082", unix_time=59)

    nonces = iter((b"0" * 12, b"1" * 12))
    cipher = AesGcmCredentialCipher(
        (
            EnvelopeKey("key-1", b"a" * 32),
            EnvelopeKey("key-2", b"b" * 32),
        ),
        active_key_id="key-1",
        nonce_source=lambda _: next(nonces),
    )
    encrypted = cipher.encrypt(
        credential_id="credential",
        workspace_id="workspace-a",
        plaintext=b"github-token-secret",
    )
    assert "github-token-secret" not in repr(encrypted)
    decrypted = cipher.decrypt(
        workspace_id="workspace-a",
        credential=encrypted,
    )
    assert decrypted == b"github-token-secret"
    with pytest.raises(IdentityError, match="workspace scope"):
        _ = cipher.decrypt(workspace_id="workspace-b", credential=encrypted)

"""Async PostgreSQL persistence for sessions, role grants, and credentials."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from work_frontier.application.ports.identity import (
    EncryptedCredential,
    LocalIdentityRecord,
    SessionRecord,
)
from work_frontier.platform.persistence.schema import (
    credential_envelopes,
    local_identities,
    role_grants,
    sessions,
)

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from work_frontier.domain.authorization import RoleGrant


class PostgresIdentityRepository:
    """Store opaque sessions and encrypted credentials within one workspace."""

    _session: AsyncSession
    _tenant_id: str
    _workspace_id: str

    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        workspace_id: str,
    ) -> None:
        """Bind one transaction-local tenant/workspace scope."""
        if not tenant_id.strip() or not workspace_id.strip():
            msg = "identity persistence requires tenant and workspace scope"
            raise ValueError(msg)
        self._session = session
        self._tenant_id = tenant_id
        self._workspace_id = workspace_id

    async def put_local_identity(self, record: LocalIdentityRecord) -> None:
        """Persist one local verifier and an encrypted MFA credential reference."""
        statement = postgres_insert(local_identities).values(
            tenant_id=self._tenant_id,
            workspace_id=self._workspace_id,
            actor_id=record.actor_id,
            username=record.username,
            password_salt_b64=record.password_salt_b64,
            password_verifier_b64=record.password_verifier_b64,
            mfa_credential_id=record.mfa_credential_id,
            role_revision=record.role_revision,
            enabled=record.enabled,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["tenant_id", "workspace_id", "actor_id"],
            set_={
                "username": statement.excluded.username,
                "password_salt_b64": statement.excluded.password_salt_b64,
                "password_verifier_b64": statement.excluded.password_verifier_b64,
                "mfa_credential_id": statement.excluded.mfa_credential_id,
                "role_revision": statement.excluded.role_revision,
                "enabled": statement.excluded.enabled,
            },
        )
        _ = await self._session.execute(statement)

    async def put_session(self, record: SessionRecord) -> None:
        """Insert or replace one opaque session record without storing its token."""
        statement = postgres_insert(sessions).values(
            tenant_id=self._tenant_id,
            workspace_id=self._workspace_id,
            session_id=record.session_id,
            actor_id=record.actor_id,
            token_hash=record.token_hash,
            scope={
                "segments": [
                    {
                        "kind": segment.kind.value,
                        "resource_id": segment.resource_id,
                    }
                    for segment in record.scope.segments
                ]
            },
            issued_at=record.issued_at,
            expires_at=record.expires_at,
            revoked_at=record.revoked_at,
            role_revision=record.role_revision,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["tenant_id", "workspace_id", "session_id"],
            set_={
                "token_hash": statement.excluded.token_hash,
                "scope": statement.excluded.scope,
                "expires_at": statement.excluded.expires_at,
                "revoked_at": statement.excluded.revoked_at,
                "role_revision": statement.excluded.role_revision,
            },
        )
        _ = await self._session.execute(statement)

    async def revoke_session(self, session_id: str, revoked_at: datetime) -> bool:
        """Revoke one session immediately within the current workspace scope."""
        statement = (
            sessions.update()
            .where(
                sessions.c.tenant_id == self._tenant_id,
                sessions.c.workspace_id == self._workspace_id,
                sessions.c.session_id == session_id,
                sessions.c.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
            .returning(sessions.c.session_id)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def put_role_grant(self, grant: RoleGrant) -> None:
        """Persist one versioned resource-scoped role grant."""
        _ = await self._session.execute(
            role_grants.insert().values(
                tenant_id=self._tenant_id,
                workspace_id=self._workspace_id,
                grant_id=grant.grant_id,
                actor_id=grant.actor_id,
                role=grant.role.value,
                scope={
                    "segments": [
                        {
                            "kind": segment.kind.value,
                            "resource_id": segment.resource_id,
                        }
                        for segment in grant.scope.segments
                    ]
                },
                revision=grant.revision,
            )
        )

    async def put_credential(self, credential: EncryptedCredential) -> None:
        """Persist only an authenticated encrypted envelope and its key reference."""
        statement = postgres_insert(credential_envelopes).values(
            tenant_id=self._tenant_id,
            workspace_id=self._workspace_id,
            credential_id=credential.credential_id,
            key_id=credential.key_id,
            nonce_b64=credential.nonce_b64,
            ciphertext_b64=credential.ciphertext_b64,
            associated_data_b64=credential.associated_data_b64,
            fingerprint=credential.fingerprint,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["tenant_id", "workspace_id", "credential_id"],
            set_={
                "key_id": statement.excluded.key_id,
                "nonce_b64": statement.excluded.nonce_b64,
                "ciphertext_b64": statement.excluded.ciphertext_b64,
                "associated_data_b64": statement.excluded.associated_data_b64,
                "fingerprint": statement.excluded.fingerprint,
            },
        )
        _ = await self._session.execute(statement)

    async def credential_envelope(
        self,
        credential_id: str,
    ) -> EncryptedCredential | None:
        """Return one encrypted envelope without exposing plaintext material."""
        result = await self._session.execute(
            sa.select(credential_envelopes).where(
                credential_envelopes.c.tenant_id == self._tenant_id,
                credential_envelopes.c.workspace_id == self._workspace_id,
                credential_envelopes.c.credential_id == credential_id,
            )
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return EncryptedCredential(
            credential_id=str(row["credential_id"]),
            key_id=str(row["key_id"]),
            nonce_b64=str(row["nonce_b64"]),
            ciphertext_b64=str(row["ciphertext_b64"]),
            associated_data_b64=str(row["associated_data_b64"]),
            fingerprint=str(row["fingerprint"]),
        )

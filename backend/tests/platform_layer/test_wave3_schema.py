from __future__ import annotations

from work_frontier.platform.persistence.schema import (
    credential_envelopes,
    decision_cycles,
    local_identities,
    role_grants,
    sessions,
    source_cursors,
    workspace_frontiers,
)


def test_wave3_schema_has_atomic_frontier_identity_and_encrypted_credentials() -> None:
    assert {"cycle_id", "decision_set_hash", "source_revision"} <= set(
        decision_cycles.c.keys()
    )
    assert {"active_cycle_id", "version"} <= set(workspace_frontiers.c.keys())
    assert {"connection_id", "revision"} <= set(source_cursors.c.keys())
    assert {"token_hash", "role_revision", "revoked_at"} <= set(sessions.c.keys())
    assert {
        "password_salt_b64",
        "password_verifier_b64",
        "mfa_credential_id",
    } <= set(local_identities.c.keys())
    assert "password" not in local_identities.c
    assert "totp_secret" not in local_identities.c
    assert {"role", "scope", "revision"} <= set(role_grants.c.keys())
    assert "plaintext" not in credential_envelopes.c
    assert {"ciphertext_b64", "nonce_b64", "key_id"} <= set(
        credential_envelopes.c.keys()
    )

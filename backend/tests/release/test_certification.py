from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from work_frontier.contracts.release_certification import (
    HarnessEvidence,
    ReleaseCertificationError,
    sign_certification,
    verify_certification,
)

if TYPE_CHECKING:
    from pathlib import Path


def evidence(root: Path, subject: str) -> tuple[HarnessEvidence, ...]:
    values: list[HarnessEvidence] = []
    for index in range(68):
        harness_id = f"WF-HAR-TEST-{index:02d}"
        path = root / f"{harness_id}.json"
        payload = {
            "harness_id": harness_id,
            "status": "pass",
            "subject_sha": subject,
        }
        _ = path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        values.append(
            HarnessEvidence(
                harness_id=harness_id,
                status="pass",
                artifact_path=path.name,
                artifact_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                subject_sha=subject,
            )
        )
    return tuple(values)


def test_signed_certification_detects_artifact_tampering(tmp_path: Path) -> None:
    subject = "subject-sha"
    private = Ed25519PrivateKey.generate()
    certification = sign_certification(
        subject_sha=subject,
        service_versions=(("api", "1"),),
        evidence=evidence(tmp_path, subject),
        private_key=private,
        key_id="release-2026-07",
    )
    verify_certification(
        certification,
        private.public_key(),
        expected_subject_sha=subject,
        evidence_root=tmp_path,
    )
    _ = (tmp_path / certification.evidence[0].artifact_path).write_text(
        "tampered",
        encoding="utf-8",
    )
    with pytest.raises(ReleaseCertificationError, match="artifact changed"):
        verify_certification(
            certification,
            private.public_key(),
            expected_subject_sha=subject,
            evidence_root=tmp_path,
        )


def test_wrong_subject_is_rejected(tmp_path: Path) -> None:
    private = Ed25519PrivateKey.generate()
    certification = sign_certification(
        subject_sha="subject-a",
        service_versions=(("api", "1"),),
        evidence=evidence(tmp_path, "subject-a"),
        private_key=private,
        key_id="key",
    )
    with pytest.raises(ReleaseCertificationError, match="subject"):
        verify_certification(
            certification,
            private.public_key(),
            expected_subject_sha="subject-b",
            evidence_root=tmp_path,
        )

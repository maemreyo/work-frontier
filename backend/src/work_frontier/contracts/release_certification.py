"""Canonical signed Standard ReleaseCertification generation and verification."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, cast

if TYPE_CHECKING:
    from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

_HARNESS_COUNT: Final = 68
_PRIVATE_KEY_BYTES: Final = 32

_SCOPED_IDS: Final = frozenset(
    {"WF-HAR-STATIC-03", "WF-HAR-OPS-02-L", "WF-HAR-OPS-02-T"}
)


class ReleaseCertificationError(ValueError):
    """Signal false, incomplete, stale, or tampered release evidence."""


@dataclass(frozen=True, slots=True, order=True)
class HarnessEvidence:
    """One revision-bound harness result included in certification."""

    harness_id: str
    status: str
    artifact_path: str
    artifact_sha256: str
    subject_sha: str
    applicability_reason: str | None = None

    def canonical(self) -> dict[str, object]:
        """Return stable JSON-compatible evidence."""
        return {
            "applicability_reason": self.applicability_reason,
            "artifact_path": self.artifact_path,
            "artifact_sha256": self.artifact_sha256,
            "harness_id": self.harness_id,
            "status": self.status,
            "subject_sha": self.subject_sha,
        }


@dataclass(frozen=True, slots=True)
class ReleaseCertification:
    """Signed exact-subject Standard release statement."""

    subject_sha: str
    service_versions: tuple[tuple[str, str], ...]
    evidence: tuple[HarnessEvidence, ...]
    manifest_sha256: str
    key_id: str
    signature_b64: str
    all_passed: bool

    def unsigned_payload(self) -> dict[str, object]:
        """Return canonical signed payload."""
        return {
            "all_passed": self.all_passed,
            "evidence": [item.canonical() for item in self.evidence],
            "key_id": self.key_id,
            "manifest_sha256": self.manifest_sha256,
            "service_versions": dict(self.service_versions),
            "subject_sha": self.subject_sha,
        }

    def canonical_json(self) -> str:
        """Return complete canonical certification JSON."""
        return json.dumps(
            {**self.unsigned_payload(), "signature_b64": self.signature_b64},
            sort_keys=True,
            separators=(",", ":"),
        )


def collect_evidence(
    *,
    registry_ids: tuple[str, ...],
    evidence_root: Path,
    subject_sha: str,
) -> tuple[HarnessEvidence, ...]:
    """Load exactly one canonical receipt for every registry harness."""
    if len(registry_ids) != _HARNESS_COUNT or len(set(registry_ids)) != _HARNESS_COUNT:
        msg = "release registry must contain exactly 68 unique harness IDs"
        raise ReleaseCertificationError(msg)
    results: list[HarnessEvidence] = []
    for harness_id in sorted(registry_ids):
        matches = sorted(evidence_root.rglob(f"{harness_id}.json"))
        if len(matches) != 1:
            msg = f"expected exactly one evidence artifact for {harness_id}"
            raise ReleaseCertificationError(msg)
        path = matches[0]
        raw = path.read_bytes()
        raw_payload: object = json.loads(raw)
        if not isinstance(raw_payload, dict):
            msg = f"invalid evidence payload for {harness_id}"
            raise ReleaseCertificationError(msg)
        payload = cast("dict[str, object]", raw_payload)
        status = str(payload.get("status", ""))
        artifact_subject = str(payload.get("subject_sha", ""))
        recorded_id = str(payload.get("harness_id", ""))
        applicability = payload.get("applicability_reason")
        if recorded_id != harness_id or artifact_subject != subject_sha:
            msg = f"stale or contradictory evidence for {harness_id}"
            raise ReleaseCertificationError(msg)
        if status == "not_applicable":
            if harness_id not in _SCOPED_IDS or not isinstance(applicability, str):
                msg = f"false N/A status for {harness_id}"
                raise ReleaseCertificationError(msg)
        elif status != "pass":
            msg = f"blocking or unknown status for {harness_id}: {status}"
            raise ReleaseCertificationError(msg)
        results.append(
            HarnessEvidence(
                harness_id=harness_id,
                status=status,
                artifact_path=path.relative_to(evidence_root).as_posix(),
                artifact_sha256=hashlib.sha256(raw).hexdigest(),
                subject_sha=subject_sha,
                applicability_reason=(
                    applicability if isinstance(applicability, str) else None
                ),
            )
        )
    return tuple(results)


def sign_certification(
    *,
    subject_sha: str,
    service_versions: tuple[tuple[str, str], ...],
    evidence: tuple[HarnessEvidence, ...],
    private_key: Ed25519PrivateKey,
    key_id: str,
) -> ReleaseCertification:
    """Sign a canonical exact-subject release certification."""
    ordered_evidence = tuple(sorted(evidence))
    manifest_payload = json.dumps(
        [item.canonical() for item in ordered_evidence],
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    manifest_sha = hashlib.sha256(manifest_payload).hexdigest()
    unsigned = {
        "all_passed": True,
        "evidence": [item.canonical() for item in ordered_evidence],
        "key_id": key_id,
        "manifest_sha256": manifest_sha,
        "service_versions": dict(sorted(service_versions)),
        "subject_sha": subject_sha,
    }
    encoded = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    signature = private_key.sign(encoded)
    return ReleaseCertification(
        subject_sha=subject_sha,
        service_versions=tuple(sorted(service_versions)),
        evidence=ordered_evidence,
        manifest_sha256=manifest_sha,
        key_id=key_id,
        signature_b64=base64.b64encode(signature).decode(),
        all_passed=True,
    )


def verify_certification(
    certification: ReleaseCertification,
    public_key: Ed25519PublicKey,
    *,
    expected_subject_sha: str,
    evidence_root: Path,
) -> None:
    """Verify subject, manifest, artifact hashes, and Ed25519 signature."""
    if (
        not certification.all_passed
        or certification.subject_sha != expected_subject_sha
    ):
        msg = "release certification subject or status is invalid"
        raise ReleaseCertificationError(msg)
    manifest_payload = json.dumps(
        [item.canonical() for item in certification.evidence],
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if hashlib.sha256(manifest_payload).hexdigest() != certification.manifest_sha256:
        msg = "release evidence manifest hash mismatch"
        raise ReleaseCertificationError(msg)
    for item in certification.evidence:
        path = evidence_root / item.artifact_path
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != (
            item.artifact_sha256
        ):
            msg = f"release evidence artifact changed: {item.harness_id}"
            raise ReleaseCertificationError(msg)
    encoded = json.dumps(
        certification.unsigned_payload(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    try:
        public_key.verify(base64.b64decode(certification.signature_b64), encoded)
    except (InvalidSignature, ValueError) as exc:
        msg = "release certification signature is invalid"
        raise ReleaseCertificationError(msg) from exc


def load_private_key(value_b64: str) -> Ed25519PrivateKey:
    """Load a raw 32-byte Ed25519 private key from base64."""
    raw = base64.b64decode(value_b64, validate=True)
    if len(raw) != _PRIVATE_KEY_BYTES:
        msg = "release signing key must be a raw 32-byte Ed25519 key"
        raise ReleaseCertificationError(msg)
    return Ed25519PrivateKey.from_private_bytes(raw)

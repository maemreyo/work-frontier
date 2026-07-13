"""Operational capability truth, SLO, backup, restore, and drill records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

_MIN_MANAGED_REPLICAS = 2


class OperationError(ValueError):
    """Signal an invalid or failed operational certification."""


class DeploymentCapability(StrEnum):
    """Truthful deployment support levels."""

    SINGLE_NODE = "single_node"
    MANAGED_STANDARD = "managed_standard"


@dataclass(frozen=True, slots=True)
class DeploymentProfile:
    """Declared deployment capabilities without unsupported HA claims."""

    name: str
    capability: DeploymentCapability
    replicas: int
    tls_required: bool
    backup_enabled: bool

    def __post_init__(self) -> None:
        """Validate truthful capability declarations."""
        if not self.name.strip() or self.replicas < 1:
            msg = "deployment profile requires name and positive replicas"
            raise OperationError(msg)
        if self.capability is DeploymentCapability.SINGLE_NODE and self.replicas != 1:
            msg = "single-node profile cannot claim multiple replicas"
            raise OperationError(msg)
        if self.capability is DeploymentCapability.MANAGED_STANDARD and (
            self.replicas < _MIN_MANAGED_REPLICAS
            or not self.tls_required
            or not self.backup_enabled
        ):
            msg = "managed Standard profile requires redundancy, TLS, and backup"
            raise OperationError(msg)


@dataclass(frozen=True, slots=True)
class SloSample:
    """One valid completed request latency sample."""

    operation: str
    latency_ms: float
    succeeded: bool


@dataclass(frozen=True, slots=True)
class SloReport:
    """Deterministic SLO evaluation."""

    p95_ms: float
    p99_ms: float
    error_rate: float
    passed: bool


def evaluate_slo(
    samples: tuple[SloSample, ...],
    *,
    p95_target_ms: float,
    max_error_rate: float = 0.001,
) -> SloReport:
    """Evaluate all valid completed requests without outlier removal."""
    if not samples:
        msg = "SLO evaluation requires samples"
        raise OperationError(msg)
    latencies = sorted(sample.latency_ms for sample in samples if sample.succeeded)
    if not latencies or any(value < 0 for value in latencies):
        msg = "SLO samples require non-negative successful latencies"
        raise OperationError(msg)
    errors = sum(not sample.succeeded for sample in samples)
    p95 = _percentile(latencies, 0.95)
    p99 = _percentile(latencies, 0.99)
    error_rate = errors / len(samples)
    return SloReport(
        p95_ms=p95,
        p99_ms=p99,
        error_rate=error_rate,
        passed=p95 <= p95_target_ms and error_rate <= max_error_rate,
    )


@dataclass(frozen=True, slots=True)
class BackupObject:
    """One content-addressed backup object."""

    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class BackupManifest:
    """Canonical database/object inventory at one recovery point."""

    subject_sha: str
    created_at: datetime
    database_lsn: str
    objects: tuple[BackupObject, ...]
    manifest_sha256: str


def create_backup_manifest(
    *,
    subject_sha: str,
    created_at: datetime,
    database_lsn: str,
    objects: tuple[BackupObject, ...],
) -> BackupManifest:
    """Create a deterministic sorted backup inventory."""
    _require_aware(created_at)
    ordered = tuple(sorted(objects, key=lambda item: item.path))
    if not subject_sha.strip() or not database_lsn.strip() or not ordered:
        msg = "backup manifest requires subject, LSN, and objects"
        raise OperationError(msg)
    if len({item.path for item in ordered}) != len(ordered):
        msg = "backup object paths must be unique"
        raise OperationError(msg)
    payload = {
        "created_at": created_at.isoformat(),
        "database_lsn": database_lsn,
        "objects": [
            {"path": item.path, "sha256": item.sha256, "size_bytes": item.size_bytes}
            for item in ordered
        ],
        "subject_sha": subject_sha,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return BackupManifest(
        subject_sha=subject_sha,
        created_at=created_at,
        database_lsn=database_lsn,
        objects=ordered,
        manifest_sha256=digest,
    )


@dataclass(frozen=True, slots=True)
class RecoveryDrill:
    """Measured restore and recovery point evidence."""

    manifest_sha256: str
    backup_at: datetime
    failure_at: datetime
    restored_at: datetime
    served_at: datetime
    integrity_verified: bool

    @property
    def rpo(self) -> timedelta:
        """Return recovery-point objective measurement."""
        return self.failure_at - self.backup_at

    @property
    def rto(self) -> timedelta:
        """Return recovery-time objective measurement."""
        return self.served_at - self.failure_at

    def assert_standard(self) -> None:
        """Enforce Standard RPO/RTO and integrity thresholds."""
        timestamps = (
            self.backup_at,
            self.failure_at,
            self.restored_at,
            self.served_at,
        )
        for value in timestamps:
            _require_aware(value)
        if (
            not self.integrity_verified
            or self.rpo < timedelta(0)
            or self.rpo > timedelta(minutes=5)
            or self.rto < timedelta(0)
            or self.rto > timedelta(minutes=60)
            or self.restored_at > self.served_at
        ):
            msg = "recovery drill does not satisfy Standard RPO/RTO"
            raise OperationError(msg)


@dataclass(frozen=True, slots=True)
class FailureInjectionReport:
    """Recovery evidence for a controlled failure scenario."""

    scenario: str
    acknowledged_events_lost: int
    recovered: bool
    alert_fired: bool
    orphaned_jobs: int

    def assert_passed(self) -> None:
        """Require lossless acknowledged-event recovery and alerting."""
        if (
            not self.recovered
            or not self.alert_fired
            or self.acknowledged_events_lost != 0
            or self.orphaned_jobs != 0
        ):
            msg = "failure injection did not recover cleanly"
            raise OperationError(msg)


def _percentile(values: list[float], quantile: float) -> float:
    if len(values) == 1:
        return values[0]
    rank = (len(values) - 1) * quantile
    lower = int(rank)
    upper = min(lower + 1, len(values) - 1)
    fraction = rank - lower
    return values[lower] + (values[upper] - values[lower]) * fraction


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        msg = "operational timestamps must be timezone-aware"
        raise OperationError(msg)

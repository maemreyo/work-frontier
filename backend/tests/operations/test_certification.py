from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from work_frontier.platform.operations.certification import (
    BackupObject,
    DeploymentCapability,
    DeploymentProfile,
    FailureInjectionReport,
    OperationError,
    RecoveryDrill,
    SloSample,
    create_backup_manifest,
    evaluate_slo,
)


def test_single_node_profile_cannot_claim_ha() -> None:
    with pytest.raises(OperationError, match="single-node"):
        _ = DeploymentProfile(
            "compose",
            DeploymentCapability.SINGLE_NODE,
            replicas=2,
            tls_required=False,
            backup_enabled=False,
        )


def test_standard_slo_includes_all_completed_requests() -> None:
    successes = tuple(
        SloSample("frontier", latency_ms=float(index), succeeded=True)
        for index in range(1, 101)
    )
    samples = (*successes, SloSample("frontier", latency_ms=999, succeeded=False))
    report = evaluate_slo(samples, p95_target_ms=100)
    assert report.p95_ms <= 100
    assert report.error_rate > 0
    assert not report.passed


def test_backup_manifest_is_order_independent() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    a = BackupObject("b", "b" * 64, 2)
    b = BackupObject("a", "a" * 64, 1)
    first = create_backup_manifest(
        subject_sha="subject",
        created_at=now,
        database_lsn="0/ABC",
        objects=(a, b),
    )
    second = create_backup_manifest(
        subject_sha="subject",
        created_at=now,
        database_lsn="0/ABC",
        objects=(b, a),
    )
    assert first.manifest_sha256 == second.manifest_sha256
    assert [item.path for item in first.objects] == ["a", "b"]


def test_recovery_drill_enforces_rpo_rto() -> None:
    failure = datetime(2026, 7, 13, 12, tzinfo=UTC)
    drill = RecoveryDrill(
        manifest_sha256="a" * 64,
        backup_at=failure - timedelta(minutes=4),
        failure_at=failure,
        restored_at=failure + timedelta(minutes=20),
        served_at=failure + timedelta(minutes=30),
        integrity_verified=True,
    )
    drill.assert_standard()
    slow = RecoveryDrill(
        manifest_sha256="a" * 64,
        backup_at=failure - timedelta(minutes=6),
        failure_at=failure,
        restored_at=failure + timedelta(minutes=20),
        served_at=failure + timedelta(minutes=61),
        integrity_verified=True,
    )
    with pytest.raises(OperationError):
        slow.assert_standard()


def test_failure_injection_requires_lossless_recovery() -> None:
    FailureInjectionReport(
        scenario="worker-kill",
        acknowledged_events_lost=0,
        recovered=True,
        alert_fired=True,
        orphaned_jobs=0,
    ).assert_passed()
    failed = FailureInjectionReport(
        scenario="db-loss",
        acknowledged_events_lost=1,
        recovered=True,
        alert_fired=True,
        orphaned_jobs=0,
    )
    with pytest.raises(OperationError):
        failed.assert_passed()

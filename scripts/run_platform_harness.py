#!/usr/bin/env python3
"""Run PostgreSQL/MinIO platform harnesses for Items 11-13."""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Final, Protocol, cast

from sqlalchemy import Connection, create_engine, text
from sqlalchemy.exc import DBAPIError

from work_frontier.platform.audit import (
    AuditEvent,
    AuditSegment,
    SignedAnchor,
    append_event,
    verify_segment,
)
from work_frontier.platform.object_store import (
    ContentAddressedEvidenceStore,
    S3Client,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.engine import Engine

ROOT: Final = Path(__file__).resolve().parents[1]
DATABASE_URL_ENV: Final = "DATABASE_URL"
TENANT: Final = "harness-tenant"
ORG: Final = "harness-org"
WORKSPACE_A: Final = "harness-workspace-a"
WORKSPACE_B: Final = "harness-workspace-b"
APP_ROLE: Final = "work_frontier_app"
FALLBACK_BY_MODE: Final = {
    "rls": "evidence/security/idor.json",
    "evidence": "evidence/security/evidence-tampering.json",
    "audit": "evidence/security/audit-integrity.json",
    "queue": "evidence/integration/durable-queue.json",
    "worker": "evidence/integration/worker.json",
    "scheduler": "evidence/integration/scheduler.json",
    "durability": "evidence/ops/event-durability.json",
}

SET_APP_ROLE_SQL: Final = text("SET LOCAL ROLE work_frontier_app")
IMMUTABLE_UPDATE_SQL: Final = {
    ("evidence_records", "evidence_id"): text(
        "UPDATE evidence_records SET evidence_id = evidence_id WHERE evidence_id = :key"
    ),
    ("audit_events", "event_id"): text(
        "UPDATE audit_events SET event_id = event_id WHERE event_id = :key"
    ),
}
COUNT_SQL: Final = {
    "webhook_inbox": text("SELECT count(*) FROM webhook_inbox"),
    "normalized_snapshots": text("SELECT count(*) FROM normalized_snapshots"),
    "work_items": text("SELECT count(*) FROM work_items"),
    "decision_records": text("SELECT count(*) FROM decision_records"),
    "current_projections": text("SELECT count(*) FROM current_projections"),
    "audit_segments": text("SELECT count(*) FROM audit_segments"),
    "audit_events": text("SELECT count(*) FROM audit_events"),
    "transactional_outbox": text("SELECT count(*) FROM transactional_outbox"),
}


def _require(condition: bool, message: str) -> None:
    """Fail one harness assertion with an explicit diagnostic."""
    if not condition:
        raise RuntimeError(message)


def _database_url() -> str:
    value = os.environ.get(DATABASE_URL_ENV)
    if value is None:
        msg = f"{DATABASE_URL_ENV} must be set"
        raise RuntimeError(msg)
    return value


def _set_scope(connection: Connection, workspace_id: str) -> None:
    _ = connection.execute(SET_APP_ROLE_SQL)
    _ = connection.execute(
        text("SELECT set_config('work_frontier.tenant_id', :value, true)"),
        {"value": TENANT},
    )
    _ = connection.execute(
        text("SELECT set_config('work_frontier.workspace_id', :value, true)"),
        {"value": workspace_id},
    )


def _reset(engine: Engine) -> None:
    with engine.begin() as connection:
        _ = connection.execute(text("TRUNCATE TABLE tenants CASCADE"))
        _ = connection.execute(
            text("INSERT INTO tenants (tenant_id, name) VALUES (:id, 'Harness')"),
            {"id": TENANT},
        )
        _ = connection.execute(
            text(
                "INSERT INTO organizations "
                "(tenant_id, organization_id, name) "
                "VALUES (:tenant, :organization, 'Harness')"
            ),
            {"tenant": TENANT, "organization": ORG},
        )
        for workspace in (WORKSPACE_A, WORKSPACE_B):
            _ = connection.execute(
                text(
                    "INSERT INTO workspaces "
                    "(tenant_id, workspace_id, organization_id, name) "
                    "VALUES (:tenant, :workspace, :organization, :name)"
                ),
                {
                    "tenant": TENANT,
                    "workspace": workspace,
                    "organization": ORG,
                    "name": workspace,
                },
            )


def _insert_item(connection: Connection, workspace: str, item_id: str) -> None:
    _set_scope(connection, workspace)
    _ = connection.execute(
        text(
            "INSERT INTO work_items "
            "(tenant_id, workspace_id, item_id, title, lifecycle, version, payload) "
            "VALUES (:tenant, :workspace, :item, :title, 'planned', 1, '{}'::jsonb)"
        ),
        {
            "tenant": TENANT,
            "workspace": workspace,
            "item": item_id,
            "title": item_id,
        },
    )


def _run_rls(engine: Engine) -> dict[str, object]:
    _reset(engine)
    with engine.begin() as connection:
        _insert_item(connection, WORKSPACE_A, "item-a")
    with engine.begin() as connection:
        _insert_item(connection, WORKSPACE_B, "item-b")

    with engine.begin() as connection:
        _set_scope(connection, WORKSPACE_A)
        visible = tuple(
            str(value)
            for value in connection.execute(
                text("SELECT item_id FROM work_items ORDER BY item_id")
            ).scalars()
        )
        cross_scope = connection.execute(
            text("SELECT item_id FROM work_items WHERE workspace_id = :workspace"),
            {"workspace": WORKSPACE_B},
        ).first()

    rejected = False
    try:
        with engine.begin() as connection:
            _set_scope(connection, WORKSPACE_A)
            _ = connection.execute(
                text(
                    """
                    INSERT INTO work_items
                      (tenant_id, workspace_id, item_id, title, lifecycle,
                       version, payload)
                    VALUES
                      (:tenant, :workspace, 'cross', 'cross', 'planned',
                       1, '{}'::jsonb)
                    """
                ),
                {"tenant": TENANT, "workspace": WORKSPACE_B},
            )
    except DBAPIError:
        rejected = True

    with engine.begin() as connection:
        _ = connection.execute(SET_APP_ROLE_SQL)
        absent_context_count = cast(
            "int",
            connection.execute(text("SELECT count(*) FROM work_items")).scalar_one(),
        )
    with engine.connect() as connection:
        bypass = cast(
            "bool",
            connection.execute(
                text("SELECT rolbypassrls FROM pg_roles WHERE rolname = :role"),
                {"role": APP_ROLE},
            ).scalar_one(),
        )
    _require(visible == ("item-a",), "workspace A must see only item-a")
    _require(cross_scope is None, "cross-workspace read must be denied")
    _require(rejected, "cross-workspace insert must be rejected")
    _require(absent_context_count == 0, "missing scope must expose no rows")
    _require(not bypass, "application role must not have BYPASSRLS")
    return {
        "visible_in_workspace_a": list(visible),
        "cross_scope_read_denied": True,
        "cross_scope_write_denied": rejected,
        "missing_context_count": absent_context_count,
        "app_role_bypassrls": bypass,
    }


def _audit_segment() -> tuple[AuditSegment, SignedAnchor]:
    event = AuditEvent(
        event_id="event-1",
        event_type="verified",
        actor="system:harness",
        subject_id="item-a",
        causation_id="cause-1",
        correlation_id="correlation-1",
        created_at=datetime(2026, 7, 13, tzinfo=UTC),
        payload=(("result", "pass"),),
    )
    segment = append_event(
        AuditSegment.open(TENANT, WORKSPACE_A, "segment-1"),
        event,
    ).close()
    return segment, SignedAnchor.sign_for_test(segment, signer="harness-root")


def _insert_audit(engine: Engine) -> tuple[AuditSegment, SignedAnchor]:
    _reset(engine)
    segment, anchor = _audit_segment()
    entry = segment.entries[0]
    with engine.begin() as connection:
        _insert_item(connection, WORKSPACE_A, "item-a")
    with engine.begin() as connection:
        _set_scope(connection, WORKSPACE_A)
        _ = connection.execute(
            text(
                """
                INSERT INTO audit_segments
                  (tenant_id, workspace_id, segment_id, state,
                   final_checksum, external_anchor)
                VALUES
                  (:tenant, :workspace, :segment, 'closed', :checksum,
                   CAST(:anchor AS jsonb))
                """
            ),
            {
                "tenant": TENANT,
                "workspace": WORKSPACE_A,
                "segment": segment.segment_id,
                "checksum": segment.final_checksum,
                "anchor": json.dumps({"signature": anchor.signature}),
            },
        )
        _ = connection.execute(
            text(
                """
                INSERT INTO audit_events
                  (tenant_id, workspace_id, segment_id, seq, event_id,
                   event_type, actor, subject_id, causation_id, correlation_id,
                   payload, payload_hash, previous_checksum, checksum, created_at)
                VALUES
                  (:tenant, :workspace, :segment, :seq, :event_id, :event_type,
                   :actor, :subject_id, :causation_id, :correlation_id,
                   CAST(:payload AS jsonb), :payload_hash, :previous_checksum,
                   :checksum, :created_at)
                """
            ),
            {
                "tenant": TENANT,
                "workspace": WORKSPACE_A,
                "segment": segment.segment_id,
                "seq": entry.seq,
                "event_id": entry.event.event_id,
                "event_type": entry.event.event_type,
                "actor": entry.event.actor,
                "subject_id": entry.event.subject_id,
                "causation_id": entry.event.causation_id,
                "correlation_id": entry.event.correlation_id,
                "payload": json.dumps(dict(entry.event.payload)),
                "payload_hash": entry.payload_hash,
                "previous_checksum": entry.previous_checksum,
                "checksum": entry.checksum,
                "created_at": entry.event.created_at,
            },
        )
    return segment, anchor


def _mutation_rejected(engine: Engine, table: str, key_column: str, key: str) -> bool:
    try:
        with engine.begin() as connection:
            _set_scope(connection, WORKSPACE_A)
            statement = IMMUTABLE_UPDATE_SQL[(table, key_column)]
            _ = connection.execute(statement, {"key": key})
    except DBAPIError:
        return True
    return False


def _run_evidence(engine: Engine) -> dict[str, object]:
    _reset(engine)
    with engine.begin() as connection:
        _insert_item(connection, WORKSPACE_A, "item-a")
    with engine.begin() as connection:
        _set_scope(connection, WORKSPACE_A)
        _ = connection.execute(
            text(
                """
                INSERT INTO evidence_records
                  (tenant_id, workspace_id, evidence_id, gate_id, item_id,
                   revision, payload, payload_hash)
                VALUES
                  (:tenant, :workspace, 'evidence-1', 'gate-1', 'item-a',
                   'revision-1', '{}'::jsonb, :hash)
                """
            ),
            {"tenant": TENANT, "workspace": WORKSPACE_A, "hash": "a" * 64},
        )
    rejected = _mutation_rejected(
        engine,
        "evidence_records",
        "evidence_id",
        "evidence-1",
    )
    _require(rejected, "evidence rows must reject updates")
    return {"evidence_update_rejected": rejected}


class Boto3Module(Protocol):
    """Dynamic boto3 module surface used without importing untyped stubs."""

    def client(self, service_name: str, **kwargs: object) -> object:
        """Create one service client."""
        ...


class HarnessS3Client(S3Client, Protocol):
    """S3 operations needed only by the executable integration harness."""

    def list_buckets(self) -> dict[str, object]:
        """List buckets visible to the harness client."""
        ...

    def create_bucket(self, **kwargs: object) -> dict[str, object]:
        """Create one harness bucket."""
        ...

    def delete_object(self, **kwargs: object) -> dict[str, object]:
        """Delete one temporary harness object."""
        ...


def _ensure_bucket(client: HarnessS3Client, bucket: str) -> None:
    buckets = cast("list[dict[str, object]]", client.list_buckets().get("Buckets", []))
    names = {str(entry["Name"]) for entry in buckets}
    if bucket not in names:
        _ = client.create_bucket(Bucket=bucket)


def _run_audit(engine: Engine) -> dict[str, object]:
    segment, anchor = _insert_audit(engine)
    chain = verify_segment(
        segment,
        anchor=anchor,
        require_external_anchor=True,
    )
    rejected = _mutation_rejected(engine, "audit_events", "event_id", "event-1")
    endpoint = os.environ.get("MINIO_ENDPOINT_URL")
    access_key = os.environ.get("MINIO_ROOT_USER")
    secret_key = os.environ.get("MINIO_ROOT_PASSWORD")
    if not endpoint or not access_key or not secret_key:
        msg = "MinIO environment is required for audit harness"
        raise RuntimeError(msg)
    boto3_module = cast("Boto3Module", cast("object", import_module("boto3")))
    client = cast(
        "HarnessS3Client",
        boto3_module.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
        ),
    )
    bucket = "work-frontier-item-12"
    _ensure_bucket(client, bucket)
    store = ContentAddressedEvidenceStore(client, bucket)
    reference = store.put(
        tenant_id=TENANT,
        workspace_id=WORKSPACE_A,
        content=b"immutable-evidence",
    )
    roundtrip = store.get(reference)
    _ = client.delete_object(Bucket=bucket, Key=reference.key)
    _require(chain.valid, "audit chain and external anchor must verify")
    _require(rejected, "audit rows must reject updates")
    _require(roundtrip == b"immutable-evidence", "object roundtrip mismatch")
    return {
        "chain_valid": chain.valid,
        "external_anchor_valid": anchor.verifies(segment),
        "audit_update_rejected": rejected,
        "object_sha256": reference.sha256,
        "object_roundtrip": True,
    }


def _insert_job(engine: Engine, *, job_id: str = "job-1") -> None:
    now = datetime.now(UTC)
    with engine.begin() as connection:
        _set_scope(connection, WORKSPACE_A)
        _ = connection.execute(
            text(
                """
                INSERT INTO job_queue
                  (tenant_id, workspace_id, job_id, job_type, state,
                   idempotency_key, payload, attempts, max_attempts,
                   next_attempt_at, attempt_history, created_at)
                VALUES
                  (:tenant, :workspace, :job, 'sync', 'pending', :key,
                   '{}'::jsonb, 0, 3, :now, '[]'::jsonb, :now)
                """
            ),
            {
                "tenant": TENANT,
                "workspace": WORKSPACE_A,
                "job": job_id,
                "key": f"key-{job_id}",
                "now": now,
            },
        )


def _claim_once(url: str, worker: str) -> str | None:
    engine = create_engine(url)
    now = datetime.now(UTC)
    try:
        with engine.begin() as connection:
            _set_scope(connection, WORKSPACE_A)
            row = connection.execute(
                text(
                    """
                WITH candidate AS (
                  SELECT tenant_id, workspace_id, job_id
                  FROM job_queue
                  WHERE state = 'pending' AND next_attempt_at <= :now
                  ORDER BY created_at, job_id
                  FOR UPDATE SKIP LOCKED LIMIT 1
                )
                UPDATE job_queue AS jobs
                SET state = 'claimed', lease_owner = :worker,
                    lease_expires_at = :expires, heartbeat_at = :now,
                    claimed_at = :now
                FROM candidate
                WHERE jobs.tenant_id = candidate.tenant_id
                  AND jobs.workspace_id = candidate.workspace_id
                  AND jobs.job_id = candidate.job_id
                RETURNING jobs.job_id
                """
                ),
                {"now": now, "worker": worker, "expires": now + timedelta(seconds=30)},
            ).first()
            time.sleep(0.1)
            return None if row is None else str(row[0])
    finally:
        engine.dispose()


def _run_queue(engine: Engine) -> dict[str, object]:
    _reset(engine)
    _insert_job(engine)
    url = _database_url()

    def claim(worker: str) -> str | None:
        return _claim_once(url, worker)

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = tuple(pool.map(claim, ("worker-a", "worker-b")))
    winners = tuple(claim for claim in claims if claim is not None)
    _require(winners == ("job-1",), "exactly one worker must claim job-1")
    return {"claim_results": list(claims), "unique_owner_count": len(winners)}


def _run_worker(engine: Engine) -> dict[str, object]:
    _reset(engine)
    _insert_job(engine)
    claimed = _claim_once(_database_url(), "worker-a")
    _require(claimed == "job-1", "worker-a must initially claim job-1")
    future = datetime.now(UTC) + timedelta(minutes=1)
    with engine.begin() as connection:
        _set_scope(connection, WORKSPACE_A)
        stale_complete = connection.execute(
            text(
                "UPDATE job_queue SET state = 'completed' "
                "WHERE job_id = 'job-1' AND state = 'claimed' "
                "AND lease_owner = 'worker-a' AND lease_expires_at >= :now"
            ),
            {"now": future},
        ).rowcount
        _ = connection.execute(
            text(
                "UPDATE job_queue SET state = 'pending', lease_owner = NULL, "
                "lease_expires_at = NULL, heartbeat_at = NULL, "
                "attempts = attempts + 1, next_attempt_at = :now "
                "WHERE job_id = 'job-1'"
            ),
            {"now": future},
        )
    recovered = _claim_once(_database_url(), "worker-b")
    _require(stale_complete == 0, "stale worker must not complete the job")
    _require(recovered == "job-1", "worker-b must recover the expired job")
    return {"stale_completion_rows": stale_complete, "recovered_owner": "worker-b"}


def _run_scheduler(engine: Engine) -> dict[str, object]:
    _reset(engine)
    now = datetime.now(UTC)

    def acquire(owner: str, at: datetime) -> int:
        with engine.begin() as connection:
            _set_scope(connection, WORKSPACE_A)
            return connection.execute(
                text(
                    """
                    INSERT INTO scheduler_leases
                      (tenant_id, workspace_id, schedule_key, lease_owner,
                       lease_expires_at, version)
                    VALUES (:tenant, :workspace, 'sync', :owner, :expires, 1)
                    ON CONFLICT (tenant_id, workspace_id, schedule_key)
                    DO UPDATE SET lease_owner = EXCLUDED.lease_owner,
                                  lease_expires_at = EXCLUDED.lease_expires_at,
                                  version = scheduler_leases.version + 1
                    WHERE scheduler_leases.lease_owner = EXCLUDED.lease_owner
                       OR scheduler_leases.lease_expires_at < :now
                    """
                ),
                {
                    "tenant": TENANT,
                    "workspace": WORKSPACE_A,
                    "owner": owner,
                    "expires": at + timedelta(seconds=30),
                    "now": at,
                },
            ).rowcount

    first = acquire("scheduler-a", now)
    overlap = acquire("scheduler-b", now + timedelta(seconds=1))
    takeover = acquire("scheduler-b", now + timedelta(seconds=31))
    _require(
        (first, overlap, takeover) == (1, 0, 1),
        "scheduler fence must reject overlap and allow expired takeover",
    )
    return {"first": first, "overlap": overlap, "expired_takeover": takeover}


def _run_durability(engine: Engine) -> dict[str, object]:
    _reset(engine)
    tables = (
        "webhook_inbox",
        "normalized_snapshots",
        "work_items",
        "decision_records",
        "current_projections",
        "audit_segments",
        "audit_events",
        "transactional_outbox",
    )
    try:
        with engine.begin() as connection:
            _set_scope(connection, WORKSPACE_A)
            _ = connection.execute(
                text(
                    "INSERT INTO webhook_inbox VALUES (:t,:w,'d','"
                    + "a" * 64
                    + "','received','{}'::jsonb)"
                ),
                {"t": TENANT, "w": WORKSPACE_A},
            )
            _ = connection.execute(
                text(
                    """
                    INSERT INTO work_items
                      (tenant_id, workspace_id, item_id, title, lifecycle,
                       version, payload)
                    VALUES (:t, :w, 'i', 'I', 'planned', 1, '{}'::jsonb)
                    """
                ),
                {"t": TENANT, "w": WORKSPACE_A},
            )
            _ = connection.execute(
                text(
                    """
                    INSERT INTO normalized_snapshots
                      (tenant_id, workspace_id, snapshot_id, content_hash,
                       source_revision_set, graph_revision, profile_version, payload)
                    VALUES
                      (:t, :w, 's', :h, '{}'::jsonb, 'g', 'p', '{}'::jsonb)
                    """
                ),
                {"t": TENANT, "w": WORKSPACE_A, "h": "b" * 64},
            )
            _ = connection.execute(
                text(
                    """
                    INSERT INTO decision_records
                      (tenant_id, workspace_id, decision_id, item_id,
                       payload, payload_hash)
                    VALUES (:t, :w, 'r', 'i', '{}'::jsonb, :h)
                    """
                ),
                {"t": TENANT, "w": WORKSPACE_A, "h": "c" * 64},
            )
            _ = connection.execute(
                text(
                    """
                    INSERT INTO current_projections
                      (tenant_id, workspace_id, item_id,
                       derived_from_decision_id, payload)
                    VALUES (:t, :w, 'i', 'r', '{}'::jsonb)
                    """
                ),
                {"t": TENANT, "w": WORKSPACE_A},
            )
            _ = connection.execute(
                text(
                    """
                    INSERT INTO audit_segments
                      (tenant_id, workspace_id, segment_id, state)
                    VALUES (:t, :w, 'seg', 'open')
                    """
                ),
                {"t": TENANT, "w": WORKSPACE_A},
            )
            _ = connection.execute(
                text(
                    "INSERT INTO audit_events "
                    "(tenant_id,workspace_id,segment_id,seq,event_id,event_type,actor,"
                    "subject_id,causation_id,correlation_id,payload,payload_hash,"
                    "previous_checksum,checksum,created_at) VALUES "
                    "(:t,:w,'seg',1,'event','cycle','system','i','cause','corr',"
                    "'{}'::jsonb,:payload_hash,:previous,:checksum,:now)"
                ),
                {
                    "t": TENANT,
                    "w": WORKSPACE_A,
                    "payload_hash": "d" * 64,
                    "previous": "0" * 64,
                    "checksum": "e" * 64,
                    "now": datetime.now(UTC),
                },
            )
            _ = connection.execute(
                text(
                    """
                    INSERT INTO transactional_outbox
                      (tenant_id, workspace_id, outbox_id, idempotency_key,
                       state, payload)
                    VALUES (:t, :w, 'o', 'key', 'pending', '{}'::jsonb)
                    """
                ),
                {"t": TENANT, "w": WORKSPACE_A},
            )
            msg = "crash injection"
            raise RuntimeError(msg)
    except RuntimeError:
        pass
    counts: dict[str, int] = {}
    with engine.begin() as connection:
        _set_scope(connection, WORKSPACE_A)
        for table in tables:
            counts[table] = cast(
                "int",
                connection.execute(COUNT_SQL[table]).scalar_one(),
            )
    _require(
        all(value == 0 for value in counts.values()),
        "crash injection must roll back every internal table",
    )
    return {"rollback_counts": counts, "atomic": True}


def _write_receipt(mode: str, *, passed: bool, detail: object) -> None:
    configured = os.environ.get("WF_HARNESS_ARTIFACT")
    artifact = Path(configured) if configured else ROOT / FALLBACK_BY_MODE[mode]
    artifact.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": "1.0.0",
        "kind": "platform_harness_receipt",
        "mode": mode,
        "passed": passed,
        "detail": detail,
    }
    temporary = artifact.with_suffix(f"{artifact.suffix}.tmp")
    _ = temporary.write_text(
        f"{json.dumps(receipt, indent=2, sort_keys=True)}\n",
        encoding="utf-8",
    )
    _ = temporary.replace(artifact)


def main() -> int:
    """Run one selected platform harness against real local services."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--mode", choices=tuple(FALLBACK_BY_MODE), required=True)
    args = parser.parse_args()
    mode = str(args.mode)
    engine = create_engine(_database_url(), pool_pre_ping=True)
    functions: dict[str, Callable[[Engine], dict[str, object]]] = {
        "rls": _run_rls,
        "evidence": _run_evidence,
        "audit": _run_audit,
        "queue": _run_queue,
        "worker": _run_worker,
        "scheduler": _run_scheduler,
        "durability": _run_durability,
    }
    try:
        detail = functions[mode](engine)
    except Exception as exc:
        _write_receipt(
            mode,
            passed=False,
            detail={"error": f"{type(exc).__name__}: {exc}"},
        )
        raise
    finally:
        engine.dispose()
    _write_receipt(mode, passed=True, detail=detail)
    print(json.dumps({"mode": mode, "passed": True, "detail": detail}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

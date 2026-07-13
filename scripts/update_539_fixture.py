#!/usr/bin/env python3
"""Verify or explicitly approve reviewed hashes for the frozen #539 corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Final

from work_frontier.adapters.reference_539 import (
    load_reference_corpus,
    reference_source_items,
)
from work_frontier.application.ingestion import build_ingestion_snapshot
from work_frontier.application.ports.ingestion import IngestionCommand
from work_frontier.domain.frontier import solve_frontier

ROOT: Final = Path(__file__).resolve().parents[1]
FIXTURE_ROOT: Final = ROOT / "contracts" / "fixtures" / "539"
_HASH: Final = "a" * 64


def _command() -> IngestionCommand:
    return IngestionCommand(
        tenant_id="tenant",
        workspace_id="workspace",
        connection_id="github",
        cycle_id="cycle",
        snapshot_id="snapshot",
        graph_revision="graph-539",
        policy_bundle_id="policy-539",
        policy_bundle_hash=_HASH,
        ranking_pipeline_hash=_HASH,
        engine_version="engine-1",
        normalization_profile_version="github-539-v1",
        causation_id="cause",
        correlation_id="correlation",
        outbox_id="outbox",
        outbox_idempotency_key="539-replay",
        computed_at_iso="2026-07-13T00:00:00+00:00",
        changed_item_ids=(),
    )


def _decision_set_hash() -> str:
    corpus = load_reference_corpus(FIXTURE_ROOT)
    build = build_ingestion_snapshot(
        _command(),
        reference_source_items(corpus),
        source_revision="observed",
    )
    return solve_frontier(build.snapshot).payload_hash


def _issues_hash() -> str:
    return hashlib.sha256((FIXTURE_ROOT / "issues.json").read_bytes()).hexdigest()


def main() -> int:
    """Check reviewed hashes or write them only with exact explicit approvals."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--approve-issues-sha")
    _ = parser.add_argument("--approve-decision-set-sha")
    args = parser.parse_args()

    issues_hash = _issues_hash()
    decision_hash = _decision_set_hash()
    manifest_path = FIXTURE_ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        msg = "#539 fixture manifest must be an object"
        raise TypeError(msg)

    if args.approve_issues_sha is not None:
        if args.approve_issues_sha != issues_hash:
            msg = "approved issues hash does not match the reviewed fixture bytes"
            raise SystemExit(msg)
        manifest["issues_sha256"] = issues_hash
        _ = manifest_path.write_text(
            f"{json.dumps(manifest, indent=2, sort_keys=True)}\n",
            encoding="utf-8",
        )
    elif manifest.get("issues_sha256") != issues_hash:
        msg = "#539 fixture bytes changed without explicit hash approval"
        raise SystemExit(msg)

    golden_path = FIXTURE_ROOT / "decision-set.sha256"
    if args.approve_decision_set_sha is not None:
        if args.approve_decision_set_sha != decision_hash:
            msg = (
                "approved DecisionRecord-set hash does not match current engine output"
            )
            raise SystemExit(msg)
        _ = golden_path.write_text(f"{decision_hash}\n", encoding="utf-8")
    elif golden_path.read_text(encoding="utf-8").strip() != decision_hash:
        msg = "#539 DecisionRecord-set golden changed without explicit approval"
        raise SystemExit(msg)

    print(
        json.dumps(
            {
                "decision_set_sha256": decision_hash,
                "issues_sha256": issues_hash,
                "verified": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Deterministic read-only setup environment detection."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from work_frontier.application.ports.setup import SystemProbe
from work_frontier.contracts.setup import DetectionSnapshot, SetupProfile


def detect_environment(
    profile: SetupProfile,
    config_revision: str,
    probe: SystemProbe,
) -> DetectionSnapshot:
    """Return a sorted canonical snapshot from read-only probes."""
    checks = tuple(sorted(probe.detect(profile), key=lambda check: check.check_id))
    canonical = json.dumps(
        {
            "profile": profile.value,
            "config_revision": config_revision,
            "checks": [check.model_dump(mode="json") for check in checks],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    snapshot_id = hashlib.sha256(canonical.encode()).hexdigest()
    return DetectionSnapshot(
        snapshot_id=snapshot_id,
        profile=profile,
        config_revision=config_revision,
        checks=checks,
    )

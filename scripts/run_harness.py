#!/usr/bin/env python3
"""CLI for registry-backed harness execution and foundation recertification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from work_frontier.contracts.harness_registry import (  # noqa: E402
    load_registry,
    validate_registry,
)
from work_frontier.contracts.harness_runner import (  # noqa: E402
    CertificationError,
    recertify_foundation,
    run_harness,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", help="Harness ID to run (e.g. WF-HAR-STATIC-02)")
    parser.add_argument(
        "--recertify-foundation",
        action="store_true",
        help="Run the foundation closure and write supersession evidence",
    )
    parser.add_argument(
        "--validate-registry",
        action="store_true",
        help="Validate contracts/harness-registry.json only",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help="Repository root (default: detected from script location)",
    )
    args = parser.parse_args()

    if args.validate_registry:
        registry = load_registry(args.repo_root / "contracts" / "harness-registry.json")
        validate_registry(registry)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "harness_count": registry["harness_count"],
                    "standard_blocker_count": registry["standard_blocker_count"],
                },
                indent=2,
            )
        )
        return 0

    if args.recertify_foundation:
        try:
            report = recertify_foundation(repo_root=args.repo_root)
        except CertificationError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(report, indent=2))
        return 0

    if not args.id:
        parser.error("provide --id or --recertify-foundation or --validate-registry")

    record = run_harness(args.id, repo_root=args.repo_root)
    print(record.model_dump_json(indent=2))
    return 0 if record.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate F1-F4 audits and close them only after explicit human approval."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Final, cast

ROOT: Final = Path(__file__).resolve().parents[1]
PLAN: Final = ROOT / ".omo" / "plans" / "full-product-implementation.md"
EVIDENCE: Final = ROOT / ".omo" / "evidence" / "final"
_AUDITS: Final = (
    "final-plan-compliance.json",
    "final-code-quality.json",
    "final-manual-qa.json",
    "final-scope-fidelity.json",
)


def _run(*args: str) -> None:
    completed = subprocess.run(list(args), cwd=ROOT, check=False, text=True)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _validate_audits() -> None:
    for filename in _AUDITS:
        path = EVIDENCE / filename
        if not path.is_file():
            msg = f"missing final audit evidence: {path}"
            raise SystemExit(msg)
        raw: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            msg = f"invalid final audit evidence: {path}"
            raise SystemExit(msg)
        payload = cast("dict[str, object]", raw)
        if payload.get("status") != "approved" and filename != "final-manual-qa.json":
            msg = f"final audit is not approved: {path}"
            raise SystemExit(msg)
        if filename == "final-manual-qa.json" and payload.get("approved") is not True:
            msg = "manual QA attestation is not approved"
            raise SystemExit(msg)


def _close_final_gates() -> None:
    content = PLAN.read_text(encoding="utf-8")
    for gate in ("F1", "F2", "F3", "F4"):
        marker = f"- [ ] {gate}."
        if content.count(marker) != 1:
            msg = f"expected one open {gate} marker"
            raise SystemExit(msg)
        content = content.replace(marker, f"- [x] {gate}.", 1)
    content = content.replace(
        (
            "F1-F4 remain open pending surfaced audit results and explicit "
            "user acceptance."
        ),
        "F1-F4 are explicitly accepted; the full implementation plan is complete.",
        1,
    )
    _ = PLAN.write_text(content, encoding="utf-8")


def main() -> int:
    """Run audits; require a second explicit invocation to approve them."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--manual-qa-attestation", type=Path, required=True)
    _ = parser.add_argument("--approve", action="store_true")
    args = parser.parse_args()
    plan = PLAN.read_text(encoding="utf-8")
    missing = [item for item in range(1, 36) if f"- [x] {item}." not in plan]
    if missing:
        msg = f"implementation todos remain open: {missing}"
        raise SystemExit(msg)
    _run(
        "uv",
        "run",
        "python",
        "scripts/run_final_audits.py",
        "--manual-qa-attestation",
        str(args.manual_qa_attestation),
    )
    _validate_audits()
    if not args.approve:
        print(f"Final audit evidence is ready under {EVIDENCE}")
        print(
            "Review it, then rerun with --approve and WF_FINAL_APPROVAL=APPROVE_F1_F4"
        )
        return 0
    if os.environ.get("WF_FINAL_APPROVAL") != "APPROVE_F1_F4":
        msg = "explicit approval requires WF_FINAL_APPROVAL=APPROVE_F1_F4"
        raise SystemExit(msg)
    _close_final_gates()
    _run(
        "python3",
        "scripts/check_anatomy_drift.py",
        "docs/anatomy",
        "--repo-root",
        ".",
        "--mode",
        "update",
        "--generator-version",
        "anatomy-skill@1.0.0",
    )
    _run("git", "diff", "--check")
    print("F1-F4 marked [x] after explicit human approval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

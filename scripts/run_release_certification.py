#!/usr/bin/env python3
"""Run all 68 harnesses once and sign a Standard ReleaseCertification."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Final, cast

ROOT: Final = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from cryptography.hazmat.primitives import serialization  # noqa: E402

from work_frontier.contracts.evidence_writer import (  # noqa: E402
    generate_run_id,
    get_git_commit_sha,
    get_git_tree_sha,
    is_working_tree_clean,
)
from work_frontier.contracts.harness_registry import (  # noqa: E402
    load_registry,
    validate_registry,
)
from work_frontier.contracts.harness_runner import (  # noqa: E402
    run_harness,
    validate_evidence_record,
)
from work_frontier.contracts.release_certification import (  # noqa: E402
    collect_evidence,
    load_private_key,
    sign_certification,
    verify_certification,
)

EVIDENCE_BASE: Final = ROOT / ".omo" / "evidence" / "release"


def _version(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return (result.stdout or result.stderr).strip().splitlines()[0]


def _write_sbom(subject_sha: str, output: Path) -> None:
    files = ("uv.lock", "pnpm-lock.yaml", "pyproject.toml", "frontend/package.json")
    components: list[dict[str, str]] = []
    for name in files:
        path = ROOT / name
        components.append(
            {
                "path": name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    _ = output.write_text(
        json.dumps(
            {
                "bomFormat": "CycloneDX",
                "specVersion": "1.6",
                "serialNumber": f"urn:uuid:work-frontier-{subject_sha}",
                "components": components,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    """Run the canonical registry and sign exact-revision evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--key-id", default=os.environ.get("WF_RELEASE_KEY_ID"))
    args = parser.parse_args()
    if not is_working_tree_clean(ROOT):
        msg = "release certification requires a clean exact revision"
        raise SystemExit(msg)
    key_b64 = os.environ.get("WF_RELEASE_SIGNING_KEY_B64", "")
    if not key_b64 or not args.key_id:
        msg = "set WF_RELEASE_SIGNING_KEY_B64 and WF_RELEASE_KEY_ID for Ed25519 signing"
        raise SystemExit(msg)
    registry = load_registry(ROOT / "contracts" / "harness-registry.json")
    validate_registry(registry)
    raw_harnesses = registry.get("harnesses")
    if not isinstance(raw_harnesses, list):
        msg = "registry harnesses must be a JSON array"
        raise SystemExit(msg)
    typed_harnesses = cast("list[object]", raw_harnesses)
    if len(typed_harnesses) != 68:
        msg = "registry must contain exactly 68 harness entries"
        raise SystemExit(msg)
    harnesses: list[dict[str, object]] = []
    for raw_harness in typed_harnesses:
        if not isinstance(raw_harness, dict):
            msg = "registry harness entries must be JSON objects"
            raise SystemExit(msg)
        harnesses.append(cast("dict[str, object]", raw_harness))

    subject_sha = get_git_commit_sha(ROOT)
    tree_sha = get_git_tree_sha(ROOT)
    run_id = generate_run_id()
    evidence_root = EVIDENCE_BASE / subject_sha / run_id
    evidence_root.mkdir(parents=True)
    for harness in harnesses:
        harness_id = str(harness["id"])
        record = run_harness(
            harness_id,
            repo_root=ROOT,
            evidence_root=evidence_root,
            run_id=run_id,
        )
        failures = validate_evidence_record(
            record,
            registry=registry,
            expected_subject_sha=subject_sha,
            expected_subject_tree_sha=tree_sha,
            require_blocking_pass=True,
            repo_root=ROOT,
        )
        if failures:
            raise SystemExit("\n".join(failures))
        if bool(harness.get("blocks_release")) and record.status != "pass":
            msg = f"blocking harness did not pass: {harness_id}"
            raise SystemExit(msg)
        if record.status not in {"pass", "not_applicable"}:
            msg = f"unsupported release status: {harness_id}={record.status}"
            raise SystemExit(msg)

    evidence = collect_evidence(
        registry_ids=tuple(str(item["id"]) for item in harnesses),
        evidence_root=evidence_root,
        subject_sha=subject_sha,
    )
    private = load_private_key(key_b64)
    certification = sign_certification(
        subject_sha=subject_sha,
        service_versions=(
            ("python", _version(["python3", "--version"])),
            ("node", _version(["node", "--version"])),
            ("pnpm", _version(["pnpm", "--version"])),
        ),
        evidence=evidence,
        private_key=private,
        key_id=args.key_id,
    )
    cert_path = EVIDENCE_BASE / subject_sha / "release-certification.json"
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    _ = cert_path.write_text(certification.canonical_json() + "\n", encoding="utf-8")
    public_raw = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_path = EVIDENCE_BASE / subject_sha / "release-public-key.json"
    _ = public_path.write_text(
        json.dumps(
            {
                "key_id": args.key_id,
                "public_key_b64": base64.b64encode(public_raw).decode(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_sbom(subject_sha, EVIDENCE_BASE / subject_sha / "sbom.cdx.json")
    _ = verify_certification(
        certification,
        private.public_key(),
        expected_subject_sha=subject_sha,
        evidence_root=evidence_root,
    )
    print(cert_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

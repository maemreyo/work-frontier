#!/usr/bin/env python3
"""Execute security controls and write one declared evidence artifact."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
ARTIFACT = Path(
    os.environ.get("WF_HARNESS_ARTIFACT", ".omo/evidence/security/final-security.json")
)


def run(*args: str) -> str:
    """Run one command and return combined output."""
    completed = subprocess.run(
        list(args),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit((completed.stdout or "") + (completed.stderr or ""))
    return (completed.stdout or "") + (completed.stderr or "")


def pytest(*paths: str) -> str:
    return run("uv", "run", "pytest", "-q", *paths)


def dependency_audit() -> str:
    output = run("uv", "run", "pip-audit", "--strict")
    output += run("pnpm", "--dir", "frontend", "audit", "--audit-level", "high")
    return output


def zap_baseline() -> str:
    import httpx

    health_url = "http://127.0.0.1:8001/healthz"
    process: subprocess.Popen[bytes] | None = None
    try:
        try:
            healthy = httpx.get(health_url, timeout=1).status_code == 200
        except httpx.HTTPError:
            healthy = False
        if not healthy:
            process = subprocess.Popen(
                [
                    "uv",
                    "run",
                    "uvicorn",
                    "work_frontier.interfaces.processes.web:build_web_process",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8001",
                ],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    if httpx.get(health_url, timeout=1).status_code == 200:
                        break
                except httpx.HTTPError:
                    time.sleep(0.25)
            else:
                msg = "web process did not become healthy for ZAP"
                raise SystemExit(msg)
        target = os.environ.get(
            "WF_ZAP_TARGET",
            "http://host.docker.internal:8001",
        )
        report_dir = ROOT / ".omo" / "evidence" / "security" / "zap"
        report_dir.mkdir(parents=True, exist_ok=True)
        output = run(
            "docker",
            "run",
            "--rm",
            "--add-host",
            "host.docker.internal:host-gateway",
            "-v",
            f"{report_dir}:/zap/wrk:rw",
            "-t",
            "ghcr.io/zaproxy/zaproxy:stable",
            "zap-baseline.py",
            "-t",
            target,
            "-J",
            "zap.json",
            "-I",
        )
        raw_payload: object = json.loads(
            (report_dir / "zap.json").read_text(encoding="utf-8")
        )
        rendered = json.dumps(raw_payload)
        if '"riskcode": "3"' in rendered or '"riskcode": "2"' in rendered:
            msg = "ZAP reported medium or high findings"
            raise SystemExit(msg)
        return output
    finally:
        if process is not None:
            process.terminate()
            try:
                _ = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                _ = process.kill()
                _ = process.wait()


def main() -> int:
    """Run one security harness mode."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--mode",
        required=True,
        choices=(
            "auth",
            "input",
            "ssrf",
            "csrf",
            "rate",
            "dependency",
            "tls",
            "safety",
            "override",
            "authority",
        ),
    )
    args = parser.parse_args()
    if args.mode == "auth":
        output = pytest("backend/tests/integration/test_web_server.py")
    elif args.mode == "input":
        output = pytest("backend/tests/security/test_hardening.py") + zap_baseline()
    elif args.mode == "ssrf":
        output = pytest(
            "backend/tests/security/test_hardening.py::test_https_allowlisted_egress_only"
        )
    elif args.mode == "csrf":
        output = pytest(
            "backend/tests/security/test_hardening.py::test_csrf_tokens_are_session_bound"
        )
    elif args.mode == "rate":
        output = pytest(
            "backend/tests/security/test_hardening.py::test_rate_limiter_uses_clock_controlled_window"
        )
    elif args.mode == "dependency":
        output = dependency_audit()
    elif args.mode == "tls":
        output = pytest(
            "backend/tests/security/test_hardening.py::test_tls_configuration_fails_closed"
        )
    elif args.mode == "safety":
        output = pytest("backend/tests/domain/test_policy_gates.py")
    elif args.mode == "override":
        output = pytest("backend/tests/domain/test_proposals.py")
    else:
        output = pytest("backend/tests/security/test_authorization_identity.py")
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    _ = ARTIFACT.write_text(
        json.dumps(
            {"mode": args.mode, "status": "passed", "output": output[-4_000:]},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

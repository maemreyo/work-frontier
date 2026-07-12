#!/usr/bin/env python3
"""Check the local Work Frontier development toolchain without third-party imports."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess  # nosec - fixed tool-version probes only
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_version(command: list[str]) -> tuple[bool, str]:
    executable = shutil.which(command[0])
    if executable is None:
        return False, "not found"
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    output = (completed.stdout or completed.stderr).strip().splitlines()
    text = output[0] if output else f"exit {completed.returncode}"
    return completed.returncode == 0, text


def read_expected_versions() -> dict[str, str]:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    return {
        "python": (ROOT / ".python-version").read_text(encoding="utf-8").strip(),
        "node": package["engines"]["node"],
        "pnpm": package["engines"]["pnpm"],
    }


def python_executable() -> list[str]:
    """Return the Python interpreter uv would use for this repo.

    The repo pins Python via ``.python-version`` and resolves it through uv.
    Calling ``python3 --version`` from ``PATH`` returns the system Python,
    which is not the Python that runs ``uv run`` commands. Prefer the uv
    interpreter when uv is available; fall back to ``sys.executable``
    only when uv is missing.
    """
    if shutil.which("uv") is not None:
        return ["uv", "run", "python", "--version"]
    return [sys.executable, "--version"]


def normalized_version(text: str) -> str:
    for token in text.replace("v", " ").split():
        if token and token[0].isdigit():
            return token
    return text.strip()


def main() -> int:
    expected = read_expected_versions()
    checks = [
        ("git", ["git", "--version"], None, True),
        ("python", python_executable(), expected["python"], True),
        ("uv", ["uv", "--version"], None, True),
        ("node", ["node", "--version"], expected["node"], True),
        ("pnpm", ["pnpm", "--version"], expected["pnpm"], True),
        ("docker", ["docker", "--version"], None, False),
        ("docker compose", ["docker", "compose", "version"], None, False),
    ]

    print(f"Work Frontier doctor on {platform.system()} {platform.release()}")
    print(f"Repository: {ROOT}")
    failures = 0
    warnings = 0

    for name, command, wanted, required in checks:
        ok, output = run_version(command)
        status = "OK"
        detail = output

        if not ok:
            if required:
                status = "FAIL"
                failures += 1
            else:
                status = "WARN"
                warnings += 1
        elif wanted is not None and normalized_version(output) != wanted:
            status = "FAIL"
            failures += 1
            detail = f"{output} (expected {wanted})"

        print(f"[{status:4}] {name:14} {detail}")

    env_file = ROOT / ".env"
    if env_file.exists():
        print("[OK  ] .env           present")
    else:
        print(
            "[INFO] .env           absent; copy .env.example for "
            "manual infrastructure work"
        )

    if failures:
        print(
            f"\nDoctor found {failures} blocking problem(s) and {warnings} warning(s)."
        )
        return 1
    print(f"\nDoctor passed with {warnings} optional warning(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

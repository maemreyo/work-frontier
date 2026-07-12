"""Helper for writing validated evidence records to the standard location."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime

    from work_frontier.contracts.evidence_record import (
        Artifact,
        JsonValue,
        Result,
    )


def get_git_commit_sha(repo_root: Path | None = None) -> str:
    """Return the current git commit SHA for the repository."""
    if repo_root is None:
        repo_root = Path.cwd()
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_tool_version(tool_name: str) -> str:
    """Return version string for a tool (stub for now)."""
    _ = tool_name  # TODO: extend per tool
    return "1.0.0"


def get_environment_fingerprint() -> dict[str, str]:
    """Return environment fingerprint for reproducibility."""
    import platform
    import sys

    return {
        "python": sys.version.split()[0],
        "os": f"{platform.system().lower()}-{platform.machine()}",
        "platform": platform.platform(),
    }


def generate_run_id() -> str:
    """Generate a unique run identifier from timestamp and PID."""
    import time

    return f"run-{int(time.time() * 1000)}"


def _relative_workdir(working_directory: str | None, repo_root: Path) -> str:
    if working_directory is None:
        return "."

    workdir_path = Path(working_directory).resolve()
    repo_root_resolved = repo_root.resolve()

    if workdir_path == repo_root_resolved:
        return "."

    try:
        return str(workdir_path.relative_to(repo_root_resolved))
    except ValueError:
        return str(workdir_path)


def write_evidence(
    *,
    harness_id: str,
    status: Literal["pass", "fail", "skip", "not_applicable"],
    command: str,
    exit_code: int,
    working_directory: str | None,
    start_time: datetime,
    end_time: datetime,
    tool_name: str,
    artifacts: list[Artifact] | None = None,
    results: list[Result] | None = None,
    property_bag: dict[str, JsonValue] | None = None,
    output_filename: str,
    repo_root: Path | None = None,
    run_id: str | None = None,
) -> Path:
    """Write a validated evidence record to .omo/evidence/static/{output_filename}."""
    from work_frontier.contracts.evidence_record import (
        EvidenceRecord,
        Invocation,
        Tool,
    )

    if repo_root is None:
        repo_root = Path.cwd()

    duration_seconds = (end_time - start_time).total_seconds()
    commit_sha = get_git_commit_sha(repo_root)
    tool_version = get_tool_version(tool_name)

    invocation = Invocation(
        command=command,
        exit_code=exit_code,
        working_directory=_relative_workdir(working_directory, repo_root),
        start_time=start_time,
        end_time=end_time,
        duration_seconds=duration_seconds,
    )

    tool = Tool(
        name=tool_name,
        version=tool_version,
        commit_sha=commit_sha,
    )

    evidence = EvidenceRecord(
        schema_version="1.0.0",
        harness_id=harness_id,
        status=status,
        run_id=run_id or generate_run_id(),
        subject_sha=commit_sha,
        invocation=invocation,
        tool=tool,
        environment=get_environment_fingerprint(),
        artifacts=artifacts or [],
        results=results or [],
        property_bag=property_bag,
    )

    evidence_dir = repo_root / ".omo" / "evidence" / "static"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / output_filename

    content = evidence.model_dump_json(indent=2, by_alias=False)
    _ = evidence_path.write_text(f"{content}\n", encoding="utf-8")

    return evidence_path

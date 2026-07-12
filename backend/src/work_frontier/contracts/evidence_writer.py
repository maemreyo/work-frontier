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


def write_evidence(
    *,
    harness_id: str,
    status: Literal["pass", "fail", "skip"],
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
) -> Path:
    """Write a validated evidence record to .omo/evidence/static/{output_filename}.

    Args:
        harness_id: Unique harness identifier (pattern WF-HAR-{CATEGORY}-{NN})
        status: Overall status ("pass", "fail", or "skip")
        command: Full command invoked by the harness
        exit_code: Process exit code
        working_directory: Working directory where command was executed
        start_time: ISO 8601 timestamp when execution started
        end_time: ISO 8601 timestamp when execution completed
        tool_name: Tool name (e.g., pytest, mypy, ruff)
        artifacts: Files or resources examined or produced
        results: Individual test results or findings
        property_bag: Extension point for harness-specific data
        output_filename: Filename for the evidence record
        (e.g., "import-boundaries.json")
        repo_root: Repository root path (defaults to current directory)

    Returns:
        Path to the written evidence file
    """
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
        working_directory=working_directory,
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
        invocation=invocation,
        tool=tool,
        artifacts=artifacts or [],
        results=results or [],
        property_bag=property_bag,
    )

    # Write to .omo/evidence/static/{output_filename}
    evidence_dir = repo_root / ".omo" / "evidence" / "static"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / output_filename

    # Serialize with Pydantic's JSON serialization
    content = evidence.model_dump_json(indent=2, by_alias=False)
    _ = evidence_path.write_text(f"{content}\n", encoding="utf-8")

    return evidence_path

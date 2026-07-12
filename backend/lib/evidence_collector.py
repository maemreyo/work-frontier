"""Evidence collector for verification harness execution.

Builds EvidenceRecord instances by accumulating results and artifacts during
harness execution, then finalizing with invocation metadata.
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Literal

from work_frontier.contracts.evidence_record import (
    Artifact,
    ArtifactHashes,
    EvidenceRecord,
    Invocation,
    JsonValue,
    Result,
    Tool,
)
from work_frontier.contracts.evidence_writer import (
    generate_run_id,
    get_environment_fingerprint,
    get_git_commit_sha,
    get_git_tree_sha,
)


class EvidenceCollector:
    """Collects evidence during harness execution and builds final record.

    Usage:
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0"
        )
        collector.add_result(kind="test", passed=True, detail="test_foo passed")
        collector.add_artifact(Path("coverage.xml"))
        record = collector.build(
            command="pytest tests/",
            exit_code=0,
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc)
        )
    """

    def __init__(
        self,
        harness_id: str,
        tool_name: str,
        tool_version: str,
        repo_root: Path | None = None,
    ) -> None:
        """Initialize collector with harness and tool metadata.

        Args:
            harness_id: Harness identifier matching WF-HAR-{CATEGORY}-{NN}
            tool_name: Name of the tool being executed
            tool_version: Version string of the tool
            repo_root: Repository root for git operations (default: CWD)
        """
        self.harness_id: str = harness_id
        self.tool_name: str = tool_name
        self.tool_version: str = tool_version
        self.repo_root: Path = repo_root if repo_root is not None else Path.cwd()
        self.commit_sha: str = get_git_commit_sha(self.repo_root)
        self.tree_sha: str = get_git_tree_sha(self.repo_root)
        self.results: list[Result] = []
        self.artifacts: list[Artifact] = []

    def add_result(self, kind: str, passed: bool, detail: str | None = None) -> None:
        """Add a test result or finding.

        Args:
            kind: Result type identifier (e.g., "test", "lint", "type-check")
            passed: Whether this specific result passed
            detail: Optional human-readable detail about the result
        """
        self.results.append(Result(kind=kind, passed=passed, detail=detail))

    def add_artifact(self, path: Path) -> None:
        """Add an artifact with SHA-256 hash.

        Args:
            path: Path to the artifact file (must be within repo root)
        """
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        # Convert to repo-relative path for portable certification.
        try:
            rel_path = str(path.resolve().relative_to(self.repo_root.resolve()))
        except ValueError:
            msg = f"artifact path {path} is outside repo root {self.repo_root}"
            raise ValueError(msg) from None
        self.artifacts.append(
            Artifact(path=rel_path, hashes=ArtifactHashes(sha256=sha256))
        )

    def build(
        self,
        command: str,
        exit_code: int,
        start_time: datetime,
        end_time: datetime,
        working_directory: str = ".",
        run_id: str | None = None,
        stdout: str = "",
        stderr: str = "",
        property_bag: dict[str, JsonValue] | None = None,
        repo_root: Path | None = None,
        evidence_root: Path | None = None,
        applicability: Literal["standard", "large", "tenant"] = "standard",
        applicability_reason: str | None = None,
    ) -> EvidenceRecord:
        """Build the final EvidenceRecord.

        Status is determined by:
        - "pass": exit_code == 0 AND all results passed
        - "fail": otherwise

        Args:
            command: Full command invoked by the harness
            exit_code: Process exit code
            start_time: Execution start timestamp (must be timezone-aware)
            end_time: Execution end timestamp (must be timezone-aware)
            working_directory: Optional working directory where command was executed
            run_id: Optional run identifier (auto-generated if not provided)
            stdout: Captured stdout content
            stderr: Captured stderr content
            property_bag: Optional extension data
            repo_root: Repository root for writing log files (default: CWD)
            evidence_root: Directory for evidence log files (default: .omo/evidence/)
            applicability: Harness applicability scope (default: "standard")
            applicability_reason: Reason for the applicability value

        Returns:
            Complete EvidenceRecord ready for serialization
        """
        if exit_code == 0 and all(r.passed for r in self.results):
            status = "pass"
        else:
            status = "fail"

        if repo_root is not None and repo_root != self.repo_root:
            msg = (
                f"repo_root passed to build() ({repo_root}) does not match "
                f"constructor repo_root ({self.repo_root})"
            )
            raise ValueError(msg)
        repo_root = self.repo_root
        if evidence_root is None:
            evidence_root = repo_root / ".omo" / "evidence"

        # Write stdout/stderr to disk so the artifact references point to
        # real files that pass validate_evidence_record's existence check.
        evidence_root.mkdir(parents=True, exist_ok=True)
        stdout_path = evidence_root / f"{self.harness_id}.stdout.txt"
        stderr_path = evidence_root / f"{self.harness_id}.stderr.txt"
        _ = stdout_path.write_text(stdout or "", encoding="utf-8")
        _ = stderr_path.write_text(stderr or "", encoding="utf-8")

        def _hash_bytes(content: str) -> str:
            return hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Compute repo-root-relative paths for the artifact records
        try:
            stdout_rel = str(stdout_path.relative_to(repo_root))
        except ValueError:
            stdout_rel = str(stdout_path)
        try:
            stderr_rel = str(stderr_path.relative_to(repo_root))
        except ValueError:
            stderr_rel = str(stderr_path)

        return EvidenceRecord(
            schema_version="1.0.0",
            harness_id=self.harness_id,
            status=status,
            run_id=run_id or generate_run_id(),
            subject_sha=self.commit_sha,
            subject_tree_sha=self.tree_sha,
            invocation=Invocation(
                command=command,
                exit_code=exit_code,
                working_directory=working_directory,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=(end_time - start_time).total_seconds(),
            ),
            tool=Tool(
                name=self.tool_name,
                version=self.tool_version,
                commit_sha=self.commit_sha,
            ),
            applicability=applicability,
            applicability_reason=(
                applicability_reason
                or f"{applicability.capitalize()} scope harness execution"
            ),
            environment=get_environment_fingerprint(),
            artifacts=self.artifacts,
            results=self.results,
            stdout_artifact=Artifact(
                path=stdout_rel,
                hashes=ArtifactHashes(sha256=_hash_bytes(stdout or "")),
            ),
            stderr_artifact=Artifact(
                path=stderr_rel,
                hashes=ArtifactHashes(sha256=_hash_bytes(stderr or "")),
            ),
            property_bag=property_bag,
        )

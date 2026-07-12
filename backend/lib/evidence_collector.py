"""Evidence collector for verification harness execution.

Builds EvidenceRecord instances by accumulating results and artifacts during
harness execution, then finalizing with invocation metadata.
"""

import hashlib
import subprocess
from datetime import datetime
from pathlib import Path

from backend.contracts.evidence_record import (
    Artifact,
    EvidenceRecord,
    Invocation,
    Result,
    Tool,
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

    def __init__(self, harness_id: str, tool_name: str, tool_version: str) -> None:
        """Initialize collector with harness and tool metadata.

        Args:
            harness_id: Harness identifier matching WF-HAR-{CATEGORY}-{NN}
            tool_name: Name of the tool being executed
            tool_version: Version string of the tool
        """
        self.harness_id: str = harness_id
        self.tool_name: str = tool_name
        self.tool_version: str = tool_version
        self.commit_sha: str = self._get_commit_sha()
        self.results: list[Result] = []
        self.artifacts: list[Artifact] = []

    def _get_commit_sha(self) -> str:
        """Get current git commit SHA.

        Returns:
            40-character hexadecimal commit SHA

        Raises:
            subprocess.CalledProcessError: If git command fails
        """
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()

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
            path: Path to the artifact file
        """
        sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        self.artifacts.append(
            Artifact(path=str(path), hashes={"sha256": sha256})
        )

    def build(
        self,
        command: str,
        exit_code: int,
        start_time: datetime,
        end_time: datetime,
        working_directory: str | None = None,
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

        Returns:
            Complete EvidenceRecord ready for serialization
        """
        if exit_code == 0 and all(r.passed for r in self.results):
            status = "pass"
        else:
            status = "fail"

        return EvidenceRecord(
            schema_version="1.0.0",
            harness_id=self.harness_id,
            status=status,
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
            artifacts=self.artifacts,
            results=self.results,
        )

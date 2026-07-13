from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from work_frontier.contracts.evidence_record import (
    Artifact,
    ArtifactHashes,
    EvidenceRecord,
    Invocation,
    Tool,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)
HASH = "ab" * 32


def artifact(path: str) -> Artifact:
    return Artifact(path=path, hashes=ArtifactHashes(sha256=HASH))


def test_posix_contract_rejects_backslashes_in_working_directory() -> None:
    with pytest.raises(ValidationError, match="POSIX"):
        _ = Invocation(
            command="pytest",
            exit_code=0,
            working_directory=r"backend\tests",
            start_time=NOW,
            end_time=NOW,
            duration_seconds=0,
        )


def test_posix_contract_rejects_backslashes_in_artifact_path() -> None:
    with pytest.raises(ValidationError, match="POSIX"):
        _ = artifact(r"evidence\output.json")


def test_release_stage_defaults_to_pre_ga() -> None:
    record = EvidenceRecord(
        schema_version="1.0.0",
        harness_id="WF-HAR-TEST-01",
        status="pass",
        run_id="run-test",
        subject_sha="a" * 40,
        subject_tree_sha="b" * 40,
        invocation=Invocation(
            command="pytest",
            exit_code=0,
            working_directory=".",
            start_time=NOW,
            end_time=NOW,
            duration_seconds=0,
        ),
        tool=Tool(name="pytest", version="8.4.0", commit_sha="a" * 40),
        applicability="standard",
        applicability_reason="Standard pre-GA contract fixture",
        environment={"os": "test"},
        stdout_artifact=artifact("stdout.txt"),
        stderr_artifact=artifact("stderr.txt"),
    )
    assert record.release_stage == "pre_ga"
    assert record.artifacts == []
    assert record.results == []


def test_schema_publishes_canonical_semantic_rules() -> None:
    schema = EvidenceRecord.model_json_schema()
    rules = schema["x-work-frontier-semantic-rules"]
    assert rules["defaults"] == {
        "artifacts": [],
        "release_stage": "pre_ga",
        "results": [],
    }
    assert "artifacts[].path" in rules["posix_relative_paths"]

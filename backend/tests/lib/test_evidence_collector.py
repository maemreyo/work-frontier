"""Tests for evidence_collector library.

Tests verify the EvidenceCollector correctly accumulates results and artifacts,
computes hashes, determines status, and builds valid EvidenceRecord instances.
"""

import hashlib
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from backend.lib.evidence_collector import EvidenceCollector


class TestEvidenceCollectorInitialization:
    """Tests for EvidenceCollector initialization."""

    def test_initialization_captures_commit_sha(self) -> None:
        """Test that initialization captures the current git commit SHA.

        Given: A git repository with a current commit
        When: EvidenceCollector is initialized
        Then: The commit_sha is captured as a 40-character hex string
        """
        # Given
        expected_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()

        # When
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
        )

        # Then
        assert collector.commit_sha == expected_sha
        assert len(collector.commit_sha) == 40
        assert all(c in "0123456789abcdef" for c in collector.commit_sha)

    def test_initialization_sets_metadata(self) -> None:
        """Test that initialization correctly sets harness and tool metadata.

        Given: Harness and tool metadata
        When: EvidenceCollector is initialized
        Then: Metadata fields are stored correctly
        """
        # When
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
        )

        # Then
        assert collector.harness_id == "WF-HAR-PYTHON-01"
        assert collector.tool_name == "pytest"
        assert collector.tool_version == "8.1.0"
        assert collector.results == []
        assert collector.artifacts == []


class TestEvidenceCollectorResultAccumulation:
    """Tests for result accumulation."""

    def test_add_result_accumulates_results(self) -> None:
        """Test that add_result() correctly accumulates results.

        Given: An initialized collector
        When: Multiple results are added
        Then: All results are accumulated in order
        """
        # Given
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
        )

        # When
        collector.add_result(kind="test", passed=True, detail="test_foo passed")
        collector.add_result(kind="test", passed=False, detail="test_bar failed")
        collector.add_result(kind="lint", passed=True)

        # Then
        assert len(collector.results) == 3
        assert collector.results[0].kind == "test"
        assert collector.results[0].passed is True
        assert collector.results[0].detail == "test_foo passed"
        assert collector.results[1].kind == "test"
        assert collector.results[1].passed is False
        assert collector.results[1].detail == "test_bar failed"
        assert collector.results[2].kind == "lint"
        assert collector.results[2].passed is True
        assert collector.results[2].detail is None


class TestEvidenceCollectorArtifactHandling:
    """Tests for artifact handling and hash computation."""

    def test_add_artifact_computes_sha256_hash(self, tmp_path: Path) -> None:
        """Test that add_artifact() correctly computes SHA-256 hash.

        Given: A file with known content
        When: add_artifact() is called
        Then: The artifact is added with correct SHA-256 hash
        """
        # Given
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
        )
        test_file = tmp_path / "test_artifact.txt"
        test_content = b"test content for hashing"
        _ = test_file.write_bytes(test_content)
        expected_hash = hashlib.sha256(test_content).hexdigest()

        # When
        collector.add_artifact(test_file)

        # Then
        assert len(collector.artifacts) == 1
        assert collector.artifacts[0].path == str(test_file)
        assert collector.artifacts[0].hashes is not None
        assert collector.artifacts[0].hashes["sha256"] == expected_hash

    def test_add_multiple_artifacts(self, tmp_path: Path) -> None:
        """Test that multiple artifacts can be added.

        Given: An initialized collector and multiple files
        When: add_artifact() is called multiple times
        Then: All artifacts are accumulated with their hashes
        """
        # Given
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
        )
        file1 = tmp_path / "artifact1.txt"
        file2 = tmp_path / "artifact2.txt"
        _ = file1.write_bytes(b"content 1")
        _ = file2.write_bytes(b"content 2")

        # When
        collector.add_artifact(file1)
        collector.add_artifact(file2)

        # Then
        assert len(collector.artifacts) == 2
        assert collector.artifacts[0].path == str(file1)
        assert collector.artifacts[1].path == str(file2)


class TestEvidenceCollectorBuildLogic:
    """Tests for EvidenceRecord building and status determination."""

    def test_build_with_all_passed_results_returns_pass(self) -> None:
        """Test that build() returns status='pass' when all results passed.

        Given: A collector with all passing results and exit_code=0
        When: build() is called
        Then: The returned record has status='pass'
        """
        # Given
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
        )
        collector.add_result(kind="test", passed=True)
        collector.add_result(kind="test", passed=True)
        start = datetime.now(UTC)
        end = start + timedelta(seconds=5)

        # When
        record = collector.build(
            command="pytest tests/",
            exit_code=0,
            start_time=start,
            end_time=end,
        )

        # Then
        assert record.status == "pass"

    def test_build_with_failed_result_returns_fail(self) -> None:
        """Test that build() returns status='fail' when any result failed.

        Given: A collector with at least one failing result
        When: build() is called with exit_code=0
        Then: The returned record has status='fail'
        """
        # Given
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
        )
        collector.add_result(kind="test", passed=True)
        collector.add_result(kind="test", passed=False, detail="assertion failed")
        start = datetime.now(UTC)
        end = start + timedelta(seconds=5)

        # When
        record = collector.build(
            command="pytest tests/",
            exit_code=0,
            start_time=start,
            end_time=end,
        )

        # Then
        assert record.status == "fail"

    def test_build_with_nonzero_exit_code_returns_fail(self) -> None:
        """Test that build() returns status='fail' when exit_code is non-zero.

        Given: A collector with all passing results but non-zero exit_code
        When: build() is called
        Then: The returned record has status='fail'
        """
        # Given
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
        )
        collector.add_result(kind="test", passed=True)
        start = datetime.now(UTC)
        end = start + timedelta(seconds=5)

        # When
        record = collector.build(
            command="pytest tests/",
            exit_code=1,
            start_time=start,
            end_time=end,
        )

        # Then
        assert record.status == "fail"

    def test_build_calculates_duration_seconds_correctly(self) -> None:
        """Test that build() calculates duration_seconds from timestamps.

        Given: Start and end timestamps with known difference
        When: build() is called
        Then: duration_seconds matches the time difference
        """
        # Given
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
        )
        start = datetime(2026, 7, 12, 10, 0, 0, tzinfo=UTC)
        end = datetime(2026, 7, 12, 10, 2, 30, tzinfo=UTC)
        expected_duration = 150.0  # 2 minutes 30 seconds

        # When
        record = collector.build(
            command="pytest tests/",
            exit_code=0,
            start_time=start,
            end_time=end,
        )

        # Then
        assert record.invocation.duration_seconds == expected_duration

    def test_build_with_working_directory(self) -> None:
        """Test that build() includes working_directory when provided.

        Given: A working directory path
        When: build() is called with working_directory parameter
        Then: The record includes the working directory
        """
        # Given
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
        )
        start = datetime.now(UTC)
        end = start + timedelta(seconds=5)

        # When
        record = collector.build(
            command="pytest tests/",
            exit_code=0,
            start_time=start,
            end_time=end,
            working_directory="/workspace/project",
        )

        # Then
        assert record.invocation.working_directory == "/workspace/project"

    def test_build_includes_all_metadata(self) -> None:
        """Test that build() includes all harness and tool metadata.

        Given: An initialized collector with metadata
        When: build() is called
        Then: All metadata is present in the record
        """
        # Given
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
        )
        start = datetime.now(UTC)
        end = start + timedelta(seconds=5)

        # When
        record = collector.build(
            command="pytest tests/",
            exit_code=0,
            start_time=start,
            end_time=end,
        )

        # Then
        assert record.schema_version == "1.0.0"
        assert record.harness_id == "WF-HAR-PYTHON-01"
        assert record.tool.name == "pytest"
        assert record.tool.version == "8.1.0"
        assert len(record.tool.commit_sha) == 40


class TestEvidenceRecordSerialization:
    """Tests for EvidenceRecord serialization."""

    def test_evidence_record_serializes_to_json(self, tmp_path: Path) -> None:
        """Test that EvidenceRecord can be serialized to JSON.

        Given: A collector with results and artifacts
        When: build() is called and the record is serialized
        Then: The JSON is valid and contains all expected fields
        """
        # Given
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
        )
        collector.add_result(kind="test", passed=True, detail="test passed")
        test_file = tmp_path / "artifact.txt"
        _ = test_file.write_bytes(b"test content")
        collector.add_artifact(test_file)
        start = datetime(2026, 7, 12, 10, 0, 0, tzinfo=UTC)
        end = start + timedelta(seconds=10)

        # When
        record = collector.build(
            command="pytest tests/",
            exit_code=0,
            start_time=start,
            end_time=end,
            working_directory="/workspace",
        )
        json_str = record.model_dump_json()
        parsed: dict[str, Any] = json.loads(json_str)

        # Then
        assert parsed["schema_version"] == "1.0.0"
        assert parsed["harness_id"] == "WF-HAR-PYTHON-01"
        assert parsed["status"] == "pass"
        assert parsed["invocation"]["command"] == "pytest tests/"
        assert parsed["invocation"]["exit_code"] == 0
        assert parsed["invocation"]["working_directory"] == "/workspace"
        assert parsed["invocation"]["duration_seconds"] == 10.0
        assert parsed["tool"]["name"] == "pytest"
        assert parsed["tool"]["version"] == "8.1.0"
        assert len(parsed["tool"]["commit_sha"]) == 40
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["kind"] == "test"
        assert parsed["results"][0]["passed"] is True
        assert len(parsed["artifacts"]) == 1
        assert "sha256" in parsed["artifacts"][0]["hashes"]

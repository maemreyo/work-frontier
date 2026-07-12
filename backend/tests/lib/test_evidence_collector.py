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

import pytest
from backend.lib.evidence_collector import EvidenceCollector


def _init_temp_git_repo(path: Path, filename: str, content: str) -> str:
    """Initialize a git repo at *path* with one commit containing *content*.

    Returns the commit SHA.
    """
    path.mkdir(parents=True, exist_ok=True)
    _ = subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    _ = subprocess.run(
        ["git", "config", "user.email", "test@test.test"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    _ = subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    file_path = path / filename
    _ = file_path.write_text(content, encoding="utf-8")
    _ = subprocess.run(  # noqa: S603 - controlled test input
        ["git", "add", filename], cwd=path, capture_output=True, check=True
    )
    _ = subprocess.run(  # noqa: S603 - controlled test input
        ["git", "commit", "-m", f"initial commit: {filename}"],
        cwd=path,
        capture_output=True,
        check=True,
    )
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


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

        Given: A file with known content in a temp git repo
        When: add_artifact() is called
        Then: The artifact is added with correct SHA-256 hash and repo-relative path
        """
        # Given
        repo = tmp_path / "repo"
        _ = _init_temp_git_repo(repo, "dummy.txt", "dummy")
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
            repo_root=repo,
        )
        test_file = repo / "test_artifact.txt"
        test_content = b"test content for hashing"
        _ = test_file.write_bytes(test_content)
        expected_hash = hashlib.sha256(test_content).hexdigest()

        # When
        collector.add_artifact(test_file)

        # Then
        assert len(collector.artifacts) == 1
        assert collector.artifacts[0].path == "test_artifact.txt"
        assert collector.artifacts[0].hashes is not None
        assert collector.artifacts[0].hashes.sha256 == expected_hash

    def test_add_multiple_artifacts(self, tmp_path: Path) -> None:
        """Test that multiple artifacts can be added.

        Given: An initialized collector and multiple files in a temp git repo
        When: add_artifact() is called multiple times
        Then: All artifacts are accumulated with their hashes and repo-relative paths
        """
        # Given
        repo = tmp_path / "repo"
        _ = _init_temp_git_repo(repo, "dummy.txt", "dummy")
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
            repo_root=repo,
        )
        file1 = repo / "artifact1.txt"
        file2 = repo / "artifact2.txt"
        _ = file1.write_bytes(b"content 1")
        _ = file2.write_bytes(b"content 2")

        # When
        collector.add_artifact(file1)
        collector.add_artifact(file2)

        # Then
        assert len(collector.artifacts) == 2
        assert collector.artifacts[0].path == "artifact1.txt"
        assert collector.artifacts[1].path == "artifact2.txt"


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
        repo = tmp_path / "repo"
        _ = _init_temp_git_repo(repo, "dummy.txt", "dummy")
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
            repo_root=repo,
        )
        collector.add_result(kind="test", passed=True, detail="test passed")
        test_file = repo / "artifact.txt"
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
        )
        json_str = record.model_dump_json()
        parsed: dict[str, Any] = json.loads(json_str)

        # Then
        assert parsed["schema_version"] == "1.0.0"
        assert parsed["harness_id"] == "WF-HAR-PYTHON-01"
        assert parsed["status"] == "pass"
        assert parsed["invocation"]["command"] == "pytest tests/"
        assert parsed["invocation"]["exit_code"] == 0
        assert parsed["invocation"]["working_directory"] == "."
        assert parsed["invocation"]["duration_seconds"] == 10.0
        assert parsed["tool"]["name"] == "pytest"
        assert parsed["tool"]["version"] == "8.1.0"
        assert len(parsed["tool"]["commit_sha"]) == 40
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["kind"] == "test"
        assert parsed["results"][0]["passed"] is True
        assert len(parsed["artifacts"]) == 1
        assert "sha256" in parsed["artifacts"][0]["hashes"]


class TestEvidenceCollectorRepoRoot:
    """Tests for EvidenceCollector repo_root handling."""

    def test_build_repo_root_mismatch_raises_error(self, tmp_path: Path) -> None:
        """Test that build() raises ValueError when repo_root doesn't match constructor.

        Given: A collector constructed with a specific repo_root
        When: build() is called with a different repo_root
        Then: ValueError is raised
        """
        # Given
        repo_a = tmp_path / "repo_a"
        _ = _init_temp_git_repo(repo_a, "file_a.txt", "content a")
        collector = EvidenceCollector(
            harness_id="WF-HAR-PYTHON-01",
            tool_name="pytest",
            tool_version="8.1.0",
            repo_root=repo_a,
        )
        start = datetime.now(UTC)
        end = start + timedelta(seconds=1)

        # When / Then
        with pytest.raises(ValueError, match="repo_root passed to build"):
            _ = collector.build(
                command="echo hello",
                exit_code=0,
                start_time=start,
                end_time=end,
                repo_root=tmp_path / "other_repo",
            )

    def test_evidence_attests_constructor_repo_root(self, tmp_path: Path) -> None:
        """Test that commit and tree SHAs always come from constructor's repo_root.

        Given: Two separate git repos with different commits
        When: EvidenceCollector is created for each repo
        Then: The commit and tree SHAs match the respective repo
        """
        # Given
        repo_a = tmp_path / "repo_a"
        repo_b = tmp_path / "repo_b"
        sha_a = _init_temp_git_repo(repo_a, "alpha.txt", "alpha content")
        sha_b = _init_temp_git_repo(repo_b, "beta.txt", "beta content")

        # When — collector for repo_a
        collector_a = EvidenceCollector(
            harness_id="WF-HAR-A",
            tool_name="pytest",
            tool_version="8.1.0",
            repo_root=repo_a,
        )
        collector_b = EvidenceCollector(
            harness_id="WF-HAR-B",
            tool_name="pytest",
            tool_version="8.1.0",
            repo_root=repo_b,
        )

        # Then — each collector attests its own repo's SHAs
        assert collector_a.commit_sha == sha_a
        assert collector_b.commit_sha == sha_b
        assert collector_a.commit_sha != collector_b.commit_sha
        assert collector_a.tree_sha != collector_b.tree_sha
        assert all(c in "0123456789abcdef" for c in collector_a.tree_sha)
        assert len(collector_a.tree_sha) == 40

        # When — build() uses the same repo (matching)
        start = datetime.now(UTC)
        end = start + timedelta(seconds=1)
        record_a = collector_a.build(
            command="echo alpha",
            exit_code=0,
            start_time=start,
            end_time=end,
        )
        record_b = collector_b.build(
            command="echo beta",
            exit_code=0,
            start_time=start,
            end_time=end,
        )

        # Then — subject_sha and subject_tree_sha match constructor-captured values
        assert record_a.subject_sha == sha_a
        assert record_a.subject_sha == collector_a.commit_sha
        assert record_a.subject_tree_sha == collector_a.tree_sha
        assert record_b.subject_sha == sha_b
        assert record_b.subject_tree_sha == collector_b.tree_sha

    def test_build_with_matching_repo_root_works(self, tmp_path: Path) -> None:
        """Test that passing the same repo_root to build() works fine.

        Given: A collector with a specific repo_root
        When: build() is called with the same repo_root
        Then: No error is raised and the record is valid
        """
        # Given
        repo = tmp_path / "repo"
        _ = _init_temp_git_repo(repo, "file.txt", "content")
        collector = EvidenceCollector(
            harness_id="WF-HAR-TEST",
            tool_name="pytest",
            tool_version="8.1.0",
            repo_root=repo,
        )
        start = datetime.now(UTC)
        end = start + timedelta(seconds=1)

        # When — pass explicit repo_root matching constructor
        record = collector.build(
            command="echo test",
            exit_code=0,
            start_time=start,
            end_time=end,
            repo_root=repo,
        )

        # Then
        assert record.status == "pass"
        assert record.harness_id == "WF-HAR-TEST"

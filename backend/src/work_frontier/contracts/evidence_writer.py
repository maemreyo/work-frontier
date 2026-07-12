"""Helper for writing validated evidence records to the standard location."""

from __future__ import annotations

import hashlib
import importlib.metadata
import shutil
import subprocess
import sys
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


def get_git_tree_sha(repo_root: Path | None = None) -> str:
    """Return the committed tree SHA of the current HEAD.

    Uses ``git rev-parse HEAD^{tree}`` so the digest reflects exactly what
    is committed at HEAD. Callers must ensure the working tree is clean
    before using this as a source-of-truth digest.
    """
    if repo_root is None:
        repo_root = Path.cwd()
    result = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def is_working_tree_clean(repo_root: Path | None = None) -> bool:
    """Return True iff the working tree matches HEAD and has no untracked files.

    The tree is considered dirty when any tracked file differs from HEAD or
    when an untracked, non-ignored source-of-truth file exists (tracked
    sources, configs, contracts, registry, evidence writers). Untracked
    ephemeral files under .omo/evidence/, .pytest_cache, .ruff_cache,
    __pycache__, frontend/dist, frontend/tsconfig.tsbuildinfo are tolerated.
    """
    if repo_root is None:
        repo_root = Path.cwd()

    # Tracked-file drift (including intent-to-add) must be zero.
    diff = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    if diff.stdout.strip():
        return False

    # Untracked, non-ignored files that affect the foundation.
    porcelain = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=normal",
            "--ignored=no",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return not _has_meaningful_untracked(porcelain.stdout)


_EPHEMERAL_UNTRACKED_PREFIXES = (
    ".omo/evidence/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".basedpyright/",
    ".coverage",
    "htmlcov/",
    "frontend/dist/",
    "frontend/tsconfig.tsbuildinfo",
    "frontend/node_modules/",
    "frontend/coverage/",
    "frontend/.vite/",
    "__pycache__/",
    ".venv/",
)


# Minimum porcelain-v1 line length: status code "??" + space + at least one
# path character. Shorter lines cannot represent an untracked file entry.
_PORCELAIN_MIN_LINE_LEN = 4


def _has_meaningful_untracked(porcelain_stdout: str) -> bool:
    for line in porcelain_stdout.splitlines():
        # Porcelain v1: two chars status + path. Untracked is "??" prefix.
        # Ignored files were filtered out by --ignored=no (we asked for untracked only).
        if not line.strip():
            continue
        if len(line) < _PORCELAIN_MIN_LINE_LEN:
            return True
        if line[:2] != "??":
            # Tracked-file drift would have been caught earlier, but be strict
            # here too in case the working tree was modified between the two
            # calls.
            return True
        path = line[3:].strip()
        if not any(
            path.startswith(prefix) or path == prefix.rstrip("/")
            for prefix in _EPHEMERAL_UNTRACKED_PREFIXES
        ):
            # Anything else counts as meaningful (e.g. a stray script in scripts/,
            # an edited registry, a brand-new test file outside ephemeral dirs).
            return True
    return False


def get_tool_version(tool_name: str) -> str:
    """Return the actual version string for a known tool.

    Never fabricates a version. Unknown tools raise LookupError so callers
    cannot silently claim a hard-coded release.
    """
    name = tool_name.strip().lower()

    if name in {"python", "cpython"}:
        return sys.version.split()[0]

    if name == "node":
        return _run_version(["node", "--version"]).lstrip("v")

    if name == "pnpm":
        return _run_version(["pnpm", "--version"])

    if name in {"pytest", "ruff", "basedpyright", "mypy", "hypothesis"}:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError as exc:
            msg = f"package metadata unavailable for tool {tool_name}"
            raise LookupError(msg) from exc

    if name in {"vitest", "typescript", "tsc", "biome", "zod"}:
        # Prefer package.json packageManager / dependency via pnpm when present.
        pnpm = shutil.which("pnpm")
        if pnpm is not None:
            package = "typescript" if name == "tsc" else name
            try:
                return _run_version(
                    ["pnpm", "--dir", "frontend", "exec", package, "--version"]
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        binary = "tsc" if name == "typescript" else name
        return _run_version([binary, "--version"]).split()[-1]

    if name in {"preflight", "adr-006-preflight", "node-preflight"}:
        return get_tool_version("node")

    if name in {"import-boundaries", "check_import_boundaries"}:
        return get_tool_version("python")

    if name in {"contracts", "generate_contracts"}:
        return get_tool_version("python")

    if name in {"alembic", "migration-smoke"}:
        try:
            return importlib.metadata.version("alembic")
        except importlib.metadata.PackageNotFoundError as exc:
            msg = f"package metadata unavailable for tool {tool_name}"
            raise LookupError(msg) from exc

    if name in {"minio", "storage-smoke", "boto3"}:
        try:
            return importlib.metadata.version("boto3")
        except importlib.metadata.PackageNotFoundError as exc:
            msg = f"package metadata unavailable for tool {tool_name}"
            raise LookupError(msg) from exc

    if name in {"gitleaks", "secret-detection"}:
        return _run_version(["gitleaks", "version"])

    msg = f"no version capture strategy for tool {tool_name!r}"
    raise LookupError(msg)


def _run_version(command: list[str]) -> str:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )
    text = (result.stdout or result.stderr).strip()
    if not text:
        msg = f"empty version output from {' '.join(command)}"
        raise LookupError(msg)
    return text.splitlines()[0].strip()


def get_environment_fingerprint() -> dict[str, str]:
    """Return environment fingerprint for reproducibility."""
    import platform

    fingerprint = {
        "python": sys.version.split()[0],
        "os": f"{platform.system().lower()}-{platform.machine()}",
        "platform": platform.platform(),
    }
    try:
        fingerprint["node"] = get_tool_version("node")
    except (LookupError, subprocess.CalledProcessError, FileNotFoundError):
        pass
    try:
        fingerprint["pnpm"] = get_tool_version("pnpm")
    except (LookupError, subprocess.CalledProcessError, FileNotFoundError):
        pass
    return fingerprint


def generate_run_id() -> str:
    """Generate a unique run identifier using UUIDv4."""
    import uuid

    return f"run-{uuid.uuid4().hex[:12]}"


def hash_bytes(content: bytes) -> str:
    """Return lowercase SHA-256 hex digest for content."""
    return hashlib.sha256(content).hexdigest()


def hash_file(path: Path) -> str:
    """Return lowercase SHA-256 hex digest for a file."""
    return hash_bytes(path.read_bytes())


def write_text_artifact(
    *,
    content: str,
    relative_path: str,
    repo_root: Path,
) -> Artifact:
    """Write a text artifact under *relative_path* relative to *repo_root*."""
    from work_frontier.contracts.evidence_record import Artifact, ArtifactHashes

    path = repo_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = content.encode("utf-8")
    _ = path.write_bytes(encoded)
    return Artifact(
        path=relative_path, hashes=ArtifactHashes(sha256=hash_bytes(encoded))
    )


def write_text_artifact_to_dir(
    *,
    content: str,
    dir_path: Path,
    filename: str,
    repo_root: Path | None = None,
) -> Artifact:
    """Write a text artifact into *dir_path* and return a hashed Artifact."""
    from work_frontier.contracts.evidence_record import Artifact, ArtifactHashes

    if repo_root is None:
        repo_root = Path.cwd()
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / filename
    encoded = content.encode("utf-8")
    _ = file_path.write_bytes(encoded)
    # Construct repo-root-relative path manually to avoid macOS
    # /var → /private/var symlink resolution issues.
    try:
        rel_path = str(file_path.relative_to(repo_root))
    except ValueError:
        rel_path = str(file_path)
    return Artifact(path=rel_path, hashes=ArtifactHashes(sha256=hash_bytes(encoded)))


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
        # Refuse absolute paths outside the repo for certification evidence.
        msg = f"working_directory must be relative to repo root: {working_directory}"
        raise ValueError(msg) from None


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
    stdout: str = "",
    stderr: str = "",
    tool_version: str | None = None,
    evidence_root: Path | None = None,
    applicability: Literal["standard", "large", "tenant"] = "standard",
    applicability_reason: str | None = None,
) -> Path:
    """Write a validated evidence record and its stdout/stderr artifacts.

    *evidence_root* — writable directory for the evidence record and sidecar
    artifacts.  When *None* (default) the legacy flat layout is used:
    ``.omo/evidence/static/``.
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
    tree_sha = get_git_tree_sha(repo_root)
    resolved_version = (
        tool_version if tool_version is not None else get_tool_version(tool_name)
    )
    if not resolved_version:
        msg = f"empty tool version for {tool_name}"
        raise ValueError(msg)

    if evidence_root is None:
        evidence_root = repo_root / ".omo" / "evidence" / "static"

    evidence_root.mkdir(parents=True, exist_ok=True)

    if applicability_reason is None or not applicability_reason.strip():
        if applicability == "standard":
            applicability_reason = (
                "Included in Standard foundation closure defined by "
                "registry.foundation_closure"
            )
        elif applicability == "large":
            applicability_reason = "Large-scope envelope trigger"
        else:
            applicability_reason = "Tenant-scope envelope trigger"

    evidence_stem = Path(output_filename).stem
    stdout_artifact = write_text_artifact_to_dir(
        content=stdout or "",
        dir_path=evidence_root,
        filename=f"{evidence_stem}.stdout.txt",
        repo_root=repo_root,
    )
    stderr_artifact = write_text_artifact_to_dir(
        content=stderr or "",
        dir_path=evidence_root,
        filename=f"{evidence_stem}.stderr.txt",
        repo_root=repo_root,
    )

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
        version=resolved_version,
        commit_sha=commit_sha,
    )

    evidence = EvidenceRecord(
        schema_version="1.0.0",
        harness_id=harness_id,
        status=status,
        run_id=run_id or generate_run_id(),
        subject_sha=commit_sha,
        subject_tree_sha=tree_sha,
        invocation=invocation,
        tool=tool,
        applicability=applicability,
        applicability_reason=applicability_reason,
        environment=get_environment_fingerprint(),
        artifacts=artifacts or [],
        results=results or [],
        stdout_artifact=stdout_artifact,
        stderr_artifact=stderr_artifact,
        property_bag=property_bag,
    )

    evidence_path = evidence_root / output_filename
    content = evidence.model_dump_json(indent=2, by_alias=False)
    _ = evidence_path.write_text(f"{content}\n", encoding="utf-8")

    return evidence_path

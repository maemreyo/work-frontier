"""Strict parser and validator for the frozen oh-my-class #539 corpus."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from work_frontier.application.ports.connections import SourceItem

if TYPE_CHECKING:
    from pathlib import Path

_MARKER = re.compile(
    r"<!--\s*omc-program:(?P<program>[^;]+);\s*issue:(?P<issue>\d+)\s*-->"
)
_BLOCKED_SECTION = re.compile(
    r"^## Blocked by\s*$\n(?P<body>.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
_EDGE_PAIR_LENGTH = 2
_ISSUE_REF = re.compile(r"(?<!\w)#(?P<number>\d+)")


class ReferenceCorpusError(ValueError):
    """Signal a malformed or integrity-invalid frozen reference corpus."""


@dataclass(frozen=True, slots=True)
class ReferenceIssue:
    """One strict API-shaped issue from the frozen corpus."""

    number: int
    title: str
    body: str
    state: str
    labels: tuple[str, ...]
    updated_at: str
    program: str | None
    marker_issue: int | None


@dataclass(frozen=True, slots=True, order=True)
class ReferenceEdge:
    """One blocker edge with explicit provenance."""

    blocker: int
    blocked: int
    provenance: str


@dataclass(frozen=True, slots=True)
class ReferenceCorpus:
    """Validated observed issue corpus plus configured policy edges."""

    repository: str
    observed_at: str
    issues: tuple[ReferenceIssue, ...]
    textual_edges: tuple[ReferenceEdge, ...]
    policy_edges: tuple[ReferenceEdge, ...]
    epics: tuple[int, ...]
    terminals: tuple[int, ...]
    report_issue: int
    issues_sha256: str

    @property
    def effective_edges(self) -> tuple[ReferenceEdge, ...]:
        """Return canonical union of textual and configured policy edges."""
        return tuple(sorted({*self.textual_edges, *self.policy_edges}))


def load_reference_corpus(root: Path) -> ReferenceCorpus:
    """Load and verify the frozen #539 corpus under *root*."""
    issues_path = root / "issues.json"
    expected_path = root / "expected.json"
    manifest_path = root / "manifest.json"
    issues_bytes = issues_path.read_bytes()
    actual_hash = hashlib.sha256(issues_bytes).hexdigest()
    manifest = _object(json.loads(manifest_path.read_text(encoding="utf-8")))
    expected_hash = _string(manifest, "issues_sha256")
    if actual_hash != expected_hash:
        msg = "frozen #539 issue corpus hash does not match manifest"
        raise ReferenceCorpusError(msg)

    document = _object(json.loads(issues_bytes))
    expected = _object(json.loads(expected_path.read_text(encoding="utf-8")))
    repository = _string(document, "repository")
    observed_at = _string(document, "observed_at")
    raw_issues = document.get("issues")
    if not isinstance(raw_issues, list):
        msg = "issues must be a JSON array"
        raise ReferenceCorpusError(msg)
    typed_issues = cast("list[object]", raw_issues)
    issues = tuple(
        sorted(
            (_parse_issue(item) for item in typed_issues),
            key=lambda item: item.number,
        )
    )
    numbers = {issue.number for issue in issues}
    if len(numbers) != len(issues):
        msg = "frozen #539 issue numbers must be unique"
        raise ReferenceCorpusError(msg)

    textual_edges = _textual_edges(issues, numbers)
    epics = _integer_tuple(expected, "epics")
    terminals = _integer_tuple(expected, "terminals")
    report_issue = _integer(expected, "report_issue")
    policy_edges = tuple(
        ReferenceEdge(blocker=blocker, blocked=blocked, provenance="policy")
        for blocker, blocked in _edge_pairs(expected, "policy_edges")
    )
    expected_textual = tuple(
        ReferenceEdge(blocker=blocker, blocked=blocked, provenance="body")
        for blocker, blocked in _edge_pairs(expected, "textual_edges")
    )
    if textual_edges != expected_textual:
        msg = "textual blocker edges do not match the reviewed expected corpus"
        raise ReferenceCorpusError(msg)
    referenced = {
        report_issue,
        *epics,
        *terminals,
        *(edge.blocker for edge in policy_edges),
        *(edge.blocked for edge in policy_edges),
    }
    if not referenced.issubset(numbers):
        msg = "expected #539 references contain unknown issue numbers"
        raise ReferenceCorpusError(msg)
    for issue in issues:
        if issue.marker_issue is not None and issue.marker_issue != issue.number:
            msg = f"marker issue mismatch for #{issue.number}"
            raise ReferenceCorpusError(msg)
    return ReferenceCorpus(
        repository=repository,
        observed_at=observed_at,
        issues=issues,
        textual_edges=textual_edges,
        policy_edges=policy_edges,
        epics=epics,
        terminals=terminals,
        report_issue=report_issue,
        issues_sha256=actual_hash,
    )


def _parse_issue(value: object) -> ReferenceIssue:
    item = _object(value)
    body = _string(item, "body", allow_empty=True)
    marker = _MARKER.search(body)
    labels_raw = item.get("labels", [])
    if not isinstance(labels_raw, list):
        msg = "issue labels must be strings"
        raise ReferenceCorpusError(msg)
    labels = cast("list[object]", labels_raw)
    if any(not isinstance(label, str) for label in labels):
        msg = "issue labels must be strings"
        raise ReferenceCorpusError(msg)
    return ReferenceIssue(
        number=_integer(item, "number"),
        title=_string(item, "title"),
        body=body,
        state=_string(item, "state"),
        labels=tuple(sorted(set(cast("list[str]", labels)))),
        updated_at=_string(item, "updated_at"),
        program=None if marker is None else marker.group("program").strip(),
        marker_issue=None if marker is None else int(marker.group("issue")),
    )


def _textual_edges(
    issues: tuple[ReferenceIssue, ...],
    numbers: set[int],
) -> tuple[ReferenceEdge, ...]:
    edges: set[ReferenceEdge] = set()
    for issue in issues:
        section = _BLOCKED_SECTION.search(issue.body)
        if section is None:
            continue
        for match in _ISSUE_REF.finditer(section.group("body")):
            blocker = int(match.group("number"))
            if blocker not in numbers:
                msg = f"ghost blocker reference #{blocker} in issue #{issue.number}"
                raise ReferenceCorpusError(msg)
            edges.add(ReferenceEdge(blocker, issue.number, "body"))
    return tuple(sorted(edges))


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        msg = "expected a JSON object"
        raise ReferenceCorpusError(msg)
    return cast("dict[str, object]", value)


def _string(
    value: dict[str, object],
    key: str,
    *,
    allow_empty: bool = False,
) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or (not allow_empty and not raw.strip()):
        msg = f"{key} must be a string"
        raise ReferenceCorpusError(msg)
    return raw


def _integer(value: dict[str, object], key: str) -> int:
    raw = value.get(key)
    if isinstance(raw, bool) or not isinstance(raw, int):
        msg = f"{key} must be an integer"
        raise ReferenceCorpusError(msg)
    return raw


def _integer_tuple(value: dict[str, object], key: str) -> tuple[int, ...]:
    raw = value.get(key)
    if not isinstance(raw, list):
        msg = f"{key} must be an array"
        raise ReferenceCorpusError(msg)
    output: list[int] = []
    typed_raw = cast("list[object]", raw)
    for item in typed_raw:
        if isinstance(item, bool) or not isinstance(item, int):
            msg = f"{key} entries must be integers"
            raise ReferenceCorpusError(msg)
        output.append(item)
    return tuple(output)


def _edge_pairs(
    value: dict[str, object],
    key: str,
) -> tuple[tuple[int, int], ...]:
    raw = value.get(key)
    if not isinstance(raw, list):
        msg = f"{key} must be an array"
        raise ReferenceCorpusError(msg)
    pairs: list[tuple[int, int]] = []
    typed_raw = cast("list[object]", raw)
    for item in typed_raw:
        if not isinstance(item, list):
            msg = f"{key} entries must be two-integer arrays"
            raise ReferenceCorpusError(msg)
        pair = cast("list[object]", item)
        if len(pair) != _EDGE_PAIR_LENGTH or any(
            isinstance(part, bool) or not isinstance(part, int) for part in pair
        ):
            msg = f"{key} entries must be two-integer arrays"
            raise ReferenceCorpusError(msg)
        blocker, blocked = cast("list[int]", pair)
        pairs.append((blocker, blocked))
    return tuple(pairs)


def reference_source_items(corpus: ReferenceCorpus) -> tuple[SourceItem, ...]:
    """Adapt the frozen observed corpus without elevating its vocabulary to Domain."""
    policy_by_target: dict[int, list[str]] = {}
    for edge in corpus.policy_edges:
        policy_by_target.setdefault(edge.blocked, []).append(str(edge.blocker))
    return tuple(
        SourceItem(
            source_id=f"github:{corpus.repository}",
            item_id=str(issue.number),
            revision=f"{issue.updated_at}:{issue.number}:{issue.state}",
            title=issue.title,
            body=issue.body,
            state=issue.state,
            labels=issue.labels,
            updated_at=issue.updated_at,
            raw=(("number", issue.number), ("repository", corpus.repository)),
            policy_blockers=tuple(policy_by_target.get(issue.number, ())),
        )
        for issue in corpus.issues
    )

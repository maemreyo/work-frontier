from __future__ import annotations

import json
from pathlib import Path

import pytest

from work_frontier.adapters.connections.file import FileAdapter
from work_frontier.adapters.connections.fixture import FixtureAdapter
from work_frontier.adapters.connections.loader import (
    AdapterLoadError,
    load_builtin_adapter,
)
from work_frontier.adapters.reference_539 import (
    ReferenceCorpusError,
    load_reference_corpus,
)
from work_frontier.application.ports.connections import (
    AdapterError,
    AdapterErrorKind,
    SourceItem,
)

ROOT = Path(__file__).resolve().parents[3] / "contracts" / "fixtures" / "539"


def test_frozen_539_corpus_hash_edges_and_observed_roles_are_pinned() -> None:
    corpus = load_reference_corpus(ROOT)
    assert corpus.report_issue == 539
    assert corpus.epics == (460, 475, 488, 504, 522)
    assert corpus.terminals == (474, 487, 503, 521, 538)
    assert {(edge.blocker, edge.blocked) for edge in corpus.policy_edges} == {
        (538, 503),
        (487, 474),
        (503, 474),
        (521, 474),
    }
    assert len(corpus.issues_sha256) == 64


def test_frozen_539_corpus_rejects_tamper_and_ghost_reference(tmp_path: Path) -> None:
    for name in ("issues.json", "expected.json", "manifest.json"):
        _ = (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    document = json.loads((tmp_path / "issues.json").read_text(encoding="utf-8"))
    document["issues"][0]["title"] = "tampered"
    _ = (tmp_path / "issues.json").write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ReferenceCorpusError, match="hash"):
        _ = load_reference_corpus(tmp_path)

    for name in ("issues.json", "expected.json", "manifest.json"):
        _ = (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    document = json.loads((tmp_path / "issues.json").read_text(encoding="utf-8"))
    document["issues"][1]["body"] += "\n## Blocked by\n#999999\n"
    payload = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    _ = (tmp_path / "issues.json").write_bytes(payload)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    import hashlib

    manifest["issues_sha256"] = hashlib.sha256(payload).hexdigest()
    _ = (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ReferenceCorpusError, match="ghost blocker"):
        _ = load_reference_corpus(tmp_path)


def source_items() -> tuple[SourceItem, ...]:
    return tuple(
        SourceItem(
            source_id="fixture",
            item_id=str(number),
            revision=f"r-{number}",
            title=f"Issue {number}",
            body="",
            state="open",
            labels=("b", "a"),
            updated_at="2026-07-13T00:00:00+00:00",
            raw=(("number", number),),
        )
        for number in (1, 2, 3)
    )


def test_fixture_and_file_adapters_page_identically_and_faults_are_typed(
    tmp_path: Path,
) -> None:
    fixture = FixtureAdapter.from_items(source_items(), "revision")
    first = fixture.list_items(cursor=None, page_size=2)
    assert tuple(item.item_id for item in first.items) == ("1", "2")
    second = fixture.list_items(cursor=first.next_cursor, page_size=2)
    assert second.items[0].item_id == "3"

    path = tmp_path / "source.json"
    _ = path.write_text(
        json.dumps(
            {
                "source_revision": "revision",
                "items": [
                    {
                        "source_id": item.source_id,
                        "item_id": item.item_id,
                        "revision": item.revision,
                        "title": item.title,
                        "body": item.body,
                        "state": item.state,
                        "labels": list(item.labels),
                        "updated_at": item.updated_at,
                        "raw": dict(item.raw),
                    }
                    for item in source_items()
                ],
            }
        ),
        encoding="utf-8",
    )
    file_adapter = FileAdapter(path)
    assert file_adapter.list_items(cursor=None, page_size=10) == fixture.list_items(
        cursor=None,
        page_size=10,
    )
    loaded = load_builtin_adapter("file", fixture_path=path)
    assert loaded.current_revision() == "revision"
    with pytest.raises(AdapterLoadError, match="unsupported"):
        _ = load_builtin_adapter("python:evil.module", fixture_path=None)

    broken = FixtureAdapter.from_items(
        source_items(),
        "revision",
        fault=AdapterErrorKind.RATE_LIMITED,
        retry_after_seconds=7,
    )
    with pytest.raises(AdapterError) as captured:
        _ = broken.current_revision()
    assert captured.value.kind is AdapterErrorKind.RATE_LIMITED
    assert captured.value.retry_after_seconds == 7

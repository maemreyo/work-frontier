from __future__ import annotations

from work_frontier.application.ingestion import (
    affected_item_ids,
    normalize_source_item,
)
from work_frontier.application.ports.connections import SourceItem

_SCENARIOS = 500


def item(number: int, blocker: int | None) -> SourceItem:
    return SourceItem(
        source_id="fixture",
        item_id=str(number),
        revision=f"revision-{number}",
        title=f"Item {number}",
        body="",
        state="open",
        labels=(),
        updated_at="2026-07-12T00:00:00+00:00",
        raw=(("number", number),),
        policy_blockers=() if blocker is None else (str(blocker),),
    )


def test_affected_region_matches_full_reachability_for_500_scenarios() -> None:
    for scenario in range(_SCENARIOS):
        count = 2 + scenario % 20
        values = tuple(
            normalize_source_item(item(number, None if number == 0 else number - 1))
            for number in range(count)
        )
        root = str(scenario % count)
        expected = tuple(str(number) for number in range(int(root), count))
        assert affected_item_ids(values, (root,)) == expected

from __future__ import annotations

import pytest
from pydantic import ValidationError

from work_frontier.contracts.events import EventEnvelope, EventType


def payload(event_type: EventType) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "event_id": f"event-{event_type.value}",
        "event_type": event_type.value,
        "tenant_id": "tenant-1",
        "workspace_id": "workspace-1",
        "causation_id": "cause-1",
        "correlation_id": "correlation-1",
        "payload": {
            "resource_id": "resource-1",
            "revision": "revision-1",
            "attributes": {"attempt": 1},
        },
    }


def test_all_published_event_types_round_trip() -> None:
    for event_type in EventType:
        event = EventEnvelope.model_validate(payload(event_type))
        replay = EventEnvelope.model_validate_json(event.model_dump_json())
        assert replay == event


def test_unknown_or_extra_event_fields_fail_closed() -> None:
    unknown = payload(EventType.SYNC_REQUESTED)
    unknown["event_type"] = "unknown.event"
    with pytest.raises(ValidationError):
        _ = EventEnvelope.model_validate(unknown)

    extra = payload(EventType.SYNC_REQUESTED)
    extra["unexpected"] = True
    with pytest.raises(ValidationError):
        _ = EventEnvelope.model_validate(extra)

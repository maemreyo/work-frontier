"""Immutable branded ULIDs and deterministic monotonic generation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import override

from work_frontier.domain.errors import DomainErrorCode, DomainInvariantError

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_PATTERN = re.compile(r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$")
_MAX_TIMESTAMP = (1 << 48) - 1
_MAX_ENTROPY = (1 << 80) - 1


@dataclass(frozen=True, slots=True, order=True)
class Ulid:
    """Canonical uppercase Crockford-base32 ULID."""

    value: str

    def __post_init__(self) -> None:
        """Validate the canonical Crockford representation."""
        if _ULID_PATTERN.fullmatch(self.value) is None:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_ULID,
                "value",
                "expected canonical 26-character uppercase ULID",
            )

    @override
    def __str__(self) -> str:
        return self.value


class ActorId(Ulid):
    """Actor identity."""


class TenantId(Ulid):
    """Tenant identity."""


class WorkspaceId(Ulid):
    """Workspace identity."""


class ResourceId(Ulid):
    """Base class for resource identities."""


class WorkItemId(ResourceId):
    """WorkItem identity."""


class ProgramId(ResourceId):
    """Program identity."""


class GateId(ResourceId):
    """Gate identity."""


class EvidenceId(ResourceId):
    """EvidenceRecord identity."""


class EdgeId(ResourceId):
    """Edge identity."""


class DecisionId(ResourceId):
    """DecisionRecord identity."""


class ExternalBlockerId(ResourceId):
    """External blocker identity."""


class AttentionItemId(ResourceId):
    """AttentionItem identity."""


class ResourceKind(StrEnum):
    """Kinds accepted by typed graph endpoints."""

    WORK_ITEM = "work_item"
    PROGRAM = "program"
    GATE = "gate"


@dataclass(frozen=True, slots=True)
class ResourceRef:
    """A typed resource endpoint."""

    kind: ResourceKind
    resource_id: ResourceId

    def __post_init__(self) -> None:
        """Validate that the branded identifier matches the resource kind."""
        expected: dict[ResourceKind, type[ResourceId]] = {
            ResourceKind.WORK_ITEM: WorkItemId,
            ResourceKind.PROGRAM: ProgramId,
            ResourceKind.GATE: GateId,
        }
        if not isinstance(self.resource_id, expected[self.kind]):
            raise DomainInvariantError(
                DomainErrorCode.INVALID_SCOPE,
                "resource_id",
                f"{self.kind} requires {expected[self.kind].__name__}",
            )


class MonotonicUlidFactory:
    """Deterministic monotonic ULID factory with caller-supplied time/entropy."""

    __slots__: tuple[str, ...] = ("_last_entropy", "_last_timestamp_ms")

    _last_timestamp_ms: int
    _last_entropy: int

    def __init__(self) -> None:
        """Initialize the local monotonic sequence."""
        self._last_timestamp_ms = -1
        self._last_entropy = -1

    def generate[TUlid: Ulid](
        self,
        id_type: type[TUlid],
        *,
        timestamp_ms: int,
        entropy: int,
    ) -> TUlid:
        """Return a monotonic branded ULID without reading clock or randomness."""
        if not 0 <= timestamp_ms <= _MAX_TIMESTAMP:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_ULID,
                "timestamp_ms",
                "must fit the ULID 48-bit timestamp",
            )
        if not 0 <= entropy <= _MAX_ENTROPY:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_ULID,
                "entropy",
                "must fit the ULID 80-bit randomness component",
            )

        resolved_timestamp = max(timestamp_ms, self._last_timestamp_ms)
        resolved_entropy = entropy
        if resolved_timestamp == self._last_timestamp_ms:
            resolved_entropy = max(entropy, self._last_entropy + 1)
        if resolved_entropy > _MAX_ENTROPY:
            if resolved_timestamp == _MAX_TIMESTAMP:
                raise DomainInvariantError(
                    DomainErrorCode.INVALID_ULID,
                    "entropy",
                    "monotonic ULID space exhausted",
                )
            resolved_timestamp += 1
            resolved_entropy = 0

        self._last_timestamp_ms = resolved_timestamp
        self._last_entropy = resolved_entropy
        numeric = (resolved_timestamp << 80) | resolved_entropy
        encoded = "".join(
            _CROCKFORD[(numeric >> shift) & 31] for shift in range(125, -1, -5)
        )
        return id_type(encoded)

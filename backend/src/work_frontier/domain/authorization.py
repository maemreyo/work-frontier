"""Resource-scoped RBAC, deny rules, separation of duties, and break glass."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Final


class Role(StrEnum):
    """Canonical resource-scoped roles."""

    VIEWER = "viewer"
    BUILDER = "builder"
    COORDINATOR = "coordinator"
    OPERATOR = "operator"
    POLICY_ADMINISTRATOR = "policy_administrator"
    TENANT_ADMINISTRATOR = "tenant_administrator"


class Permission(StrEnum):
    """Permissions required by the platform and Wave-3 workflows."""

    PROGRAM_CREATE = "program.create"
    PROGRAM_READ = "program.read"
    PROGRAM_READ_ALL = "program.read_all"
    PROGRAM_UPDATE = "program.update"
    PROGRAM_DELETE = "program.delete"
    WORK_ITEM_CREATE = "work_item.create"
    WORK_ITEM_READ = "work_item.read"
    WORK_ITEM_UPDATE_OWN = "work_item.update_own"
    WORK_ITEM_UPDATE_ALL = "work_item.update_all"
    WORK_ITEM_CLAIM = "work_item.claim"
    WORK_ITEM_SUBMIT = "work_item.submit"
    DECISION_CREATE = "decision.create"
    DECISION_OVERRIDE = "decision.override"
    DECISION_VIEW_HISTORY = "decision.view_history"
    POLICY_READ = "policy.read"
    POLICY_MANAGE = "policy.manage"
    EVIDENCE_COLLECT = "evidence.collect"
    EVIDENCE_VERIFY = "evidence.verify"
    EVIDENCE_VIEW = "evidence.view"
    PROPOSED_CHANGE_DECIDE = "proposed_change.decide"
    PROPOSED_CHANGE_VIEW = "proposed_change.view"
    CONNECTION_VIEW = "connection.view"
    CONNECTION_CONFIGURE = "connection.configure"
    CONNECTION_RECONNECT = "connection.reconnect"
    WORKSPACE_SETTINGS = "workspace.settings"
    USER_INVITE = "user.invite"
    USER_ASSIGN_ROLE = "user.assign_role"
    AUDIT_VIEW = "audit.view"
    BREAK_GLASS_INVOKE = "break_glass.invoke"


class ScopeKind(StrEnum):
    """Canonical six-level resource scopes."""

    TENANT = "tenant"
    ORGANIZATION = "organization"
    WORKSPACE = "workspace"
    PROGRAM = "program"
    REPOSITORY = "repository"
    CONNECTION = "connection"


_SCOPE_ORDER: Final = {
    ScopeKind.TENANT: 0,
    ScopeKind.ORGANIZATION: 1,
    ScopeKind.WORKSPACE: 2,
    ScopeKind.PROGRAM: 3,
    ScopeKind.REPOSITORY: 4,
    ScopeKind.CONNECTION: 5,
}


@dataclass(frozen=True, slots=True, order=True)
class ScopeSegment:
    """One identified resource level in a scope path."""

    kind: ScopeKind
    resource_id: str

    def __post_init__(self) -> None:
        """Reject blank scope identities."""
        if not self.resource_id.strip():
            msg = "scope resource_id is required"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class ResourceScope:
    """Canonical ancestor path ending at the protected resource."""

    segments: tuple[ScopeSegment, ...]

    def __post_init__(self) -> None:
        """Require a strictly ordered, unique scope path."""
        if not self.segments:
            msg = "resource scope must not be empty"
            raise ValueError(msg)
        positions = tuple(_SCOPE_ORDER[segment.kind] for segment in self.segments)
        if positions != tuple(sorted(set(positions))):
            msg = "resource scope levels must be unique and ordered"
            raise ValueError(msg)

    def contains(self, other: ResourceScope) -> bool:
        """Return whether this scope is an exact ancestor of *other*."""
        return other.segments[: len(self.segments)] == self.segments


@dataclass(frozen=True, slots=True)
class RoleGrant:
    """One explicit role grant bound to a resource scope."""

    actor_id: str
    role: Role
    scope: ResourceScope
    grant_id: str
    revision: int

    def __post_init__(self) -> None:
        """Reject blank grant identities and invalid revisions."""
        if not self.actor_id.strip() or not self.grant_id.strip():
            msg = "role grant actor_id and grant_id are required"
            raise ValueError(msg)
        if self.revision < 1:
            msg = "role grant revision must be positive"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class DenyRule:
    """Explicit deny that overrides all matching grants."""

    actor_id: str
    permission: Permission
    scope: ResourceScope
    reason: str

    def __post_init__(self) -> None:
        """Reject blank deny identities and reasons."""
        if not self.actor_id.strip() or not self.reason.strip():
            msg = "deny rule actor_id and reason are required"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class AccessRequest:
    """One permission check against current grants and denies."""

    actor_id: str
    permission: Permission
    scope: ResourceScope

    def __post_init__(self) -> None:
        """Reject a blank actor identity."""
        if not self.actor_id.strip():
            msg = "access request actor_id is required"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """Typed, non-leaking authorization result."""

    allowed: bool
    reason: str
    matched_grant_ids: tuple[str, ...]


_ROLE_PERMISSIONS: Final = {
    Role.VIEWER: frozenset(
        {
            Permission.PROGRAM_READ,
            Permission.WORK_ITEM_READ,
            Permission.DECISION_VIEW_HISTORY,
            Permission.POLICY_READ,
            Permission.EVIDENCE_VERIFY,
            Permission.EVIDENCE_VIEW,
            Permission.PROPOSED_CHANGE_VIEW,
        }
    ),
    Role.BUILDER: frozenset(
        {
            Permission.PROGRAM_CREATE,
            Permission.PROGRAM_READ,
            Permission.WORK_ITEM_CREATE,
            Permission.WORK_ITEM_READ,
            Permission.WORK_ITEM_UPDATE_OWN,
            Permission.WORK_ITEM_CLAIM,
            Permission.WORK_ITEM_SUBMIT,
            Permission.DECISION_CREATE,
            Permission.DECISION_OVERRIDE,
            Permission.DECISION_VIEW_HISTORY,
            Permission.POLICY_READ,
            Permission.EVIDENCE_COLLECT,
            Permission.EVIDENCE_VERIFY,
            Permission.EVIDENCE_VIEW,
            Permission.PROPOSED_CHANGE_DECIDE,
            Permission.PROPOSED_CHANGE_VIEW,
        }
    ),
    Role.COORDINATOR: frozenset(
        {
            Permission.PROGRAM_CREATE,
            Permission.PROGRAM_READ,
            Permission.PROGRAM_READ_ALL,
            Permission.PROGRAM_UPDATE,
            Permission.WORK_ITEM_CREATE,
            Permission.WORK_ITEM_READ,
            Permission.WORK_ITEM_UPDATE_OWN,
            Permission.WORK_ITEM_UPDATE_ALL,
            Permission.WORK_ITEM_CLAIM,
            Permission.DECISION_VIEW_HISTORY,
            Permission.POLICY_READ,
            Permission.EVIDENCE_VERIFY,
            Permission.EVIDENCE_VIEW,
            Permission.PROPOSED_CHANGE_VIEW,
        }
    ),
    Role.OPERATOR: frozenset(
        {
            Permission.PROGRAM_READ,
            Permission.PROGRAM_READ_ALL,
            Permission.WORK_ITEM_READ,
            Permission.DECISION_VIEW_HISTORY,
            Permission.POLICY_READ,
            Permission.EVIDENCE_VIEW,
            Permission.PROPOSED_CHANGE_VIEW,
            Permission.CONNECTION_VIEW,
            Permission.CONNECTION_RECONNECT,
            Permission.AUDIT_VIEW,
        }
    ),
    Role.POLICY_ADMINISTRATOR: frozenset(
        {
            Permission.PROGRAM_READ,
            Permission.PROGRAM_READ_ALL,
            Permission.WORK_ITEM_READ,
            Permission.DECISION_VIEW_HISTORY,
            Permission.POLICY_READ,
            Permission.POLICY_MANAGE,
            Permission.EVIDENCE_VERIFY,
            Permission.EVIDENCE_VIEW,
            Permission.PROPOSED_CHANGE_VIEW,
        }
    ),
    Role.TENANT_ADMINISTRATOR: frozenset(Permission),
}


_MIN_BREAK_GLASS_REASON_LENGTH: Final = 20


_FOUR_EYES: Final = frozenset(
    {
        Permission.PROGRAM_DELETE,
        Permission.CONNECTION_CONFIGURE,
        Permission.USER_ASSIGN_ROLE,
    }
)


@dataclass(frozen=True, slots=True)
class ApprovalContext:
    """Actors involved in the action and its approvals."""

    performer_id: str
    approver_ids: tuple[str, ...]
    claimant_id: str | None = None
    connection_configurer_id: str | None = None

    def __post_init__(self) -> None:
        """Canonicalize approvers and reject blank performer identity."""
        if not self.performer_id.strip():
            msg = "approval performer_id is required"
            raise ValueError(msg)
        object.__setattr__(self, "approver_ids", tuple(sorted(set(self.approver_ids))))


@dataclass(frozen=True, slots=True)
class SeparationDecision:
    """Result of one separation-of-duties evaluation."""

    allowed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class BreakGlassGrant:
    """Narrow emergency permission with strong-auth and review metadata."""

    actor_id: str
    permission: Permission
    scope: ResourceScope
    reason: str
    strong_reauthenticated: bool
    second_factor_verified: bool
    duration: timedelta

    def __post_init__(self) -> None:
        """Enforce maximum duration, strong auth, and prohibited actions."""
        if len(self.reason.strip()) < _MIN_BREAK_GLASS_REASON_LENGTH:
            msg = "break-glass reason must contain at least twenty characters"
            raise ValueError(msg)
        if not self.strong_reauthenticated or not self.second_factor_verified:
            msg = "break-glass requires strong reauthentication and a second factor"
            raise ValueError(msg)
        if self.duration <= timedelta(0) or self.duration > timedelta(hours=2):
            msg = "break-glass duration must be positive and no longer than two hours"
            raise ValueError(msg)
        prohibited = {
            Permission.USER_ASSIGN_ROLE,
            Permission.POLICY_MANAGE,
            Permission.CONNECTION_CONFIGURE,
        }
        if self.permission in prohibited:
            msg = "break-glass cannot grant role, policy, or connection configuration"
            raise ValueError(msg)


def authorize(
    request: AccessRequest,
    grants: tuple[RoleGrant, ...],
    denies: tuple[DenyRule, ...] = (),
) -> AuthorizationDecision:
    """Evaluate current role grants with explicit deny and deny-by-default."""
    matching_denies = tuple(
        deny
        for deny in denies
        if deny.actor_id == request.actor_id
        and deny.permission is request.permission
        and deny.scope.contains(request.scope)
    )
    if matching_denies:
        return AuthorizationDecision(
            allowed=False, reason="explicit_deny", matched_grant_ids=()
        )
    matching = tuple(
        grant
        for grant in grants
        if grant.actor_id == request.actor_id
        and grant.scope.contains(request.scope)
        and request.permission in _ROLE_PERMISSIONS[grant.role]
    )
    if not matching:
        return AuthorizationDecision(
            allowed=False, reason="deny_by_default", matched_grant_ids=()
        )
    return AuthorizationDecision(
        allowed=True,
        reason="explicit_role_grant",
        matched_grant_ids=tuple(sorted(grant.grant_id for grant in matching)),
    )


def evaluate_separation_of_duties(
    permission: Permission,
    context: ApprovalContext,
) -> SeparationDecision:
    """Enforce claimant/configurer separation and four-eyes operations."""
    approvers = set(context.approver_ids)
    if (
        permission is Permission.DECISION_CREATE
        and context.claimant_id is not None
        and approvers <= {context.claimant_id}
    ):
        return SeparationDecision(
            allowed=False,
            reason="claimant_cannot_be_sole_approver",
        )
    if (
        permission is Permission.CONNECTION_RECONNECT
        and context.connection_configurer_id is not None
        and approvers <= {context.connection_configurer_id}
    ):
        return SeparationDecision(
            allowed=False,
            reason="configurer_cannot_be_sole_operator",
        )
    if permission in _FOUR_EYES and len(approvers - {context.performer_id}) < 1:
        return SeparationDecision(allowed=False, reason="four_eyes_required")
    return SeparationDecision(allowed=True, reason="separation_satisfied")


def permissions_for_role(role: Role) -> frozenset[Permission]:
    """Return immutable permissions for generated matrix tests."""
    return _ROLE_PERMISSIONS[role]

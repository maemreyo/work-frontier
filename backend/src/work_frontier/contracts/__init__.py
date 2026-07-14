"""Canonical transport contracts generated from Pydantic models."""

from .decision_record import DecisionRecordContract
from .setup import (
    ActionResult,
    ActionState,
    CapabilityName,
    CapabilityReport,
    CheckState,
    DetectionCheck,
    DetectionSnapshot,
    SecretReference,
    SetupAction,
    SetupEnvelope,
    SetupPlan,
    SetupProfile,
)

__all__ = [
    "ActionResult",
    "ActionState",
    "CapabilityName",
    "CapabilityReport",
    "CheckState",
    "DecisionRecordContract",
    "DetectionCheck",
    "DetectionSnapshot",
    "SecretReference",
    "SetupAction",
    "SetupEnvelope",
    "SetupPlan",
    "SetupProfile",
]

"""Typed API errors mapped to non-leaking HTTP responses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ControlPlaneError(Exception):
    """Application-facing error with stable code and HTTP status."""

    code: str
    message: str
    status_code: int

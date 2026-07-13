"""Fail-closed inputs for exact final certification."""

from __future__ import annotations

import base64
import binascii
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

_REQUIRED_ENV = (
    "WF_GITHUB_SANDBOX_REPOSITORY",
    "WF_GITHUB_SANDBOX_TOKEN",
    "WF_RELEASE_SIGNING_KEY_B64",
    "WF_RELEASE_KEY_ID",
    "WF_CUTOVER_CONFIRM",
    "WF_CUTOVER_APPROVAL_ID",
    "WF_CUTOVER_SOURCE_REVISION",
    "WF_CUTOVER_REPOSITORY",
)
_ED25519_PRIVATE_KEY_BYTES = 32
_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_PLACEHOLDER_MARKERS = (
    "<",
    ">",
    "replace-with",
    "short-lived-token",
    "exact-github-source-revision",
    "approved-cutover-id",
    "owner/isolated-sandbox",
    "owner/reference-repository",
)


class FinalCertificationInputError(ValueError):
    """Signal invalid release/cutover inputs before expensive harnesses run."""


def validate_exact_certification_environment(env: Mapping[str, str]) -> None:
    """Reject missing, placeholder, malformed, or weak exact-certification inputs."""
    missing = [name for name in _REQUIRED_ENV if not env.get(name, "").strip()]
    if missing:
        msg = "missing exact-certification environment: " + ", ".join(missing)
        raise FinalCertificationInputError(msg)

    for name in _REQUIRED_ENV:
        value = env[name].strip()
        if any(marker in value.casefold() for marker in _PLACEHOLDER_MARKERS):
            msg = f"{name} still contains a documented placeholder"
            raise FinalCertificationInputError(msg)

    if env["WF_CUTOVER_CONFIRM"] != "ACTIVATE_539":
        msg = "WF_CUTOVER_CONFIRM must equal ACTIVATE_539"
        raise FinalCertificationInputError(msg)

    for name in ("WF_GITHUB_SANDBOX_REPOSITORY", "WF_CUTOVER_REPOSITORY"):
        if _REPOSITORY_PATTERN.fullmatch(env[name].strip()) is None:
            msg = f"{name} must use owner/repository form"
            raise FinalCertificationInputError(msg)

    try:
        raw_key = base64.b64decode(
            env["WF_RELEASE_SIGNING_KEY_B64"],
            validate=True,
        )
    except (binascii.Error, ValueError) as exc:
        msg = "WF_RELEASE_SIGNING_KEY_B64 must be valid base64"
        raise FinalCertificationInputError(msg) from exc
    if len(raw_key) != _ED25519_PRIVATE_KEY_BYTES:
        msg = "WF_RELEASE_SIGNING_KEY_B64 must encode a raw 32-byte Ed25519 key"
        raise FinalCertificationInputError(msg)


def validate_plan_ready_for_final_certification(content: str) -> None:
    """Require completed predecessors and open final implementation items."""
    missing_done = [item for item in range(1, 28) if f"- [x] {item}." not in content]
    not_open = [item for item in range(28, 36) if f"- [ ] {item}." not in content]
    if missing_done or not_open:
        msg = f"unexpected plan state: missing_done={missing_done}, not_open={not_open}"
        raise FinalCertificationInputError(msg)

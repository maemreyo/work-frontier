from __future__ import annotations

import base64

import pytest

from work_frontier.contracts.final_certification import (
    FinalCertificationInputError,
    validate_exact_certification_environment,
    validate_plan_ready_for_final_certification,
)


def _valid_environment() -> dict[str, str]:
    return {
        "WF_GITHUB_SANDBOX_REPOSITORY": "acme/work-frontier-sandbox",
        "WF_GITHUB_SANDBOX_TOKEN": "github_pat_realistic_test_value",
        "WF_RELEASE_SIGNING_KEY_B64": base64.b64encode(bytes(range(32))).decode(),
        "WF_RELEASE_KEY_ID": "work-frontier-standard-2026-01",
        "WF_CUTOVER_CONFIRM": "ACTIVATE_539",
        "WF_CUTOVER_APPROVAL_ID": "approval-2026-07-13-001",
        "WF_CUTOVER_SOURCE_REVISION": "sha256:0123456789abcdef",
        "WF_CUTOVER_REPOSITORY": "acme/reference-repository",
    }


def test_documented_placeholders_are_rejected_before_certification() -> None:
    env = _valid_environment()
    env["WF_GITHUB_SANDBOX_TOKEN"] = "short-lived-" + "token"

    with pytest.raises(FinalCertificationInputError, match="placeholder"):
        validate_exact_certification_environment(env)


def test_raw_ed25519_key_must_be_exactly_32_bytes() -> None:
    env = _valid_environment()
    env["WF_RELEASE_SIGNING_KEY_B64"] = base64.b64encode(b"too-short").decode()

    with pytest.raises(FinalCertificationInputError, match="32-byte"):
        validate_exact_certification_environment(env)


def test_real_shaped_environment_is_accepted() -> None:
    validate_exact_certification_environment(_valid_environment())


def test_final_certification_requires_items_28_through_35_open() -> None:
    plan = "\n".join(
        [
            *(f"- [x] {item}. done" for item in range(1, 28)),
            *(f"- [ ] {item}. open" for item in range(28, 36)),
        ]
    )
    validate_plan_ready_for_final_certification(plan)

    with pytest.raises(FinalCertificationInputError, match=r"not_open=\[28\]"):
        validate_plan_ready_for_final_certification(
            plan.replace("- [ ] 28.", "- [x] 28.")
        )

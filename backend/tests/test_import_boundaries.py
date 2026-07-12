from pathlib import Path

import pytest
from scripts.check_import_boundaries import validate

FIXTURES = Path(__file__).parent / "fixtures" / "boundaries"


def test_validate_when_only_public_ports_are_imported() -> None:
    # Given Platform and Adapter modules importing only public Application ports
    # When the boundary checker validates their source root
    violations = validate(FIXTURES / "valid")

    # Then the documented implementation exception is accepted
    assert violations == ()


@pytest.mark.parametrize(
    ("fixture_name", "expected_rule"),
    [
        ("domain-to-platform", "domain-cannot-import-non-domain"),
        ("platform-to-application", "platform-may-import-only-application-ports"),
        ("application-to-adapter", "application-cannot-import-implementation"),
        ("adapters-to-domain", "adapters-cannot-import-domain"),
        (
            "adapters-to-internal-application",
            "adapters-may-import-only-application-ports",
        ),
        ("interfaces-to-platform", "interfaces-must-call-application"),
    ],
)
def test_validate_when_forbidden_import_is_injected(
    fixture_name: str, expected_rule: str
) -> None:
    # Given a fixture that injects one ADR-006 forbidden import edge
    # When the boundary checker validates its source root
    violations = validate(FIXTURES / fixture_name)

    # Then it reports the exact architecture rule
    assert tuple(violation.rule for violation in violations) == (expected_rule,)

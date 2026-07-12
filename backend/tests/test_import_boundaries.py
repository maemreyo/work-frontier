from __future__ import annotations

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


class TestImportBoundaryFixes:
    """Tests validating that bypass vulnerabilities are fixed."""

    def test_aliased_import_is_caught(self, tmp_path: Path) -> None:
        """Aliased imports like 'from work_frontier import platform' are now caught."""
        src = tmp_path / "work_frontier" / "domain"
        src.mkdir(parents=True)
        module = src / "entity.py"
        _ = module.write_text("from work_frontier import platform\n", encoding="utf-8")

        violations = validate(tmp_path)

        domain_to_platform = [
            v for v in violations if "domain-cannot-import-non-domain" in v.rule
        ]
        assert len(domain_to_platform) > 0

    def test_relative_import_in_init_is_checked(self, tmp_path: Path) -> None:
        """Relative imports in __init__.py are correctly resolved and checked."""
        src = tmp_path / "work_frontier" / "domain"
        src.mkdir(parents=True)
        init = src / "__init__.py"
        _ = init.write_text("from ..platform import storage\n", encoding="utf-8")

        violations = validate(tmp_path)

        domain_to_platform = [
            v for v in violations if "domain-cannot-import-non-domain" in v.rule
        ]
        assert len(domain_to_platform) > 0

    def test_composition_root_can_import_everything(self, tmp_path: Path) -> None:
        """Composition root files (__main__.py, composition.py) are exempt."""
        src = tmp_path / "work_frontier"
        src.mkdir(parents=True)
        main = src / "__main__.py"
        _ = main.write_text(
            (
                "from work_frontier.domain import entity\n"
                "from work_frontier.platform import storage\n"
                "from work_frontier.adapters import github\n"
                "from work_frontier.interfaces import api\n"
            ),
            encoding="utf-8",
        )

        violations = validate(tmp_path)

        assert violations == ()

    def test_domain_cannot_import_contracts(self, tmp_path: Path) -> None:
        """Domain layer cannot import contracts (transport DTOs)."""
        src = tmp_path / "work_frontier" / "domain"
        src.mkdir(parents=True)
        module = src / "entity.py"
        _ = module.write_text(
            "from work_frontier.contracts import decision_record\n", encoding="utf-8"
        )

        violations = validate(tmp_path)

        domain_to_contracts = [
            v for v in violations if "domain-cannot-import-contracts" in v.rule
        ]
        assert len(domain_to_contracts) > 0

    def test_platform_can_import_contracts(self, tmp_path: Path) -> None:
        """Platform layer can import contracts."""
        src = tmp_path / "work_frontier" / "platform"
        src.mkdir(parents=True)
        module = src / "storage.py"
        _ = module.write_text(
            "from work_frontier.contracts import evidence_record\n", encoding="utf-8"
        )

        violations = validate(tmp_path)

        assert violations == ()

    def test_application_can_import_domain(self, tmp_path: Path) -> None:
        """Application layer can orchestrate domain (corrected matrix)."""
        src = tmp_path / "work_frontier" / "application"
        src.mkdir(parents=True)
        module = src / "service.py"
        _ = module.write_text(
            "from work_frontier.domain import entity\n", encoding="utf-8"
        )

        violations = validate(tmp_path)

        assert violations == ()

    def test_platform_can_import_domain(self, tmp_path: Path) -> None:
        """Platform layer can reference domain types (corrected matrix)."""
        src = tmp_path / "work_frontier" / "platform"
        src.mkdir(parents=True)
        module = src / "audit.py"
        _ = module.write_text(
            "from work_frontier.domain import decision\n", encoding="utf-8"
        )

        violations = validate(tmp_path)

        assert violations == ()

    def test_relative_import_in_regular_module_is_checked(self, tmp_path: Path) -> None:
        src = tmp_path / "work_frontier" / "domain"
        src.mkdir(parents=True)
        module = src / "entity.py"
        _ = module.write_text("from .. import platform\n", encoding="utf-8")

        violations = validate(tmp_path)

        assert any("domain-cannot-import-non-domain" in v.rule for v in violations)

    def test_unknown_source_layer_fails_closed(self, tmp_path: Path) -> None:
        src = tmp_path / "work_frontier" / "services"
        src.mkdir(parents=True)
        module = src / "foo.py"
        _ = module.write_text("x = 1\n", encoding="utf-8")

        violations = validate(tmp_path)

        assert any(v.rule == "unknown-source-layer" for v in violations)

    def test_unknown_target_layer_fails_closed(self, tmp_path: Path) -> None:
        src = tmp_path / "work_frontier" / "domain"
        src.mkdir(parents=True)
        module = src / "entity.py"
        _ = module.write_text(
            "from work_frontier.infrastructure import db\n", encoding="utf-8"
        )

        violations = validate(tmp_path)

        assert any(v.rule == "unknown-target-layer" for v in violations)

    def test_nested_composition_py_is_not_exempt(self, tmp_path: Path) -> None:
        src = tmp_path / "work_frontier" / "domain"
        src.mkdir(parents=True)
        module = src / "composition.py"
        _ = module.write_text(
            "from work_frontier.adapters import github\n", encoding="utf-8"
        )

        violations = validate(tmp_path)

        assert any("domain-cannot-import-non-domain" in v.rule for v in violations)

    def test_package_root_composition_py_is_exempt(self, tmp_path: Path) -> None:
        pkg = tmp_path / "work_frontier"
        pkg.mkdir(parents=True)
        module = pkg / "composition.py"
        _ = module.write_text(
            "from work_frontier.adapters import github\n", encoding="utf-8"
        )

        violations = validate(tmp_path)

        assert violations == ()

    def test_from_application_import_ports_is_allowed_for_platform(
        self, tmp_path: Path
    ) -> None:
        src = tmp_path / "work_frontier" / "platform"
        src.mkdir(parents=True)
        module = src / "connector.py"
        _ = module.write_text(
            "from work_frontier.application import ports\n", encoding="utf-8"
        )

        violations = validate(tmp_path)

        assert violations == ()

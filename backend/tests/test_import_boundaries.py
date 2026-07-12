from __future__ import annotations

import inspect
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


class TestImportBoundaryBypasses:
    """RED tests proving bypass vulnerabilities in check_import_boundaries.py.
    
    These tests MUST FAIL with the current implementation.
    They prove that forbidden imports can bypass the checker.
    """

    def test_relative_import_not_checked(self, tmp_path: Path) -> None:
        """BYPASS: Relative imports (from ..X import Y) are silently skipped.
        
        Current: check_import_boundaries.py line 82 skips when node.level > 0
        Required: Relative imports must be normalized to absolute and checked
        """
        # Given: application layer module using relative import to domain
        src = tmp_path / "work_frontier" / "application"
        src.mkdir(parents=True)
        module = src / "service.py"
        # This is a forbidden application→domain edge via relative import
        _ = module.write_text("from ...work_frontier.domain import entity\n", encoding="utf-8")
        
        # When: the boundary checker validates this source root
        violations = validate(tmp_path)
        
        # Then: it SHOULD report application-cannot-import-implementation
        # But currently FAILS because relative imports are skipped
        application_to_domain = [
            v for v in violations 
            if "application-cannot-import-implementation" in v.rule
        ]
        assert len(application_to_domain) > 0, (
            "Relative import from application→domain should be a violation, "
            "but check_import_boundaries.py line 82 skips node.level > 0"
        )

    def test_undeclared_edge_passes_silently(self, tmp_path: Path) -> None:
        """BYPASS: Edges not in deny-list pass through case _ wildcard.
        
        Current: check_import_boundaries.py line 64 has 'case _: pass'
        Required: All 25 layer pairs must have explicit allow/deny verdict
        
        Example: platform→domain is forbidden but not in current deny-list.
        """
        # Given: platform layer importing domain (forbidden but undeclared)
        platform_src = tmp_path / "work_frontier" / "platform"
        platform_src.mkdir(parents=True)
        module = platform_src / "storage.py"
        # platform→domain is architecturally forbidden but not in deny-list
        _ = module.write_text("from work_frontier.domain import entity\n", encoding="utf-8")
        
        # When: the boundary checker validates this source root
        violations = validate(tmp_path)
        
        # Then: it SHOULD report a violation for platform→domain
        # But currently FAILS because this edge hits 'case _: pass'
        platform_to_domain = [
            v for v in violations
            if v.path == module
        ]
        assert len(platform_to_domain) > 0, (
            "platform→domain is architecturally forbidden but passes silently "
            "through 'case _: pass' at check_import_boundaries.py line 64"
        )

    def test_case_wildcard_exists_in_checker_source(self) -> None:
        """BYPASS: case _ wildcard allows arbitrary undeclared edges.
        
        Current: check_import_boundaries.py line 64 has 'case _: pass'
        Required: Exhaustive match with no wildcard fallthrough
        
        This test verifies the root cause exists in source code.
        """
        # Given: the check_import_boundaries module source
        import scripts.check_import_boundaries as checker_module
        source = inspect.getsource(checker_module)
        
        # Then: it SHOULD NOT have a wildcard case statement
        # But currently FAILS because 'case _:' exists at line 64
        assert "case _:" not in source, (
            "check_import_boundaries.py contains 'case _:' wildcard at line 64. "
            "This allows undeclared layer edges to pass silently. "
            "All 25 layer pairs must have explicit allow/deny rules."
        )

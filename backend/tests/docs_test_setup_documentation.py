from pathlib import Path


def test_quick_start_uses_interactive_setup_without_shell_exports() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "uv run work-frontier setup" in readme
    assert "export WF_RELEASE_SIGNING_KEY_B64" not in readme


def test_setup_operations_doc_explains_independent_readiness() -> None:
    content = Path("docs/operations/setup-center.md").read_text(encoding="utf-8")
    for capability in (
        "Local Runtime Ready",
        "GitHub Integration Ready",
        "Release Certification Ready",
        "Production Cutover Ready",
    ):
        assert capability in content


def test_development_guide_uses_setup_center_as_first_run() -> None:
    content = Path("docs/development.md").read_text(encoding="utf-8")
    assert "uv run work-frontier setup" in content
    assert "manual_recovery_required" in content
    assert "export WF_RELEASE_SIGNING_KEY_B64" not in content

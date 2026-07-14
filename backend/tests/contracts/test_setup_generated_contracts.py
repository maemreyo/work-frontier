from pathlib import Path

from scripts.generate_contracts import setup_artifacts


def test_setup_contract_is_part_of_generated_artifacts() -> None:
    artifacts = setup_artifacts()
    paths = {path for path, _content in artifacts}
    assert paths == {
        Path("contracts/generated/setup.schema.json"),
        Path("frontend/src/contracts/setup.generated.ts"),
    }
    assert all(
        content.startswith(("{", "// Generated")) for _path, content in artifacts
    )

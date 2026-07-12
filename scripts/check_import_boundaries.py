"""Enforce ADR-006 Python layer import boundaries."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, override

PACKAGE: Final = "work_frontier"
MIN_PACKAGE_PARTS: Final = 2
LAYERS: Final = frozenset(
    {"domain", "platform", "application", "adapters", "interfaces"}
)
ALLOW_MATRIX: Final = {
    "domain": {
        "domain": True,
        "platform": False,
        "application": False,
        "adapters": False,
        "interfaces": False,
    },
    "platform": {
        "domain": False,
        "platform": True,
        "application": False,
        "adapters": False,
        "interfaces": False,
    },
    "application": {
        "domain": False,
        "platform": False,
        "application": True,
        "adapters": False,
        "interfaces": False,
    },
    "adapters": {
        "domain": False,
        "platform": True,
        "application": False,
        "adapters": True,
        "interfaces": False,
    },
    "interfaces": {
        "domain": False,
        "platform": False,
        "application": True,
        "adapters": False,
        "interfaces": True,
    },
}


@dataclass(frozen=True, slots=True)
class BoundaryViolation:
    """A forbidden package-layer import."""

    path: Path
    line: int
    rule: str


def layer_for_path(path: Path, source_root: Path) -> str | None:
    """Return the ADR-006 layer owning a Python source path."""
    relative_parts = path.relative_to(source_root).parts
    if len(relative_parts) < MIN_PACKAGE_PARTS or relative_parts[0] != PACKAGE:
        return None
    candidate = relative_parts[1]
    return candidate if candidate in LAYERS else None


def resolve_relative_import(
    file_path: Path, source_root: Path, module: str | None, level: int
) -> str | None:
    """Resolve a relative import to an absolute module path."""
    if level == 0:
        return module

    relative_path = file_path.relative_to(source_root)
    module_parts = list(relative_path.with_suffix("").parts)

    if module_parts and module_parts[-1] == "__init__":
        _ = module_parts.pop()

    if len(module_parts) < level:
        return None
    base_parts = module_parts[:-level] if level > 0 else module_parts

    if module:
        base_parts.extend(module.split("."))

    return ".".join(base_parts) if base_parts else None


def target_for_module(module: str) -> tuple[str, bool] | None:
    """Return the target layer and whether it is the public ports package."""
    parts = module.split(".")
    if len(parts) < MIN_PACKAGE_PARTS or parts[0] != PACKAGE or parts[1] not in LAYERS:
        return None
    return (parts[1], parts[:3] == [PACKAGE, "application", "ports"])


def violation_rule(
    source_layer: str, target_layer: str, target_is_ports: bool
) -> str | None:
    """Return the ADR-006 rule violated by a layer-to-layer import."""
    if (
        source_layer not in ALLOW_MATRIX
        or target_layer not in ALLOW_MATRIX[source_layer]
    ):
        return "unknown-layer-pair"

    allowed = ALLOW_MATRIX[source_layer][target_layer]

    if target_layer == "application" and target_is_ports:
        if source_layer in {"platform", "adapters"}:
            allowed = True

    if allowed:
        return None

    if source_layer == "domain":
        return "domain-cannot-import-non-domain"
    if source_layer == "platform" and target_layer == "application":
        return "platform-may-import-only-application-ports"
    if source_layer == "application":
        return "application-cannot-import-implementation"
    if source_layer == "adapters" and target_layer == "domain":
        return "adapters-cannot-import-domain"
    if source_layer == "adapters" and target_layer == "application":
        return "adapters-may-import-only-application-ports"
    if source_layer == "adapters" and target_layer == "interfaces":
        return "adapters-cannot-import-interfaces"
    if source_layer == "interfaces":
        return "interfaces-must-call-application"

    return "unknown-violation"


class ImportCollector(ast.NodeVisitor):
    """Collect absolute Work Frontier imports from an AST."""

    def __init__(self, file_path: Path, source_root: Path) -> None:
        """Initialize the mutable AST import accumulator."""
        self.file_path: Path = file_path
        self.source_root: Path = source_root
        self.modules: list[tuple[str, int]] = []

    @override
    def visit_Import(self, node: ast.Import) -> None:
        self.modules.extend((alias.name, node.lineno) for alias in node.names)

    @override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        resolved = resolve_relative_import(
            self.file_path, self.source_root, node.module, node.level
        )
        if resolved is not None:
            self.modules.append((resolved, node.lineno))


def imported_modules(
    tree: ast.Module, file_path: Path, source_root: Path
) -> tuple[tuple[str, int], ...]:
    """Extract absolute Work Frontier imports and their source lines."""
    collector = ImportCollector(file_path, source_root)
    collector.visit(tree)
    return tuple(collector.modules)


def validate(source_root: Path) -> tuple[BoundaryViolation, ...]:
    """Return every forbidden import below a Work Frontier source root."""
    violations: list[BoundaryViolation] = []
    for path in sorted(source_root.rglob("*.py")):
        source_layer = layer_for_path(path, source_root)
        if source_layer is None:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path)
        for module, line in imported_modules(tree, path, source_root):
            target = target_for_module(module)
            if target is None:
                continue
            target_layer, target_is_ports = target
            rule = violation_rule(source_layer, target_layer, target_is_ports)
            if rule is not None:
                violations.append(BoundaryViolation(path=path, line=line, rule=rule))
    return tuple(violations)


def parse_source_root(arguments: list[str]) -> Path | None:
    """Parse the source root supplied to the standalone checker."""
    if len(arguments) == 0:
        return Path("backend/src").resolve()
    if len(arguments) == 2 and arguments[0] == "--root":
        return Path(arguments[1]).resolve()
    return None


def main() -> int:
    """Print violations and return a nonzero status when an import boundary fails."""
    from work_frontier.contracts.evidence_record import Artifact, Result
    from work_frontier.contracts.evidence_writer import write_evidence

    start_time = datetime.now(UTC)
    repo_root = Path(__file__).parent.parent

    source_root = parse_source_root(sys.argv[1:])
    if source_root is None:
        print("usage: check_import_boundaries.py [--root PATH]", file=sys.stderr)
        return 2

    violations = validate(source_root)
    for violation in violations:
        print(f"{violation.path}:{violation.line}: {violation.rule}")

    exit_code = 1 if violations else 0
    end_time = datetime.now(UTC)

    artifacts = [
        Artifact(path=str(path.relative_to(repo_root)))
        for path in sorted(source_root.rglob("*.py"))
        if layer_for_path(path, source_root) is not None
    ]

    results = [
        Result(
            kind=violation.rule,
            passed=False,
            detail=f"{violation.path.relative_to(repo_root)}:{violation.line}",
        )
        for violation in violations
    ]

    _ = write_evidence(
        harness_id="WF-HAR-STATIC-01",
        status="fail" if violations else "pass",
        command=f"python {' '.join(sys.argv)}",
        exit_code=exit_code,
        working_directory=str(repo_root),
        start_time=start_time,
        end_time=end_time,
        tool_name="check_import_boundaries",
        artifacts=artifacts,
        results=results,
        property_bag={
            "check_import_boundaries": {
                "source_root": str(source_root.relative_to(repo_root)),
                "violation_count": len(violations),
            }
        },
        output_filename="import-boundaries.json",
        repo_root=repo_root,
    )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

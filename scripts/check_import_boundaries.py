"""Enforce ADR-006 Python layer import boundaries."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, override

PACKAGE: Final = "work_frontier"
MIN_PACKAGE_PARTS: Final = 2
LAYERS: Final = frozenset(
    {"domain", "platform", "application", "adapters", "interfaces"}
)


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
    rule: str | None = None
    match source_layer:
        case "domain" if target_layer != "domain":
            rule = "domain-cannot-import-non-domain"
        case "platform" if target_layer == "application" and not target_is_ports:
            rule = "platform-may-import-only-application-ports"
        case "application" if target_layer in {"platform", "adapters", "interfaces"}:
            rule = "application-cannot-import-implementation"
        case "adapters" if target_layer == "domain":
            rule = "adapters-cannot-import-domain"
        case "adapters" if target_layer == "application" and not target_is_ports:
            rule = "adapters-may-import-only-application-ports"
        case "adapters" if target_layer == "interfaces":
            rule = "adapters-cannot-import-interfaces"
        case "interfaces" if target_layer in {"domain", "platform", "adapters"}:
            rule = "interfaces-must-call-application"
        case _:
            pass
    return rule


class ImportCollector(ast.NodeVisitor):
    """Collect absolute Work Frontier imports from an AST."""

    def __init__(self) -> None:
        """Initialize the mutable AST import accumulator."""
        self.modules: list[tuple[str, int]] = []

    @override
    def visit_Import(self, node: ast.Import) -> None:
        self.modules.extend((alias.name, node.lineno) for alias in node.names)

    @override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level == 0 and node.module is not None:
            self.modules.append((node.module, node.lineno))


def imported_modules(tree: ast.Module) -> tuple[tuple[str, int], ...]:
    """Extract absolute Work Frontier imports and their source lines."""
    collector = ImportCollector()
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
        for module, line in imported_modules(tree):
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
    match arguments:
        case []:
            return Path("backend/src").resolve()
        case ["--root", root]:
            return Path(root).resolve()
        case _:
            return None


def main() -> int:
    """Print violations and return a nonzero status when an import boundary fails."""
    source_root = parse_source_root(sys.argv[1:])
    if source_root is None:
        print("usage: check_import_boundaries.py [--root PATH]", file=sys.stderr)
        return 2
    violations = validate(source_root)
    for violation in violations:
        print(f"{violation.path}:{violation.line}: {violation.rule}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())

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
    {"domain", "platform", "application", "adapters", "interfaces", "contracts"}
)
COMPOSITION_ROOT_FILES: Final = frozenset({"__main__.py", "composition.py"})

# Canonical import matrix from ARCHITECTURE.md section 3.3
# Application orchestrates Domain; Platform (audit) references Domain types
# Contracts is a shared transport/DTO layer importable by all except Domain
ALLOW_MATRIX: Final = {
    "domain": {
        "domain": True,
        "platform": False,
        "application": False,
        "adapters": False,
        "interfaces": False,
        "contracts": False,  # Domain stays pure, no transport DTOs
    },
    "platform": {
        "domain": True,  # audit references domain types (AUD → DEC)
        "platform": True,
        "application": False,  # except application.ports
        "adapters": False,
        "interfaces": False,
        "contracts": True,
    },
    "application": {
        "domain": True,  # application orchestrates domain
        "platform": False,
        "application": True,
        "adapters": False,
        "interfaces": False,
        "contracts": True,
    },
    "adapters": {
        "domain": False,
        "platform": True,
        "application": False,  # except application.ports
        "adapters": True,
        "interfaces": False,
        "contracts": True,
    },
    "interfaces": {
        "domain": False,
        "platform": False,
        "application": True,
        "adapters": False,
        "interfaces": True,
        "contracts": True,
    },
    "contracts": {
        "domain": False,
        "platform": False,
        "application": False,
        "adapters": False,
        "interfaces": False,
        "contracts": True,
    },
}


@dataclass(frozen=True, slots=True)
class BoundaryViolation:
    """A forbidden package-layer import."""

    path: Path
    line: int
    rule: str


def is_composition_root(path: Path, source_root: Path) -> bool:
    """True only for package-root composition entrypoints (not nested)."""
    relative_parts = path.relative_to(source_root).parts
    return (
        len(relative_parts) == MIN_PACKAGE_PARTS
        and relative_parts[0] == PACKAGE
        and relative_parts[1] in COMPOSITION_ROOT_FILES
    )


def layer_for_path(path: Path, source_root: Path) -> str | None:
    """Return the ADR-006 layer owning a Python source path, if known."""
    relative_parts = path.relative_to(source_root).parts
    if len(relative_parts) < MIN_PACKAGE_PARTS or relative_parts[0] != PACKAGE:
        return None
    candidate = relative_parts[1]
    return candidate if candidate in LAYERS else None


def unknown_source_layer(path: Path, source_root: Path) -> bool:
    """True when a file lives under an undeclared package sub-layer."""
    relative_parts = path.relative_to(source_root).parts
    if len(relative_parts) < MIN_PACKAGE_PARTS or relative_parts[0] != PACKAGE:
        return False
    second = relative_parts[1]
    if second.endswith(".py"):
        return False
    return second not in LAYERS


def resolve_relative_import(
    file_path: Path, source_root: Path, module: str | None, level: int
) -> str | None:
    """Resolve a relative import to an absolute module path.

    Always strips the importing file's stem so both regular modules and
    ``__init__.py`` resolve relative to their containing package.
    """
    if level == 0:
        return module

    relative_path = file_path.relative_to(source_root)
    package_parts = list(relative_path.with_suffix("").parts)
    if package_parts:
        _ = package_parts.pop()

    levels_up = level - 1
    if len(package_parts) < levels_up:
        return None

    base_parts = package_parts[:-levels_up] if levels_up > 0 else package_parts

    if module:
        base_parts.extend(module.split("."))

    return ".".join(base_parts) if base_parts else None


UNKNOWN_TARGET_LAYER: Final = "__unknown__"


def target_for_module(module: str) -> tuple[str, bool] | None:
    """Return the target layer and whether it is the public ports package.

    Unknown layers under the package root are returned as
    ``(UNKNOWN_TARGET_LAYER, False)`` so callers fail closed.
    """
    parts = module.split(".")
    if not parts or parts[0] != PACKAGE:
        return None
    if len(parts) < MIN_PACKAGE_PARTS:
        return None

    target_layer = parts[1]
    if target_layer not in LAYERS:
        return (UNKNOWN_TARGET_LAYER, False)

    is_ports = parts[:3] == [PACKAGE, "application", "ports"]
    return (target_layer, is_ports)


def violation_rule(  # noqa: PLR0912
    source_layer: str, target_layer: str, target_is_ports: bool
) -> str | None:
    """Return the ADR-006 rule violated by a layer-to-layer import."""
    if target_layer == UNKNOWN_TARGET_LAYER:
        return "unknown-target-layer"
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
        if target_layer == "contracts":
            return "domain-cannot-import-contracts"
        return "domain-cannot-import-non-domain"
    if source_layer == "platform":
        if target_layer == "application":
            return "platform-may-import-only-application-ports"
        return "platform-cannot-import-implementation"
    if source_layer == "application":
        return "application-cannot-import-implementation"
    if source_layer == "adapters":
        if target_layer == "domain":
            return "adapters-cannot-import-domain"
        if target_layer == "application":
            return "adapters-may-import-only-application-ports"
        if target_layer == "interfaces":
            return "adapters-cannot-import-interfaces"
        return "adapters-cannot-import-target"
    if source_layer == "interfaces":
        return "interfaces-must-call-application"
    if source_layer == "contracts":
        return "contracts-cannot-import-other-layers"

    return f"forbidden-import-{source_layer}-to-{target_layer}"


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
        if resolved is None:
            return

        self.modules.append((resolved, node.lineno))

        if resolved == PACKAGE or resolved.startswith(f"{PACKAGE}."):
            for alias in node.names:
                if alias.name == "*":
                    continue
                if alias.name in LAYERS:
                    self.modules.append((f"{PACKAGE}.{alias.name}", node.lineno))
                elif resolved == PACKAGE:
                    self.modules.append((f"{resolved}.{alias.name}", node.lineno))


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
        if is_composition_root(path, source_root):
            continue

        if unknown_source_layer(path, source_root):
            violations.append(
                BoundaryViolation(
                    path=path,
                    line=1,
                    rule="unknown-source-layer",
                )
            )
            continue

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
    from work_frontier.contracts.evidence_writer import hash_file, write_evidence

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
        Artifact(
            path=str(path.relative_to(repo_root)),
            hashes={"sha256": hash_file(path)},
        )
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
        harness_id="WF-HAR-STATIC-02",
        status="fail" if violations else "pass",
        command=f"uv run python {' '.join(sys.argv)}",
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

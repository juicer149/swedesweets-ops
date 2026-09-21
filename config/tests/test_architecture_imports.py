"""Guards the dependency rules documented in ARCHITECTURE.md.

Add a rule by adding an entry to FORBIDDEN_IMPORTS: the key is the package
whose (non-test, non-migration) code is scanned, the value is the set of
top-level packages it must not import.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_IMPORTS: dict[str, frozenset[str]] = {
    # reservations depends on orders, never the reverse.
    "orders": frozenset({"reservations"}),
}


def _scanned_files(package: str) -> list[Path]:
    return sorted(
        path
        for path in (ROOT / package).rglob("*.py")
        if "tests" not in path.parts and "migrations" not in path.parts
    )


def _imported_top_level_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])

    return modules


@pytest.mark.parametrize("package", sorted(FORBIDDEN_IMPORTS))
def test_package_does_not_import_forbidden_packages(package: str) -> None:
    forbidden = FORBIDDEN_IMPORTS[package]
    violations = [
        f"{path.relative_to(ROOT)} imports {sorted(found)}"
        for path in _scanned_files(package)
        if (found := _imported_top_level_modules(path) & forbidden)
    ]

    assert not violations, "\n".join(violations)

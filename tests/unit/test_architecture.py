"""Constitution III.10: app/core imports none of the infrastructure libraries."""

import ast
from pathlib import Path

BANNED = {
    "fastapi", "sqlalchemy", "sqlite3", "httpx", "fastembed",
    "rapidocr_onnxruntime", "pypdf", "pypdfium2",
}
CORE = Path(__file__).resolve().parents[2] / "app" / "core"


def imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_core_imports_no_banned_modules() -> None:
    violations = {
        str(p.relative_to(CORE)): sorted(imported_roots(p) & BANNED)
        for p in CORE.rglob("*.py")
        if imported_roots(p) & BANNED
    }
    assert violations == {}


def test_core_does_not_import_adapters_or_api() -> None:
    for p in CORE.rglob("*.py"):
        source = p.read_text()
        assert "app.adapters" not in source and "app.api" not in source, p

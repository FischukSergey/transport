import ast
from pathlib import Path

_DOMAIN = Path("src/transport/domain")
_FORBIDDEN = frozenset({"PySide6", "sqlite3", "openpyxl", "pandas"})


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_domain_does_not_import_qt_or_sqlite() -> None:
    files = list(_DOMAIN.rglob("*.py"))
    assert files
    imported = set().union(*(_imported_roots(path) for path in files))
    assert imported.isdisjoint(_FORBIDDEN)

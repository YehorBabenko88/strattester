import ast
from pathlib import Path


def test_preflight_does_not_import_connectivity_at_module_level():
    """
    Cold-start / pre-install preflight must be importable before third-party
    network dependencies such as requests have been installed.
    """
    path = Path("strattester/preflight.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))

    eager_connectivity_imports = []

    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.endswith("connectivity"):
                eager_connectivity_imports.append(node.lineno)

        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.endswith("connectivity"):
                    eager_connectivity_imports.append(node.lineno)

    assert eager_connectivity_imports == [], (
        "preflight.py imports connectivity eagerly at module level; "
        f"lines={eager_connectivity_imports}"
    )


def test_network_connectivity_import_is_inside_check_network_branch():
    path = Path("strattester/preflight.py")
    text = path.read_text(encoding="utf-8")

    assert "if check_network:" in text
    assert "from .connectivity import check_bybit,check_telegram" in text

    branch_pos = text.index("if check_network:")
    import_pos = text.index(
        "from .connectivity import check_bybit,check_telegram"
    )

    assert import_pos > branch_pos

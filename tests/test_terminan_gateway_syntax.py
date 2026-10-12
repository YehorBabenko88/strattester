import ast
from pathlib import Path


def test_gateway_has_valid_syntax_and_one_handler():
    source = (Path(__file__).resolve().parents[1] / "strattester" / "terminan_gateway.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    assert sum(isinstance(node, ast.ClassDef) and node.name == "Handler" for node in module.body) == 1
    assert sum(isinstance(node, ast.FunctionDef) and node.name == "runs" for node in module.body) == 1

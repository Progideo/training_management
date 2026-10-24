"""Retain baseline test files/methods while accepting new imported Odoo tests."""

import ast
from pathlib import Path
import re
import subprocess


def source_files(root, revision, directory):
    return subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", revision, "--", directory], cwd=root, text=True
    ).splitlines()


def methods(text):
    tree = ast.parse(text)
    return {
        (node.name, method.name)
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        for method in node.body
        if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name.startswith("test_")
    }


def validate(root, revision):
    root = Path(root)
    current = {str(file.relative_to(root)): file for file in root.glob("addons/training_management*/tests/test_*.py")}
    baseline = {
        path
        for path in source_files(root, revision, "addons")
        if re.fullmatch(r"addons/training_management[^/]*/tests/test_[^/]+\.py", path)
    }
    missing = baseline - current.keys()
    if missing:
        raise ValueError(f"Deleted baseline test files: {sorted(missing)}")
    for path, file in current.items():
        tree = ast.parse((file.parent / "__init__.py").read_text())
        imported = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None
            for alias in node.names
        }
        if file.stem not in imported:
            raise ValueError(f"Test module is not imported by Odoo: {path}")
        if path in baseline:
            original = subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=root, text=True)
            removed = methods(original) - methods(file.read_text())
            if removed:
                raise ValueError(f"Deleted baseline test methods in {path}: {sorted(removed)}")

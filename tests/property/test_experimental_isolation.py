# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import ast
from dataclasses import fields
from pathlib import Path

import mcift
from mcift.types import EvaluationResult


def test_stable_modules_do_not_import_experimental_namespace() -> None:
    package_root = Path(mcift.__file__).parent
    for path in package_root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all("experimental" not in alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert "experimental" not in (node.module or "")


def test_experimental_api_is_not_exported() -> None:
    assert "experimental" not in mcift.__all__
    assert not hasattr(mcift, "spherical")
    assert not hasattr(mcift, "threefold")


def test_no_experimental_score_can_influence_stable_evaluation_result() -> None:
    stable_fields = {field.name for field in fields(EvaluationResult)}

    assert all(
        marker not in field_name
        for field_name in stable_fields
        for marker in ("experimental", "spherical", "threefold", "hierarchy", "remediation")
    )

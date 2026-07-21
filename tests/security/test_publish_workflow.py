# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Fail-closed structural checks for the production PyPI publication workflow."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-pypi.yml"


def _job(text: str, name: str, following: str | None = None) -> str:
    end = rf"(?=^  {following}:\n)" if following else r"\Z"
    match = re.search(rf"(?ms)^  {name}:\n(.*?){end}", text)
    assert match is not None, f"missing {name!r} job"
    return match.group(1)


def test_publish_workflow_is_release_only_and_tag_restricted() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    trigger = text.split("on:\n", 1)[1].split("\npermissions:", 1)[0]
    assert trigger == "  release:\n    types: [published]\n"
    assert "workflow_dispatch" not in text
    assert "github.event.release.tag_name == 'v0.1.0a1'" in text


def test_publish_workflow_has_minimal_separated_permissions() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    build = _job(text, "build", "publish")
    publish = _job(text, "publish")

    assert "permissions:\n      contents: read" in build
    assert "needs: build" in publish
    assert "environment:\n      name: pypi" in publish
    assert "permissions:\n      id-token: write" in publish
    assert "contents: write" not in publish
    assert "actions/checkout@" not in publish


def test_publish_workflow_has_no_credentials_or_unsafe_retry() -> None:
    text = WORKFLOW.read_text(encoding="utf-8").lower()
    forbidden = (
        "workflow_dispatch",
        "skip-existing",
        "twine upload",
        "twine_password",
        "pypi_token",
        "secrets.",
        "username:",
        "password:",
    )
    assert all(item not in text for item in forbidden)
    assert "https://pypi.org/project/mcift/" in text


def test_publish_workflow_uses_reviewed_artifact_and_official_publisher() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    build = _job(text, "build", "publish")
    publish = _job(text, "publish")

    refs = re.findall(
        r"^\s*(?:-\s*)?uses:\s*([^@\s]+)@([^\s#]+)", text, flags=re.MULTILINE
    )
    assert len(refs) >= 5
    assert all(re.fullmatch(r"[0-9a-f]{40}", sha) for _, sha in refs)
    assert "actions/upload-artifact@" in build
    assert "actions/download-artifact@" in publish
    assert "python -m build" in build
    assert "python -m build" not in publish
    assert "pypa/gh-action-pypi-publish@" in publish
    assert "packages-dir: packages/" in publish


def test_other_workflows_cannot_publish() -> None:
    for name in ("ci.yml", "release-check.yml"):
        text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8").lower()
        assert "pypa/gh-action-pypi-publish" not in text
        assert "twine upload" not in text
        assert "id-token: write" not in text

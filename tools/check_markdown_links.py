# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Check that local Markdown link targets exist."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    failures: list[str] = []
    markdown = sorted(path for path in ROOT.rglob("*.md") if ".git" not in path.parts)
    for source in markdown:
        text = source.read_text(encoding="utf-8")
        for raw in LINK.findall(text):
            target = raw.strip().split(maxsplit=1)[0].strip("<>")
            if target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            relative = unquote(target.split("#", 1)[0])
            if not relative:
                continue
            resolved = (source.parent / relative).resolve()
            if not resolved.is_relative_to(ROOT) or not resolved.exists():
                failures.append(f"{source.relative_to(ROOT)} -> {target}")
    if failures:
        raise SystemExit("broken local Markdown links:\n" + "\n".join(failures))
    print(f"checked {len(markdown)} Markdown files; local links resolve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

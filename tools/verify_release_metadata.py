# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Verify the exact release distribution identities using only the standard library."""

from __future__ import annotations

import tarfile
import zipfile
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

EXPECTED = {
    "Name": "mcift",
    "Version": "0.1.0a1",
    "Requires-Python": ">=3.11",
}
EXPECTED_PROJECT_URLS = {
    "Benchmarks": "https://github.com/corpobear/MCIFT-Benchmarks",
    "Documentation": "https://github.com/corpobear/MCIFT#readme",
    "Homepage": "https://www.mcift.com",
    "Issues": "https://github.com/corpobear/MCIFT/issues",
    "Repository": "https://github.com/corpobear/MCIFT",
}


def _check_metadata(raw: bytes, artifact: Path) -> None:
    metadata = BytesParser(policy=default).parsebytes(raw)
    for field, expected in EXPECTED.items():
        actual = metadata.get(field)
        if actual != expected:
            raise SystemExit(f"{artifact.name}: {field} is {actual!r}, expected {expected!r}")
    license_value = metadata.get("License-Expression") or metadata.get("License")
    if license_value != "AGPL-3.0-only":
        raise SystemExit(
            f"{artifact.name}: licence is {license_value!r}, expected 'AGPL-3.0-only'"
        )
    project_urls = {
        label.strip(): url.strip()
        for value in metadata.get_all("Project-URL", [])
        for label, url in [value.split(",", 1)]
    }
    if project_urls != EXPECTED_PROJECT_URLS:
        raise SystemExit(
            f"{artifact.name}: project URLs are {project_urls!r}, "
            f"expected {EXPECTED_PROJECT_URLS!r}"
        )


def main() -> None:
    dist = Path("dist")
    wheels = sorted(dist.glob("mcift-0.1.0a1-*.whl"))
    sdists = sorted(dist.glob("mcift-0.1.0a1.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit(f"expected one wheel and one sdist, found {wheels!r} and {sdists!r}")

    with zipfile.ZipFile(wheels[0]) as archive:
        names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise SystemExit(f"{wheels[0].name}: expected one METADATA member")
        _check_metadata(archive.read(names[0]), wheels[0])

    with tarfile.open(sdists[0], mode="r:gz") as archive:
        members = [
            member
            for member in archive.getmembers()
            if member.isfile() and member.name.count("/") == 1 and member.name.endswith("/PKG-INFO")
        ]
        if len(members) != 1:
            raise SystemExit(f"{sdists[0].name}: expected one top-level PKG-INFO member")
        extracted = archive.extractfile(members[0])
        if extracted is None:
            raise SystemExit(f"{sdists[0].name}: could not read PKG-INFO")
        _check_metadata(extracted.read(), sdists[0])

    print("release metadata verified for mcift 0.1.0a1")


if __name__ == "__main__":
    main()

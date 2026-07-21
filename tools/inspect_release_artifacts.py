# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Fail closed when release archives contain unexpected or private material."""

from __future__ import annotations

import argparse
import hashlib
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

MAX_MEMBER_BYTES = 5 * 1024 * 1024
MAX_ARCHIVE_BYTES = 20 * 1024 * 1024
PROHIBITED_PARTS = {
    ".git",
    ".github",
    "__pycache__",
    "artifacts",
    "benchmarks",
    "data",
    "datasets",
    "experimental",
    "runs",
    "tests",
}
PROHIBITED_SUFFIXES = {
    ".7z",
    ".env",
    ".jsonl",
    ".mat",
    ".mcift",
    ".npy",
    ".npz",
    ".p12",
    ".pem",
    ".pfx",
    ".zip",
}
TEXT_PATH_PATTERN = re.compile(
    rb"(?i)(?:[A-Z]:\\Users\\[^\\\s]+\\|/(?:home|Users)/[^/\s]+/|"
    rb"(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|"
    rb"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}))"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError(f"unsafe archive member path: {name}")
    lowered = {part.lower() for part in path.parts}
    if lowered & PROHIBITED_PARTS:
        raise ValueError(f"prohibited archive member: {name}")
    if path.suffix.lower() in PROHIBITED_SUFFIXES:
        raise ValueError(f"prohibited archive member type: {name}")
    return path


def _validate_payload(name: str, payload: bytes) -> None:
    if len(payload) > MAX_MEMBER_BYTES:
        raise ValueError(f"archive member exceeds size limit: {name}")
    if b"\x00" not in payload and TEXT_PATH_PATTERN.search(payload):
        raise ValueError(f"archive member contains a local/private path or address: {name}")


def _wheel_members(path: Path) -> list[str]:
    members: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            _validate_name(info.filename)
            _validate_payload(info.filename, archive.read(info))
            members.append(info.filename)
    if not any(name == "mcift/__init__.py" for name in members):
        raise ValueError("wheel does not contain mcift/__init__.py")
    return sorted(members)


def _sdist_members(path: Path) -> list[str]:
    members: list[str] = []
    with tarfile.open(path, mode="r:gz") as archive:
        for info in archive.getmembers():
            if info.issym() or info.islnk() or info.isdev():
                raise ValueError(f"sdist contains a link or special member: {info.name}")
            if not info.isfile():
                continue
            _validate_name(info.name)
            extracted = archive.extractfile(info)
            if extracted is None:
                raise ValueError(f"could not read sdist member: {info.name}")
            _validate_payload(info.name, extracted.read())
            members.append(info.name)
    if not any(name.endswith("/src/mcift/__init__.py") for name in members):
        raise ValueError("sdist does not contain src/mcift/__init__.py")
    return sorted(members)


def inspect(dist: Path, summary: Path) -> None:
    artifacts = sorted([*dist.glob("*.whl"), *dist.glob("*.tar.gz")])
    if len(artifacts) != 2:
        raise ValueError("expected exactly one wheel and one sdist")
    lines = ["MCIFT release artifact audit", "status: passed"]
    for path in artifacts:
        if path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError(f"archive exceeds size limit: {path.name}")
        members = _wheel_members(path) if path.suffix == ".whl" else _sdist_members(path)
        lines.extend(
            [
                "",
                f"artifact: {path.name}",
                f"sha256: {_sha256(path)}",
                f"size_bytes: {path.stat().st_size}",
                f"member_count: {len(members)}",
                "members:",
                *[f"- {name}" for name in members],
            ]
        )
    summary.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--summary", type=Path, default=Path("dist/audit-summary.txt"))
    args = parser.parse_args()
    inspect(args.dist, args.summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

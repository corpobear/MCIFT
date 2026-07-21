# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import hashlib
import io
import json
import os
import struct
import zipfile
from pathlib import Path

import numpy as np
import pytest

from mcift import MCIFTMonitor, serialization
from mcift.exceptions import SerializationError


def _monitor() -> MCIFTMonitor:
    windows = np.random.default_rng(44).normal(size=(8, 16, 2))
    return MCIFTMonitor.fit(windows, sampling_rate_hz=100.0, channel_names=["a", "b"])


def _save(tmp_path: Path) -> Path:
    path = tmp_path / "monitor.mcift"
    _monitor().save(path)
    return path


def _refresh_checksum(bundle: Path, name: str) -> None:
    checksums_path = bundle / "checksums.json"
    checksums = json.loads(checksums_path.read_text(encoding="utf-8"))
    checksums[name] = hashlib.sha256((bundle / name).read_bytes()).hexdigest()
    checksums_path.write_text(json.dumps(checksums), encoding="utf-8")


def _rewrite_archive_member(bundle: Path, member_name: str, payload: bytes) -> None:
    arrays_path = bundle / "arrays.npz"
    with zipfile.ZipFile(arrays_path, "r") as archive:
        members = {info.filename: archive.read(info) for info in archive.infolist()}
    members.pop("channel_scales.npy")
    members[member_name] = payload
    with zipfile.ZipFile(arrays_path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    _refresh_checksum(bundle, "arrays.npz")


def test_load_rejects_top_level_symlink(tmp_path: Path) -> None:
    target = _save(tmp_path)
    link = tmp_path / "linked.mcift"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable")

    with pytest.raises(SerializationError, match="symlink"):
        MCIFTMonitor.load(link)


def test_load_rejects_component_symlink(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    external = tmp_path / "manifest-copy.json"
    external.write_bytes((bundle / "manifest.json").read_bytes())
    (bundle / "manifest.json").unlink()
    try:
        (bundle / "manifest.json").symlink_to(external)
    except OSError:
        pytest.skip("file symlinks are unavailable")

    with pytest.raises(SerializationError, match="symlink"):
        MCIFTMonitor.load(bundle)


def test_load_rejects_unexpected_file(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    (bundle / "extra.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(SerializationError, match="unexpected"):
        MCIFTMonitor.load(bundle)


def test_archive_compressed_and_uncompressed_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _save(tmp_path)
    monkeypatch.setattr(serialization, "MAX_ARCHIVE_COMPRESSED_BYTES", 1)
    with pytest.raises(SerializationError, match="compressed"):
        MCIFTMonitor.load(bundle)

    monkeypatch.setattr(serialization, "MAX_ARCHIVE_COMPRESSED_BYTES", 2**30)
    monkeypatch.setattr(serialization, "MAX_ARCHIVE_UNCOMPRESSED_BYTES", 1)
    with pytest.raises(SerializationError, match="uncompressed"):
        MCIFTMonitor.load(bundle)


def test_archive_rejects_oversized_array_shape(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    arrays_path = bundle / "arrays.npz"
    header = io.BytesIO()
    np.lib.format.write_array_header_1_0(
        header,
        {
            "descr": np.dtype(np.float64).str,
            "fortran_order": False,
            "shape": (serialization.MAX_ARRAY_ELEMENTS + 1,),
        },
    )
    with np.load(arrays_path, allow_pickle=False) as current:
        reference = np.asarray(current["reference_exchange"])
        edge_scales = np.asarray(current["edge_scales"])
    with zipfile.ZipFile(arrays_path, "w") as archive:
        archive.writestr("channel_scales.npy", header.getvalue())
        for name, array in (("reference_exchange", reference), ("edge_scales", edge_scales)):
            payload = io.BytesIO()
            np.lib.format.write_array(payload, array, allow_pickle=False)
            archive.writestr(f"{name}.npy", payload.getvalue())
    _refresh_checksum(bundle, "arrays.npz")

    with pytest.raises(SerializationError, match="dimensions|element limit"):
        MCIFTMonitor.load(bundle)


def test_load_rejects_duplicate_archive_members(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    arrays_path = bundle / "arrays.npz"
    with (
        pytest.warns(UserWarning, match="Duplicate name"),
        zipfile.ZipFile(arrays_path, "a") as archive,
    ):
        archive.writestr("channel_scales.npy", b"duplicate")
    _refresh_checksum(bundle, "arrays.npz")

    with pytest.raises(SerializationError, match="duplicate"):
        MCIFTMonitor.load(bundle)


def test_malformed_json_and_unknown_schema_are_rejected(tmp_path: Path) -> None:
    malformed = _save(tmp_path / "malformed")
    (malformed / "manifest.json").write_text("{", encoding="utf-8")
    _refresh_checksum(malformed, "manifest.json")
    with pytest.raises(SerializationError, match="invalid JSON"):
        MCIFTMonitor.load(malformed)

    unknown = _save(tmp_path / "unknown")
    manifest_path = unknown / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 999
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _refresh_checksum(unknown, "manifest.json")
    with pytest.raises(SerializationError, match="schema"):
        MCIFTMonitor.load(unknown)


def test_failed_atomic_save_leaves_no_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "failed.mcift"

    def fail_replace(source: os.PathLike[str], destination: os.PathLike[str]) -> None:
        raise OSError("simulated rename failure")

    monkeypatch.setattr(serialization.os, "replace", fail_replace)
    with pytest.raises(SerializationError, match="save model"):
        _monitor().save(target)

    assert not target.exists()
    assert not list(tmp_path.glob(".failed.mcift.tmp-*"))


@pytest.mark.parametrize(
    ("member_name", "match"),
    [
        ("/channel_scales.npy", "absolute"),
        ("../channel_scales.npy", "traversal"),
        ("nested/channel_scales.npy", "nested"),
    ],
)
def test_archive_rejects_unsafe_member_paths(tmp_path: Path, member_name: str, match: str) -> None:
    bundle = _save(tmp_path)
    payload = io.BytesIO()
    np.lib.format.write_array(payload, np.ones(2), allow_pickle=False)
    _rewrite_archive_member(bundle, member_name, payload.getvalue())

    with pytest.raises(SerializationError, match=match):
        MCIFTMonitor.load(bundle)


def test_archive_rejects_excessive_npy_header(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    header_length = serialization.MAX_NPY_HEADER_BYTES + 1
    payload = b"\x93NUMPY\x01\x00" + struct.pack("<H", header_length) + b" " * header_length
    _rewrite_archive_member(bundle, "channel_scales.npy", payload)

    with pytest.raises(SerializationError, match="header"):
        MCIFTMonitor.load(bundle)


def test_archive_rejects_declared_shape_payload_mismatch(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    payload = io.BytesIO()
    np.lib.format.write_array_header_1_0(
        payload,
        {"descr": np.dtype(np.float64).str, "fortran_order": False, "shape": (2,)},
    )
    payload.write(np.array([1.0], dtype=np.float64).tobytes())
    _rewrite_archive_member(bundle, "channel_scales.npy", payload.getvalue())

    with pytest.raises(SerializationError, match="payload size"):
        MCIFTMonitor.load(bundle)


def test_manifest_channel_count_must_match_array_shapes(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["channel_names"].append("c")
    manifest["channel_units"].append("V")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _refresh_checksum(bundle, "manifest.json")

    with pytest.raises(SerializationError, match="shape|channel"):
        MCIFTMonitor.load(bundle)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("processing_profile", "unknown", "processing profile"),
        ("gate_profile", "unknown", "gate profile"),
        ("calibration_sequence_mode", "unknown", "sequence mode"),
    ],
)
def test_serialization_rejects_unknown_versioned_identifiers(
    tmp_path: Path, field: str, value: str, match: str
) -> None:
    bundle = _save(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[field] = value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _refresh_checksum(bundle, "manifest.json")

    with pytest.raises(SerializationError, match=match):
        MCIFTMonitor.load(bundle)


def test_runtime_version_differences_are_provenance_warnings(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["numpy_version_at_fit"] = "0.0-test"
    manifest["python_version_at_fit"] = "0.0-test"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _refresh_checksum(bundle, "manifest.json")

    loaded = MCIFTMonitor.load(bundle)

    assert loaded.numpy_version_at_fit == "0.0-test"
    assert loaded.python_version_at_fit == "0.0-test"
    assert any("NumPy runtime version" in warning for warning in loaded.warnings)
    assert any("Python runtime version" in warning for warning in loaded.warnings)


def test_manifest_contains_compatibility_and_provenance_fields(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 4
    assert manifest["model_version"] == "0.1.0a1"
    assert manifest["gate_profile"] == "mcift.gates.exchange-screening.v1"
    assert manifest["calibration_sequence_mode"] == "unordered"
    assert manifest["minimum_reference_windows"] == 8
    assert manifest["minimum_calibration_windows"] == 20
    assert manifest["small_sample_override_used"] is False
    assert manifest["numpy_version_at_fit"]
    assert manifest["python_version_at_fit"]
    assert manifest["conventional_feature_version"] == (
        "mcift.vibration-features.centered-v1"
    )
    assert manifest["conventional_numerical_floor"] > 0.0
    assert manifest["conventional_thresholds_available"] is False

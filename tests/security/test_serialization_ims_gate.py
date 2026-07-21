# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from mcift import MCIFTMonitor, serialization
from mcift.exceptions import SerializationError
from mcift.profiles import IMS_SIX_GATE_PROFILE_ID, VIBRATION_PROFILE_ID
from mcift.vibration_features import CONVENTIONAL_FEATURE_VERSION


def _monitor() -> MCIFTMonitor:
    rng = np.random.default_rng(6400)
    return MCIFTMonitor.fit(
        rng.normal(size=(8, 24, 3)),
        sampling_rate_hz=20_000.0,
        channel_names=["a", "b", "c"],
        profile=VIBRATION_PROFILE_ID,
        gate_profile=IMS_SIX_GATE_PROFILE_ID,
    ).calibrate(rng.normal(size=(20, 24, 3)), sequence_order="chronological")


def _save(tmp_path: Path) -> Path:
    path = tmp_path / "ims.mcift"
    _monitor().save(path)
    return path


def _refresh(bundle: Path, component: str) -> None:
    checksums_path = bundle / "checksums.json"
    checksums = json.loads(checksums_path.read_text(encoding="utf-8"))
    checksums[component] = hashlib.sha256((bundle / component).read_bytes()).hexdigest()
    checksums_path.write_text(json.dumps(checksums), encoding="utf-8")


def test_schema4_six_gate_round_trip_preserves_thresholds(tmp_path: Path) -> None:
    monitor = _monitor()
    path = tmp_path / "roundtrip.mcift"
    monitor.save(path)
    loaded = MCIFTMonitor.load(path)

    assert loaded.gate_profile == IMS_SIX_GATE_PROFILE_ID
    assert loaded.conventional_feature_version == CONVENTIONAL_FEATURE_VERSION
    for before, after in (
        (monitor.conventional_rms_thresholds, loaded.conventional_rms_thresholds),
        (
            monitor.conventional_excess_kurtosis_thresholds,
            loaded.conventional_excess_kurtosis_thresholds,
        ),
        (
            monitor.conventional_crest_factor_thresholds,
            loaded.conventional_crest_factor_thresholds,
        ),
    ):
        assert before is not None and after is not None
        np.testing.assert_array_equal(after, before)
        assert not after.flags.writeable


@pytest.mark.parametrize("mutation", ["missing", "wrong_shape"])
def test_threshold_members_are_exact_and_shape_checked(tmp_path: Path, mutation: str) -> None:
    bundle = _save(tmp_path)
    arrays_path = bundle / "arrays.npz"
    with np.load(arrays_path, allow_pickle=False) as current:
        arrays = {name: np.asarray(current[name]) for name in current.files}
    if mutation == "missing":
        arrays.pop("conventional_rms_thresholds")
    else:
        arrays["conventional_rms_thresholds"] = np.ones(2, dtype=np.float64)
    np.savez(arrays_path, **arrays)
    _refresh(bundle, "arrays.npz")

    with pytest.raises(SerializationError, match="unexpected|shape"):
        MCIFTMonitor.load(bundle)


def test_unknown_conventional_feature_version_is_rejected(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["conventional_feature_version"] = "mcift.vibration-features.future.v9"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _refresh(bundle, "manifest.json")

    with pytest.raises(SerializationError, match="conventional feature version"):
        MCIFTMonitor.load(bundle)


def test_schema3_exchange_model_has_explicit_migration(tmp_path: Path) -> None:
    rng = np.random.default_rng(6401)
    monitor = MCIFTMonitor.fit(
        rng.normal(size=(8, 16, 2)), sampling_rate_hz=100.0, channel_names=["a", "b"]
    )
    bundle = tmp_path / "legacy.mcift"
    monitor.save(bundle)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 3
    manifest["model_version"] = "0.1.0.dev2"
    manifest.pop("conventional_feature_version")
    manifest.pop("conventional_numerical_floor")
    manifest.pop("conventional_thresholds_available")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _refresh(bundle, "manifest.json")

    loaded = MCIFTMonitor.load(bundle)

    assert loaded.gate_profile == "mcift.gates.exchange-screening.v1"
    assert loaded.model_version == "0.1.0a1"
    assert loaded.conventional_rms_thresholds is None
    assert any("schema3_to_schema4" in item for item in loaded.diagnostics)


def test_schemas_before_three_are_explicitly_rejected(tmp_path: Path) -> None:
    bundle = _save(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 2
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _refresh(bundle, "manifest.json")

    with pytest.raises(SerializationError, match="external migration"):
        MCIFTMonitor.load(bundle)


def test_conventional_arrays_remain_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _save(tmp_path)
    monkeypatch.setattr(serialization, "MAX_ARRAY_ELEMENTS", 2)
    with pytest.raises(SerializationError, match="element limit"):
        MCIFTMonitor.load(bundle)

# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path

import numpy as np

from mcift import MCIFTHistory, MCIFTMonitor


def _data() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(710)
    return rng.normal(size=(8, 32, 3)), rng.normal(size=(20, 32, 3))


def test_unordered_calibration_leaves_progression_unavailable() -> None:
    reference, calibration = _data()
    monitor = MCIFTMonitor.fit(
        reference, sampling_rate_hz=100.0, channel_names=["a", "b", "c"]
    ).calibrate(calibration)

    assert monitor.calibration_sequence_mode == "unordered"
    assert monitor.progression_slope_threshold is None
    result, _ = monitor.evaluate_with_history(calibration[0], history=MCIFTHistory())
    progression = next(gate for gate in result.gate_results if gate.name == "robust_progression")
    assert not progression.available
    assert progression.evidence["reason"] == "chronological_calibration_unavailable"


def test_chronological_calibration_fits_progression_and_round_trips(tmp_path: Path) -> None:
    reference, calibration = _data()
    monitor = MCIFTMonitor.fit(
        reference, sampling_rate_hz=100.0, channel_names=["a", "b", "c"]
    ).calibrate(calibration, sequence_order="chronological")

    assert monitor.calibration_sequence_mode == "chronological"
    assert monitor.progression_slope_threshold is not None

    bundle = tmp_path / "chronological.mcift"
    monitor.save(bundle)
    loaded = MCIFTMonitor.load(bundle)
    assert loaded.calibration_sequence_mode == "chronological"
    assert loaded.progression_slope_threshold == monitor.progression_slope_threshold


def test_shuffled_calibration_requires_explicit_chronological_declaration() -> None:
    reference, calibration = _data()
    shuffled = calibration[np.random.default_rng(711).permutation(len(calibration))]
    monitor = MCIFTMonitor.fit(
        reference, sampling_rate_hz=100.0, channel_names=["a", "b", "c"]
    ).calibrate(shuffled, sequence_order="unordered")

    assert monitor.progression_slope_threshold is None

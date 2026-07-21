# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

from pathlib import Path

import numpy as np

from mcift import MCIFTMonitor
from mcift.profiles import TELEMETRY_PROFILE_ID


def _windows(seed: int, count: int = 20) -> np.ndarray:
    rng = np.random.default_rng(seed)
    samples = 64
    time = np.arange(samples) / 64.0
    windows = []
    for _ in range(count):
        jitter = rng.normal(0.0, 0.01, size=(samples, 3))
        windows.append(
            np.column_stack(
                (
                    np.sin(2.0 * np.pi * 5.0 * time),
                    np.sin(2.0 * np.pi * 5.0 * time + 0.2),
                    np.sin(2.0 * np.pi * 8.0 * time),
                )
            )
            + jitter
        )
    return np.asarray(windows)


def test_fit_calibrate_evaluate_save_load_round_trip(tmp_path: Path) -> None:
    reference = _windows(1, count=8)
    calibration = _windows(2)
    monitor = MCIFTMonitor.fit(
        reference,
        sampling_rate_hz=64.0,
        channel_names=["input", "shaft", "output"],
        channel_units=["V", "m/s2", "V"],
    ).calibrate(calibration)

    before = monitor.reference_exchange.copy()
    result = monitor.evaluate(calibration[0])
    np.testing.assert_array_equal(monitor.reference_exchange, before)
    assert result.exchange_matrix.shape == (3, 3)
    assert np.isfinite(result.global_exchange_score)
    assert result.gate_results

    model_path = tmp_path / "monitor.mcift"
    monitor.save(model_path)
    loaded = MCIFTMonitor.load(model_path)
    loaded_result = loaded.evaluate(calibration[0])

    np.testing.assert_allclose(loaded_result.exchange_matrix, result.exchange_matrix)
    assert loaded_result.global_exchange_score == result.global_exchange_score
    assert loaded.channel_names == monitor.channel_names
    assert loaded.processing_profile == TELEMETRY_PROFILE_ID
    assert loaded.processing_profile == monitor.processing_profile

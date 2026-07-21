# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import json
from pathlib import Path

import numpy as np
import pytest

from mcift import MCIFTMonitor
from mcift.exchange import compute_exchange_matrix
from mcift.observables import compute_observables
from mcift.profiles import VIBRATION_PROFILE_ID

RTOL = 2e-12
ATOL = 2e-14


def _windows(seed: int, count: int, drift_step: float = 0.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    time = np.arange(64) / 64.0
    windows = []
    for index in range(count):
        drift = index * drift_step
        windows.append(
            np.column_stack(
                (
                    np.sin(2.0 * np.pi * 5.0 * time),
                    0.9
                    * np.sin(
                        2.0 * np.pi * (5.25 + 0.08 * drift) * time
                        + 0.25
                        + drift
                    ),
                    1.1
                    * np.sin(
                        2.0 * np.pi * (5.6 + 0.12 * drift) * time
                        - 0.15
                        - 0.3 * drift
                    ),
                )
            )
            + rng.normal(0.0, 0.025, size=(64, 3))
        )
    return np.asarray(windows, dtype=np.float64)


def test_vibration_profile_matches_frozen_historical_adapter() -> None:
    expected = json.loads(
        Path(__file__).with_name("historical_vibration_v1.json").read_text(encoding="utf-8")
    )
    reference = _windows(710, 8)
    calibration = _windows(711, 20)
    sequence = _windows(712, 15, drift_step=0.09)
    monitor = MCIFTMonitor.fit(
        reference,
        sampling_rate_hz=64.0,
        channel_names=["a", "b", "c"],
        channel_units=["V", "V", "V"],
        profile=VIBRATION_PROFILE_ID,
    )
    observables = compute_observables(reference[0], monitor.channel_scales, 64.0)
    matrix = compute_exchange_matrix(
        observables.information,
        observables.omega,
        observables.phase,
        sigma_i=monitor.sigma_i,
        sigma_omega=monitor.sigma_omega,
    )
    calibrated = monitor.calibrate(calibration)
    sequence_scores = [
        calibrated.evaluate(window).global_exchange_score for window in sequence
    ]
    first_positive = next(
        (
            index
            for index, score in enumerate(sequence_scores)
            if score > calibrated.global_threshold
        ),
        None,
    )

    np.testing.assert_allclose(monitor.channel_scales, expected["channel_scales"], rtol=RTOL)
    np.testing.assert_allclose(
        (reference[0] - reference[0].mean(axis=0)) / monitor.channel_scales,
        expected["centered_scaled_first_window"],
        rtol=RTOL,
        atol=ATOL,
    )
    np.testing.assert_allclose(observables.information, expected["information"], rtol=RTOL)
    np.testing.assert_allclose(observables.omega, expected["omega"], rtol=RTOL)
    np.testing.assert_allclose(observables.phase, expected["phase"], rtol=RTOL)
    assert observables.shared_bin == expected["shared_bin"]
    assert monitor.sigma_i == pytest.approx(expected["sigma_i"], rel=RTOL, abs=ATOL)
    assert monitor.sigma_omega == pytest.approx(
        expected["sigma_omega"], rel=RTOL, abs=ATOL
    )
    np.testing.assert_allclose(matrix, expected["exchange_matrix"], rtol=RTOL, atol=ATOL)
    np.testing.assert_allclose(
        monitor.reference_exchange, expected["reference_exchange"], rtol=RTOL, atol=ATOL
    )
    np.testing.assert_allclose(
        monitor.edge_scales,
        expected["edge_scales_package_extension"],
        rtol=RTOL,
        atol=ATOL,
    )
    assert calibrated.global_threshold == pytest.approx(
        expected["calibrated_threshold"], rel=RTOL, abs=ATOL
    )
    np.testing.assert_allclose(
        sequence_scores, expected["sequence_scores"], rtol=RTOL, atol=ATOL
    )
    assert first_positive == expected["first_positive_index"]

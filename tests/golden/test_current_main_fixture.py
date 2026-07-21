# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import json
from pathlib import Path

import numpy as np
import pytest

from mcift import MCIFTMonitor
from mcift.exchange import compute_exchange_matrix
from mcift.observables import compute_observables

ALGEBRA_RTOL = 1e-13
ALGEBRA_ATOL = 1e-15
FFT_RTOL = 5e-12
FFT_ATOL = 1e-12


def synthetic_windows(
    seed: int,
    count: int,
    *,
    drift_start: float = 0.0,
    drift_step: float = 0.0,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    time = np.arange(64) / 64.0
    result = []
    for index in range(count):
        drift = drift_start + index * drift_step
        base = np.column_stack(
            (
                np.sin(2.0 * np.pi * 5.0 * time),
                0.8 * np.sin(2.0 * np.pi * 5.0 * time + 0.2 + drift),
                1.2 * np.sin(2.0 * np.pi * (8.0 + 0.15 * drift) * time - 0.1),
            )
        )
        result.append(base + rng.normal(0.0, 0.015, size=base.shape))
    return np.asarray(result, dtype=np.float64)


def test_current_main_telemetry_outputs_are_frozen() -> None:
    fixture_path = Path(__file__).with_name("current_main_telemetry_v1.json")
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))
    reference = synthetic_windows(101, 8)
    calibration = synthetic_windows(202, 20)
    sequence = synthetic_windows(303, 12, drift_step=0.12)

    monitor = MCIFTMonitor.fit(
        reference,
        sampling_rate_hz=64.0,
        channel_names=["a", "b", "c"],
        channel_units=["V", "V", "V"],
    ).calibrate(calibration)
    observables = compute_observables(reference[0], monitor.channel_scales, 64.0)
    exchange = compute_exchange_matrix(
        observables.information,
        observables.omega,
        observables.phase,
        sigma_i=monitor.sigma_i,
        sigma_omega=monitor.sigma_omega,
    )
    scores = [monitor.evaluate(window).global_exchange_score for window in sequence]
    first_positive = next(
        (index for index, score in enumerate(scores) if score > monitor.global_threshold),
        None,
    )

    np.testing.assert_allclose(
        (reference[0] - reference[0].mean(axis=0)) / monitor.channel_scales,
        expected["centered_scaled_first_window"],
        rtol=ALGEBRA_RTOL,
        atol=ALGEBRA_ATOL,
    )
    np.testing.assert_allclose(
        monitor.channel_scales, expected["channel_scales"], rtol=ALGEBRA_RTOL
    )
    np.testing.assert_allclose(observables.information, expected["information"], rtol=ALGEBRA_RTOL)
    np.testing.assert_allclose(observables.omega, expected["omega"], rtol=FFT_RTOL, atol=FFT_ATOL)
    circular_delta = np.angle(np.exp(1j * (observables.phase - np.asarray(expected["phase"]))))
    np.testing.assert_allclose(circular_delta, 0.0, rtol=0.0, atol=FFT_ATOL)
    assert observables.shared_bin == expected["shared_bin"]
    assert monitor.sigma_i == pytest.approx(expected["sigma_i"], rel=FFT_RTOL)
    assert monitor.sigma_omega == pytest.approx(expected["sigma_omega"], rel=FFT_RTOL)
    np.testing.assert_allclose(exchange, expected["exchange_matrix"], rtol=FFT_RTOL, atol=FFT_ATOL)
    np.testing.assert_allclose(
        monitor.reference_exchange,
        expected["reference_exchange"],
        rtol=FFT_RTOL,
        atol=FFT_ATOL,
    )
    np.testing.assert_allclose(
        monitor.edge_scales,
        expected["edge_scales"],
        rtol=FFT_RTOL,
        atol=FFT_ATOL,
    )
    assert monitor.global_threshold == pytest.approx(expected["global_threshold"], rel=FFT_RTOL)
    assert monitor.local_edge_threshold == pytest.approx(
        expected["local_edge_threshold"], rel=FFT_RTOL
    )
    np.testing.assert_allclose(scores, expected["sequence_scores"], rtol=FFT_RTOL, atol=FFT_ATOL)
    assert first_positive == expected["first_positive_index"]
    assert np.argsort(np.asarray(scores), kind="stable").tolist() == expected["score_order"]
    assert [monitor.evaluate(window).final_decision for window in sequence] == expected["decisions"]

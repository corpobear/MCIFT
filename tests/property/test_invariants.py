# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import numpy as np
import pytest

from mcift import MCIFTMonitor
from mcift.exchange import compute_exchange_matrix
from mcift.observables import compute_observables
from mcift.scoring import global_exchange_score


def test_channel_permutation_permutes_exchange_and_preserves_score() -> None:
    rng = np.random.default_rng(11)
    window = rng.normal(size=(128, 4))
    scales = np.array([0.8, 1.1, 0.9, 1.2])
    observables = compute_observables(window, scales, 256.0)
    matrix = compute_exchange_matrix(
        observables.information,
        observables.omega,
        observables.phase,
        sigma_i=0.7,
        sigma_omega=20.0,
    )
    reference = matrix * 0.9
    permutation = np.array([2, 0, 3, 1])
    permuted_observables = compute_observables(
        window[:, permutation], scales[permutation], 256.0
    )
    permuted_matrix = compute_exchange_matrix(
        permuted_observables.information,
        permuted_observables.omega,
        permuted_observables.phase,
        sigma_i=0.7,
        sigma_omega=20.0,
    )

    np.testing.assert_allclose(permuted_matrix, matrix[np.ix_(permutation, permutation)])
    assert global_exchange_score(
        permuted_matrix, reference[np.ix_(permutation, permutation)]
    ) == pytest.approx(global_exchange_score(matrix, reference), rel=1e-12, abs=1e-15)


def test_constant_window_returns_finite_observables_with_diagnostics() -> None:
    result = compute_observables(np.ones((16, 2)), np.ones(2), 100.0)

    assert np.all(np.isfinite(result.information))
    np.testing.assert_array_equal(result.omega, np.zeros(2))
    assert len(result.diagnostics) == 2


def test_matching_window_and_scale_amplitude_change_is_neutral() -> None:
    rng = np.random.default_rng(12)
    window = rng.normal(size=(64, 3))
    scales = np.array([1.0, 2.0, 3.0])

    baseline = compute_observables(window, scales, 64.0)
    scaled = compute_observables(window * 4.0, scales * 4.0, 64.0)

    np.testing.assert_allclose(baseline.information, scaled.information)
    np.testing.assert_allclose(baseline.omega, scaled.omega)
    np.testing.assert_allclose(baseline.phase, scaled.phase)


def test_consistent_whole_system_unit_rescaling_preserves_evaluation() -> None:
    rng = np.random.default_rng(13)
    reference = rng.normal(size=(8, 48, 3))
    calibration = rng.normal(size=(20, 48, 3))
    current = rng.normal(size=(48, 3))

    base = MCIFTMonitor.fit(
        reference,
        sampling_rate_hz=96.0,
        channel_names=["a", "b", "c"],
    ).calibrate(calibration)
    rescaled = MCIFTMonitor.fit(
        reference * 1000.0,
        sampling_rate_hz=96.0,
        channel_names=["a", "b", "c"],
    ).calibrate(calibration * 1000.0)

    base_result = base.evaluate(current)
    rescaled_result = rescaled.evaluate(current * 1000.0)

    np.testing.assert_allclose(
        rescaled_result.exchange_matrix,
        base_result.exchange_matrix,
        rtol=2e-12,
        atol=2e-14,
    )
    assert rescaled_result.global_exchange_score == pytest.approx(
        base_result.global_exchange_score, rel=2e-12, abs=2e-14
    )
    assert rescaled.global_threshold == pytest.approx(
        base.global_threshold, rel=2e-12, abs=2e-14
    )

# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import numpy as np

from mcift.exchange import compute_exchange_matrix, mean_exchange
from mcift.observables import compute_observables


def test_observables_use_one_shared_dominant_bin() -> None:
    samples = 64
    sampling_rate = 64.0
    time = np.arange(samples) / sampling_rate
    window = np.column_stack(
        (
            np.sin(2.0 * np.pi * 5.0 * time),
            np.sin(2.0 * np.pi * 5.0 * time + 0.25),
        )
    )

    result = compute_observables(window, np.ones(2), sampling_rate)

    assert result.shared_bin == 5
    np.testing.assert_allclose(result.omega, np.full(2, 2.0 * np.pi * 5.0), rtol=1e-12)
    assert not result.diagnostics


def test_exchange_matrix_is_symmetric_finite_and_has_zero_diagonal() -> None:
    information = np.array([0.0, 0.2, -0.1])
    omega = np.array([1.0, 2.0, 1.5])
    phase = np.array([0.0, 0.4, -0.3])

    matrix = compute_exchange_matrix(information, omega, phase, sigma_i=0.5, sigma_omega=2.0)

    np.testing.assert_allclose(matrix, matrix.T)
    np.testing.assert_array_equal(np.diag(matrix), np.zeros(3))
    assert np.all(np.isfinite(matrix))
    assert np.all(matrix >= 0.0)
    assert 0.0 <= mean_exchange(matrix) <= 1.0


def test_phase_shift_by_pi_preserves_exchange() -> None:
    base = compute_exchange_matrix(
        np.zeros(2), np.zeros(2), np.array([0.0, 0.3]), sigma_i=1.0, sigma_omega=1.0
    )
    shifted = compute_exchange_matrix(
        np.zeros(2),
        np.zeros(2),
        np.array([0.0, 0.3 + np.pi]),
        sigma_i=1.0,
        sigma_omega=1.0,
    )

    np.testing.assert_allclose(base, shifted, atol=1e-15)

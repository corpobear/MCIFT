# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import numpy as np
import pytest

from mcift.exceptions import ValidationError
from mcift.vibration_features import compute_vibration_features


def _known_window() -> np.ndarray:
    return np.column_stack(
        (
            np.array([-1.0, 1.0, -1.0, 1.0]),
            np.array([-1.0, 0.0, 1.0, 0.0]),
        )
    )


def test_known_centered_rms_crest_factor_and_excess_kurtosis() -> None:
    result = compute_vibration_features(_known_window())

    np.testing.assert_allclose(result.centered_rms, [1.0, np.sqrt(0.5)])
    np.testing.assert_allclose(result.crest_factor, [1.0, np.sqrt(2.0)])
    np.testing.assert_allclose(result.excess_kurtosis, [-2.0, -1.0])


@pytest.mark.parametrize("constant", [0.0, 7.5])
def test_constant_and_zero_signals_use_finite_zero_fallback(constant: float) -> None:
    result = compute_vibration_features(np.full((8, 2), constant))

    np.testing.assert_array_equal(result.centered_rms, np.zeros(2))
    np.testing.assert_array_equal(result.crest_factor, np.zeros(2))
    np.testing.assert_array_equal(result.excess_kurtosis, np.zeros(2))
    assert len(result.diagnostics) == 2
    assert all(not array.flags.writeable for array in (
        result.centered_rms,
        result.crest_factor,
        result.excess_kurtosis,
    ))


def test_scaling_and_channel_permutation_are_deterministic() -> None:
    window = _known_window()
    base = compute_vibration_features(window)
    scaled = compute_vibration_features(window * -4.0)
    permutation = np.array([1, 0])
    permuted = compute_vibration_features(window[:, permutation])
    repeated = compute_vibration_features(window)

    np.testing.assert_allclose(scaled.centered_rms, base.centered_rms * 4.0)
    np.testing.assert_allclose(scaled.crest_factor, base.crest_factor)
    np.testing.assert_allclose(scaled.excess_kurtosis, base.excess_kurtosis)
    for name in ("centered_rms", "crest_factor", "excess_kurtosis"):
        np.testing.assert_array_equal(getattr(permuted, name), getattr(base, name)[permutation])
        np.testing.assert_array_equal(getattr(repeated, name), getattr(base, name))


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_nonfinite_input_is_rejected(bad: float) -> None:
    window = np.ones((8, 2))
    window[0, 0] = bad
    with pytest.raises(ValidationError, match="non-finite"):
        compute_vibration_features(window)

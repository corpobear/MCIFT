# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Reference fitting and robust calibration helpers."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import numpy as np

from .exchange import compute_exchange_matrix
from .observables import DEFAULT_EPSILON, compute_observables
from .types import FloatArray, ObservableResult

MAD_FACTOR = 1.4826


def robust_scale(values: FloatArray, *, epsilon: float = DEFAULT_EPSILON) -> tuple[float, str]:
    """Return MAD scale, standard-deviation fallback, or final unit fallback."""
    array = np.asarray(values, dtype=np.float64)
    median = np.median(array)
    mad_scale = float(MAD_FACTOR * np.median(np.abs(array - median)))
    if np.isfinite(mad_scale) and mad_scale > epsilon:
        return mad_scale, "mad"
    standard = float(np.std(array, dtype=np.float64))
    if np.isfinite(standard) and standard > epsilon:
        return standard, "standard_deviation_fallback"
    return 1.0, "unit_fallback"


def fit_channel_scales(windows: Sequence[FloatArray]) -> tuple[FloatArray, tuple[str, ...]]:
    """Fit generic-telemetry scales across reference observations."""
    stacked = np.concatenate(windows, axis=0)
    scales = np.empty(stacked.shape[1], dtype=np.float64)
    diagnostics: list[str] = []
    for channel in range(stacked.shape[1]):
        scales[channel], method = robust_scale(stacked[:, channel])
        if method != "mad":
            diagnostics.append(f"channel_scale:{method}:channel={channel}")
    scales.setflags(write=False)
    return scales, tuple(diagnostics)


def fit_exchange_reference(
    windows: Sequence[FloatArray],
    channel_scales: FloatArray,
    sampling_rate_hz: float,
    *,
    scale_epsilon: float = DEFAULT_EPSILON,
) -> tuple[float, float, FloatArray, FloatArray, tuple[str, ...]]:
    """Fit frozen sigmas, healthy exchange matrix, and robust edge scales."""
    observables = tuple(
        compute_observables(window, channel_scales, sampling_rate_hz) for window in windows
    )
    delta_i = _pairwise_differences(observables, field="information")
    delta_omega = _pairwise_differences(observables, field="omega")
    sigma_i, sigma_i_method = robust_scale(delta_i, epsilon=scale_epsilon)
    sigma_omega, sigma_omega_method = robust_scale(delta_omega, epsilon=scale_epsilon)
    diagnostics = [item for result in observables for item in result.diagnostics]
    if sigma_i_method != "mad":
        diagnostics.append(f"sigma_i:{sigma_i_method}")
    if sigma_omega_method != "mad":
        diagnostics.append(f"sigma_omega:{sigma_omega_method}")
    matrices = np.asarray(
        [
            compute_exchange_matrix(
                result.information,
                result.omega,
                result.phase,
                sigma_i=sigma_i,
                sigma_omega=sigma_omega,
            )
            for result in observables
        ],
        dtype=np.float64,
    )
    reference = np.median(matrices, axis=0)
    edge_scales = np.zeros_like(reference)
    for first, second in zip(*np.triu_indices(reference.shape[0], k=1), strict=True):
        scale, method = robust_scale(matrices[:, first, second], epsilon=scale_epsilon)
        edge_scales[first, second] = scale
        edge_scales[second, first] = scale
        if method != "mad":
            diagnostics.append(f"edge_scale:{method}:edge={first},{second}")
    reference.setflags(write=False)
    edge_scales.setflags(write=False)
    return sigma_i, sigma_omega, reference, edge_scales, tuple(diagnostics)


def calibration_quantile(
    values: FloatArray,
    quantile: float = 0.99,
    *,
    method: Literal["higher", "linear"] = "higher",
) -> float:
    """Fit a conservative finite threshold from calibration scores."""
    return float(np.quantile(np.asarray(values, dtype=np.float64), quantile, method=method))


def calibration_quantiles(
    values: FloatArray,
    quantile: float = 0.99,
    *,
    method: Literal["higher", "linear"] = "higher",
) -> FloatArray:
    """Fit independent finite upper thresholds for every feature column."""
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2 or array.shape[0] == 0:
        raise ValueError("calibration feature values must be a non-empty matrix")
    result = np.asarray(np.quantile(array, quantile, axis=0, method=method), dtype=np.float64)
    result.setflags(write=False)
    return result


def _pairwise_differences(
    results: Sequence[ObservableResult], *, field: str
) -> FloatArray:
    rows: list[FloatArray] = []
    for result in results:
        values = getattr(result, field)
        rows.append(np.abs(values[:, None] - values[None, :])[np.triu_indices(values.size, k=1)])
    return np.concatenate(rows)

# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Stable v1 pairwise exchange calculations."""

from __future__ import annotations

import numpy as np

from .exceptions import ValidationError
from .types import FloatArray


def compute_exchange_matrix(
    information: FloatArray,
    omega: FloatArray,
    phase: FloatArray,
    *,
    sigma_i: float,
    sigma_omega: float,
    g: float = 1.0,
) -> FloatArray:
    """Construct the symmetric stable-v1 exchange matrix."""
    info = _validate_vector(information, "information")
    angular = _validate_vector(omega, "omega")
    angles = _validate_vector(phase, "phase")
    if info.shape != angular.shape or info.shape != angles.shape:
        raise ValidationError("observable vectors must have identical shapes")
    if info.size < 2:
        raise ValidationError("exchange requires at least two channels")
    sigma_info = _positive_float(sigma_i, "sigma_i")
    sigma_frequency = _positive_float(sigma_omega, "sigma_omega")
    coupling = _positive_float(g, "g")

    delta_i = info[:, None] - info[None, :]
    delta_omega = angular[:, None] - angular[None, :]
    delta_phase = _wrap_phase(angles[:, None] - angles[None, :])
    matrix = coupling * np.exp(-np.square(delta_i) / (2.0 * sigma_info**2))
    matrix *= np.exp(-np.square(delta_omega) / (2.0 * sigma_frequency**2))
    matrix *= np.square(np.cos(delta_phase))
    np.fill_diagonal(matrix, 0.0)
    if not np.all(np.isfinite(matrix)):
        raise ValidationError("exchange calculation produced non-finite values")
    return matrix


def mean_exchange(matrix: FloatArray) -> float:
    """Return the mean over unique edges."""
    validated = _validate_matrix(matrix)
    upper = validated[np.triu_indices(validated.shape[0], k=1)]
    return float(np.mean(upper, dtype=np.float64))


def densification(matrix: FloatArray, *, eta: float = 1.0) -> float:
    """Return the auxiliary densification observable."""
    if not np.isfinite(eta):
        raise ValidationError("eta must be finite")
    return float(np.exp(float(eta) * mean_exchange(matrix)))


def _validate_vector(values: FloatArray, name: str) -> FloatArray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 1 or not np.all(np.isfinite(result)):
        raise ValidationError(f"{name} must be a finite one-dimensional vector")
    return result


def _validate_matrix(matrix: FloatArray) -> FloatArray:
    result = np.asarray(matrix, dtype=np.float64)
    if result.ndim != 2 or result.shape[0] != result.shape[1] or result.shape[0] < 2:
        raise ValidationError("exchange matrix must be square with at least two channels")
    if not np.all(np.isfinite(result)):
        raise ValidationError("exchange matrix must be finite")
    return result


def _positive_float(value: float, name: str) -> float:
    result = float(value)
    if not np.isfinite(result) or result <= 0.0:
        raise ValidationError(f"{name} must be finite and positive")
    return result


def _wrap_phase(values: FloatArray) -> FloatArray:
    return (values + np.pi) % (2.0 * np.pi) - np.pi

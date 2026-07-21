# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Stable global and local exchange deformation scores."""

from __future__ import annotations

import numpy as np

from .exceptions import ValidationError
from .observables import DEFAULT_EPSILON
from .types import FloatArray


def global_exchange_score(current: FloatArray, reference: FloatArray) -> float:
    """Compute RMS difference over unique relationship edges."""
    current_matrix, reference_matrix = _paired_matrices(current, reference)
    upper = np.triu_indices(current_matrix.shape[0], k=1)
    differences = current_matrix[upper] - reference_matrix[upper]
    return float(np.sqrt(np.mean(np.square(differences), dtype=np.float64)))


def edge_residuals(
    current: FloatArray,
    reference: FloatArray,
    edge_scales: FloatArray,
    *,
    epsilon: float = DEFAULT_EPSILON,
) -> FloatArray:
    """Compute symmetric standardized absolute edge damage."""
    current_matrix, reference_matrix = _paired_matrices(current, reference)
    scales = np.asarray(edge_scales, dtype=np.float64)
    if scales.shape != current_matrix.shape:
        raise ValidationError("edge scales must match exchange matrix shape")
    if not np.all(np.isfinite(scales)) or np.any(scales < 0.0):
        raise ValidationError("edge scales must be finite and non-negative")
    result = np.abs(current_matrix - reference_matrix) / (scales + epsilon)
    np.fill_diagonal(result, 0.0)
    return result


def node_incident_damage_ratio(
    residuals: FloatArray, *, epsilon: float = DEFAULT_EPSILON
) -> FloatArray:
    """Return each node's incident damage divided by unique-edge damage.

    Every unique edge contributes to two nodes, so non-zero results sum to
    approximately two. These values are not probabilities.
    """
    matrix = _matrix(residuals)
    denominator = np.sum(matrix[np.triu_indices(matrix.shape[0], k=1)], dtype=np.float64)
    incident_damage = np.asarray(np.sum(matrix, axis=1, dtype=np.float64), dtype=np.float64)
    return incident_damage / (denominator + epsilon)


def node_concentration(
    residuals: FloatArray, *, epsilon: float = DEFAULT_EPSILON
) -> FloatArray:
    """Compatibility alias for :func:`node_incident_damage_ratio`."""
    return node_incident_damage_ratio(residuals, epsilon=epsilon)


def _paired_matrices(first: FloatArray, second: FloatArray) -> tuple[FloatArray, FloatArray]:
    first_matrix = _matrix(first)
    second_matrix = _matrix(second)
    if first_matrix.shape != second_matrix.shape:
        raise ValidationError("exchange matrices must have identical shapes")
    return first_matrix, second_matrix


def _matrix(values: FloatArray) -> FloatArray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 2 or result.shape[0] != result.shape[1] or result.shape[0] < 2:
        raise ValidationError("matrix must be square with at least two channels")
    if not np.all(np.isfinite(result)):
        raise ValidationError("matrix must contain only finite values")
    return result

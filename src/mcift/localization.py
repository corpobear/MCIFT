# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Explainable candidate localization helpers."""

from __future__ import annotations

import numpy as np

from .exceptions import ValidationError
from .types import FloatArray


def top_damaged_edge(residuals: FloatArray) -> tuple[int, int, float]:
    """Return the endpoints and value of the strongest unique edge."""
    matrix = np.asarray(residuals, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or matrix.shape[0] < 2:
        raise ValidationError("edge residual matrix must be square")
    if not np.all(np.isfinite(matrix)) or np.any(matrix < 0.0):
        raise ValidationError("edge residual matrix must be finite and non-negative")
    upper = np.triu_indices(matrix.shape[0], k=1)
    position = int(np.argmax(matrix[upper]))
    first = int(upper[0][position])
    second = int(upper[1][position])
    return first, second, float(matrix[first, second])

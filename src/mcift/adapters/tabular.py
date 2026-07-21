# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Tabular window validation adapter."""

from __future__ import annotations

import numpy.typing as npt

from ..types import FloatArray
from ..validation import validate_window


def adapt_tabular_window(values: npt.ArrayLike) -> FloatArray:
    """Validate an already-windowed tabular array without inferring units."""
    return validate_window(values)

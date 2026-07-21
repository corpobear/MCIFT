# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Deterministic vibration reference-scale helpers."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ..calibration import robust_scale
from ..types import FloatArray


def fit_vibration_scales(
    windows: Sequence[FloatArray], *, scale_epsilon: float = 1e-12
) -> tuple[FloatArray, tuple[str, ...]]:
    """Fit median centered reference-window RMS with declared fallbacks."""
    rms = np.asarray(
        [
            np.sqrt(
                np.mean(
                    np.square(window - np.mean(window, axis=0, dtype=np.float64)),
                    axis=0,
                    dtype=np.float64,
                )
            )
            for window in windows
        ]
    )
    scales = np.median(rms, axis=0)
    diagnostics: list[str] = []
    for channel in range(scales.size):
        if not np.isfinite(scales[channel]) or scales[channel] <= scale_epsilon:
            concatenated = np.concatenate([window[:, channel] for window in windows])
            scales[channel], method = robust_scale(concatenated, epsilon=scale_epsilon)
            diagnostics.append(f"vibration_scale:{method}:channel={channel}")
    scales.setflags(write=False)
    return scales, tuple(diagnostics)

# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Stable v1 per-channel observables."""

from __future__ import annotations

import numpy as np

from .exceptions import ValidationError
from .types import FloatArray, ObservableResult
from .validation import validate_sampling_rate, validate_window

DEFAULT_EPSILON = np.finfo(np.float64).eps


def compute_observables(
    window: FloatArray,
    channel_scales: FloatArray,
    sampling_rate_hz: float,
    *,
    epsilon: float = DEFAULT_EPSILON,
) -> ObservableResult:
    """Compute information, angular frequency, and shared-bin phase."""
    data = validate_window(window)
    sampling_rate = validate_sampling_rate(sampling_rate_hz)
    scales = np.asarray(channel_scales, dtype=np.float64)
    if scales.shape != (data.shape[1],):
        raise ValidationError("channel scales must contain one value per channel")
    if not np.all(np.isfinite(scales)) or np.any(scales <= 0.0):
        raise ValidationError("channel scales must be finite and positive")
    if not np.isfinite(epsilon) or epsilon <= 0.0:
        raise ValidationError("epsilon must be finite and positive")

    centered_scaled = (data - np.mean(data, axis=0, dtype=np.float64)) / scales
    rms = np.sqrt(np.mean(np.square(centered_scaled), axis=0, dtype=np.float64))
    information = np.log(rms + epsilon)

    spectrum = np.fft.rfft(centered_scaled, axis=0)
    power = np.square(np.abs(spectrum))
    if power.shape[0] > 1:
        power[0, :] = 0.0
    frequencies = np.fft.rfftfreq(data.shape[0], d=1.0 / sampling_rate)
    total_power = np.asarray(np.sum(power, axis=0, dtype=np.float64), dtype=np.float64)
    omega = np.zeros(data.shape[1], dtype=np.float64)
    nonzero = total_power > 0.0
    weighted_power = np.asarray(
        np.sum((2.0 * np.pi * frequencies[:, None]) * power[:, nonzero], axis=0),
        dtype=np.float64,
    )
    omega[nonzero] = weighted_power / total_power[nonzero]
    diagnostics = tuple(
        f"zero_non_dc_power:channel={index}"
        for index in np.flatnonzero(~nonzero).tolist()
    )

    shared_bin = int(np.argmax(np.sum(power, axis=1, dtype=np.float64)))
    phase = np.angle(spectrum[shared_bin, :]).astype(np.float64, copy=False)
    return ObservableResult(
        information=_readonly(information),
        omega=_readonly(omega),
        phase=_readonly(phase),
        shared_bin=shared_bin,
        diagnostics=diagnostics,
    )


def _readonly(array: FloatArray) -> FloatArray:
    result = np.asarray(array, dtype=np.float64)
    result.setflags(write=False)
    return result

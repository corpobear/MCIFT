# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Stable deterministic conventional vibration features."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from .exceptions import ValidationError
from .types import FloatArray

CONVENTIONAL_FEATURE_VERSION = "mcift.vibration-features.centered-v1"
DEFAULT_NUMERICAL_FLOOR = 1e-12
FEATURE_NAMES = ("centered_rms", "excess_kurtosis", "crest_factor")


def _readonly(values: npt.ArrayLike) -> FloatArray:
    result = np.array(values, dtype=np.float64, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class VibrationFeatureValues:
    """Per-channel centred conventional feature values for one window."""

    centered_rms: FloatArray
    excess_kurtosis: FloatArray
    crest_factor: FloatArray
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        arrays = tuple(
            _readonly(getattr(self, name)) for name in FEATURE_NAMES
        )
        if arrays[0].ndim != 1 or any(array.shape != arrays[0].shape for array in arrays):
            raise ValidationError(
                "vibration feature arrays must be matching one-dimensional arrays"
            )
        if any(not np.all(np.isfinite(array)) for array in arrays):
            raise ValidationError("vibration feature arrays must be finite")
        for name, array in zip(FEATURE_NAMES, arrays, strict=True):
            object.__setattr__(self, name, array)


def compute_vibration_features(
    window: npt.ArrayLike, *, numerical_floor: float = DEFAULT_NUMERICAL_FLOOR
) -> VibrationFeatureValues:
    """Compute centred RMS, excess kurtosis, and crest factor in float64.

    Channels whose centred RMS is at or below ``numerical_floor`` receive finite
    fallback values of ``0.0`` for crest factor and excess kurtosis.
    """
    if not np.isfinite(numerical_floor) or numerical_floor <= 0.0:
        raise ValidationError("vibration feature numerical floor must be finite and positive")
    source = np.asarray(window)
    if source.dtype.hasobject or source.ndim != 2:
        raise ValidationError("vibration window must be a numeric samples-by-channels array")
    try:
        values = np.array(source, dtype=np.float64, copy=True)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValidationError("vibration window must be convertible to float64") from error
    if not np.all(np.isfinite(values)):
        raise ValidationError("vibration window contains non-finite values")
    if values.shape[0] < 4 or values.shape[1] < 1:
        raise ValidationError("vibration window must contain at least 4 samples and 1 channel")
    centered = values - np.mean(values, axis=0, dtype=np.float64)
    if not np.all(np.isfinite(centered)):
        raise ValidationError("centred vibration window is outside float64 range")

    channels = values.shape[1]
    rms = np.empty(channels, dtype=np.float64)
    kurtosis = np.empty(channels, dtype=np.float64)
    crest = np.empty(channels, dtype=np.float64)
    diagnostics: list[str] = []
    for channel in range(channels):
        channel_values = centered[:, channel]
        peak = float(np.max(np.abs(channel_values)))
        if peak == 0.0:
            channel_rms = 0.0
            normalized_rms = 0.0
        else:
            normalized = channel_values / peak
            normalized_rms = float(
                np.sqrt(np.mean(np.square(normalized), dtype=np.float64))
            )
            channel_rms = peak * normalized_rms
        rms[channel] = channel_rms
        if channel_rms <= numerical_floor or normalized_rms == 0.0:
            crest[channel] = 0.0
            kurtosis[channel] = 0.0
            diagnostics.append(
                f"conventional_feature:finite_zero_fallback:channel={channel}:"
                f"rms={channel_rms:.17g}:floor={numerical_floor:.17g}"
            )
            continue
        crest[channel] = 1.0 / normalized_rms
        fourth_moment = float(np.mean(np.power(normalized, 4), dtype=np.float64))
        kurtosis[channel] = fourth_moment / normalized_rms**4 - 3.0

    return VibrationFeatureValues(
        centered_rms=rms,
        excess_kurtosis=kurtosis,
        crest_factor=crest,
        diagnostics=tuple(diagnostics),
    )

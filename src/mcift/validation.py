# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Fail-early validation for untrusted arrays and metadata."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from .exceptions import ValidationError
from .types import FloatArray


@dataclass(frozen=True)
class ValidationLimits:
    """Conservative aggregate limits suitable for an 8 GB laptop."""

    max_total_elements: int = 100_000_000
    max_total_bytes: int = 800_000_000
    max_windows: int = 10_000
    max_samples_per_window: int = 1_000_000
    max_channels: int = 256

    def __post_init__(self) -> None:
        if (
            min(
                self.max_total_elements,
                self.max_total_bytes,
                self.max_windows,
                self.max_samples_per_window,
                self.max_channels,
            )
            <= 0
        ):
            raise ValueError("validation limits must be positive")


DEFAULT_LIMITS = ValidationLimits()
DEFAULT_MAX_SAMPLES = DEFAULT_LIMITS.max_samples_per_window
DEFAULT_MAX_CHANNELS = DEFAULT_LIMITS.max_channels
DEFAULT_MAX_WINDOWS = DEFAULT_LIMITS.max_windows


def validate_window(
    window: npt.ArrayLike,
    *,
    expected_channels: int | None = None,
    limits: ValidationLimits = DEFAULT_LIMITS,
    max_samples: int | None = None,
    max_channels: int | None = None,
) -> FloatArray:
    """Return a validated independent float64 window after shape checks."""
    source = np.asarray(window)
    sample_limit = limits.max_samples_per_window if max_samples is None else max_samples
    channel_limit = limits.max_channels if max_channels is None else max_channels
    _validate_window_metadata(
        source,
        expected_channels=expected_channels,
        max_samples=sample_limit,
        max_channels=channel_limit,
    )
    elements = int(source.shape[0]) * int(source.shape[1])
    _validate_aggregate(elements, limits)
    try:
        result = np.array(source, dtype=np.float64, copy=True)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValidationError("window must be convertible to float64") from error
    if not np.all(np.isfinite(result)):
        raise ValidationError("window contains non-finite values")
    return result


def validate_windows(
    windows: npt.ArrayLike | Sequence[npt.ArrayLike],
    *,
    expected_channels: int | None = None,
    limits: ValidationLimits = DEFAULT_LIMITS,
    max_windows: int | None = None,
) -> tuple[FloatArray, ...]:
    """Validate aggregate shape and memory before making float64 copies."""
    window_limit = limits.max_windows if max_windows is None else max_windows
    sources: tuple[npt.NDArray[np.generic], ...]
    if isinstance(windows, np.ndarray):
        source = windows
        if source.dtype.hasobject:
            raise ValidationError("object dtype window collections are forbidden")
        if source.ndim != 3:
            raise ValidationError("windows must have shape (windows, samples, channels)")
        count, samples, channels = (int(item) for item in source.shape)
        _validate_collection_shape(count, samples, channels, window_limit, limits)
        _validate_aggregate(count * samples * channels, limits)
        sources = tuple(source[index] for index in range(count))
    elif isinstance(windows, Sequence):
        count = len(windows)
        if count == 0:
            raise ValidationError("at least one window is required")
        if count > window_limit:
            raise ValidationError(f"collection exceeds maximum of {window_limit} windows")
        inspected: list[npt.NDArray[np.generic]] = []
        expected_shape: tuple[int, int] | None = None
        total_elements = 0
        for item in windows:
            source = np.asarray(item)
            _validate_window_metadata(
                source,
                expected_channels=expected_channels,
                max_samples=limits.max_samples_per_window,
                max_channels=limits.max_channels,
            )
            shape = (int(source.shape[0]), int(source.shape[1]))
            if expected_shape is None:
                expected_shape = shape
            elif shape != expected_shape:
                raise ValidationError("all windows must have the same shape")
            total_elements += shape[0] * shape[1]
            if total_elements > limits.max_total_elements:
                raise ValidationError("collection exceeds total element limit")
            inspected.append(source)
        _validate_aggregate(total_elements, limits)
        sources = tuple(inspected)
    else:
        raise ValidationError("windows must be a NumPy array or sized sequence")
    validated = tuple(
        validate_window(item, expected_channels=expected_channels, limits=limits)
        for item in sources
    )
    first_shape = validated[0].shape
    if any(item.shape != first_shape for item in validated[1:]):
        raise ValidationError("all windows must have the same shape")
    return validated


def validate_channel_names(names: Sequence[str], *, channel_count: int) -> tuple[str, ...]:
    """Validate stable, unique channel names."""
    result = tuple(names)
    if len(result) != channel_count:
        raise ValidationError("channel name count does not match channel count")
    if any(not isinstance(name, str) or not name.strip() for name in result):
        raise ValidationError("channel names must be non-empty strings")
    if len(set(result)) != len(result):
        raise ValidationError("channel names must be unique")
    return result


def validate_channel_units(units: Sequence[str], *, channel_count: int) -> tuple[str, ...]:
    """Validate explicit channel units without inferring them."""
    result = tuple(units)
    if len(result) != channel_count:
        raise ValidationError("channel unit count does not match channel count")
    if any(not isinstance(unit, str) or not unit.strip() for unit in result):
        raise ValidationError("channel units must be non-empty strings")
    return result


def validate_sampling_rate(sampling_rate_hz: float) -> float:
    """Validate and normalize a sampling rate."""
    try:
        result = float(sampling_rate_hz)
    except (TypeError, ValueError) as error:
        raise ValidationError("sampling rate must be a finite positive number") from error
    if not np.isfinite(result) or result <= 0.0:
        raise ValidationError("sampling rate must be a finite positive number")
    return result


def _validate_collection_shape(
    count: int,
    samples: int,
    channels: int,
    window_limit: int,
    limits: ValidationLimits,
) -> None:
    if count == 0:
        raise ValidationError("at least one window is required")
    if count > window_limit:
        raise ValidationError(f"collection exceeds maximum of {window_limit} windows")
    if samples < 4 or samples > limits.max_samples_per_window:
        raise ValidationError("samples per window are outside permitted limits")
    if channels < 2 or channels > limits.max_channels:
        raise ValidationError("channel count is outside permitted limits")


def _validate_window_metadata(
    source: npt.NDArray[np.generic],
    *,
    expected_channels: int | None,
    max_samples: int,
    max_channels: int,
) -> None:
    if source.dtype.hasobject:
        raise ValidationError("object dtype arrays are forbidden")
    if source.ndim != 2:
        raise ValidationError("window must have shape (samples, channels)")
    samples, channels = (int(item) for item in source.shape)
    if samples < 4:
        raise ValidationError("window must contain at least 4 samples")
    if samples > max_samples:
        raise ValidationError(f"window exceeds maximum of {max_samples} samples")
    if channels < 2:
        raise ValidationError("relational calculations require at least 2 channels")
    if channels > max_channels:
        raise ValidationError(f"window exceeds maximum of {max_channels} channels")
    if expected_channels is not None and channels != expected_channels:
        raise ValidationError(f"expected {expected_channels} channels, received {channels}")


def _validate_aggregate(elements: int, limits: ValidationLimits) -> None:
    if elements > limits.max_total_elements:
        raise ValidationError("collection exceeds total element limit")
    if elements * np.dtype(np.float64).itemsize > limits.max_total_bytes:
        raise ValidationError("collection exceeds total byte limit")

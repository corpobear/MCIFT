# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Offline deterministic adapter for user-supplied IMS recordings."""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from ..exceptions import ValidationError
from ..types import FloatArray
from ..validation import ValidationLimits, validate_sampling_rate, validate_window

DEFAULT_MAX_IMS_FILE_BYTES = 64 * 1024 * 1024
DEFAULT_IMS_LIMITS = ValidationLimits(
    max_total_elements=16_000_000,
    max_total_bytes=128 * 1024 * 1024,
    max_windows=1,
    max_samples_per_window=250_000,
    max_channels=256,
)


@dataclass(frozen=True)
class FileIdentity:
    """Filesystem identity used to detect changes during two-pass parsing."""

    size_bytes: int
    modification_time_ns: int
    device: int
    inode: int


@dataclass(frozen=True)
class IMSRecording:
    """Validated local recording with explicit acquisition metadata."""

    values: FloatArray
    sampling_rate_hz: float
    channel_count: int

    def __post_init__(self) -> None:
        values = np.array(self.values, dtype=np.float64, copy=True)
        values.setflags(write=False)
        object.__setattr__(self, "values", values)


def adapt_ims_array(
    values: npt.ArrayLike,
    *,
    expected_channel_count: int,
    sampling_rate_hz: float,
    validation_limits: ValidationLimits = DEFAULT_IMS_LIMITS,
) -> IMSRecording:
    """Validate an IMS-shaped samples-by-channels array without inferring labels."""
    _validate_expected_channels(expected_channel_count, validation_limits)
    sampling_rate = validate_sampling_rate(sampling_rate_hz)
    window = validate_window(
        values, expected_channels=expected_channel_count, limits=validation_limits
    )
    return IMSRecording(
        values=window,
        sampling_rate_hz=sampling_rate,
        channel_count=expected_channel_count,
    )


def load_ims_file(
    path: str | Path,
    *,
    expected_channel_count: int,
    sampling_rate_hz: float,
    max_file_bytes: int = DEFAULT_MAX_IMS_FILE_BYTES,
    validation_limits: ValidationLimits = DEFAULT_IMS_LIMITS,
) -> IMSRecording:
    """Parse one local whitespace-delimited IMS recording with bounded memory."""
    source = Path(path)
    _validate_expected_channels(expected_channel_count, validation_limits)
    sampling_rate = validate_sampling_rate(sampling_rate_hz)
    initial_identity = _file_identity(source, max_file_bytes=max_file_bytes)

    row_count = 0
    try:
        with source.open("r", encoding="utf-8", errors="strict", newline=None) as stream:
            for row_number, line in enumerate(stream, start=1):
                _parse_row(line, row_number, expected_channel_count)
                row_count = row_number
                _validate_parse_size(row_count, expected_channel_count, validation_limits)
    except UnicodeError as error:
        raise ValidationError("IMS recording is not valid UTF-8 text") from error
    if row_count < 4:
        raise ValidationError("IMS recording must contain at least 4 samples")
    if _file_identity(source, max_file_bytes=max_file_bytes) != initial_identity:
        raise ValidationError("IMS recording changed between parsing passes")

    values = np.empty((row_count, expected_channel_count), dtype=np.float64)
    filled = 0
    try:
        with source.open("r", encoding="utf-8", errors="strict", newline=None) as stream:
            for row_number, line in enumerate(stream, start=1):
                if row_number > row_count:
                    raise ValidationError("IMS recording changed between parsing passes")
                values[row_number - 1] = _parse_row(line, row_number, expected_channel_count)
                filled = row_number
    except UnicodeError as error:
        raise ValidationError("IMS recording is not valid UTF-8 text") from error
    if (
        filled != row_count
        or _file_identity(source, max_file_bytes=max_file_bytes) != initial_identity
    ):
        raise ValidationError("IMS recording changed between parsing passes")
    return IMSRecording(
        values=validate_window(
            values,
            expected_channels=expected_channel_count,
            limits=validation_limits,
        ),
        sampling_rate_hz=sampling_rate,
        channel_count=expected_channel_count,
    )


def _file_identity(path: Path, *, max_file_bytes: int) -> FileIdentity:
    if type(max_file_bytes) is not int or max_file_bytes <= 0:
        raise ValidationError("IMS file-size limit must be a positive integer")
    try:
        metadata = path.lstat()
    except OSError as error:
        raise ValidationError("IMS recording is unavailable") from error
    if stat.S_ISLNK(metadata.st_mode):
        raise ValidationError("IMS recording must not be a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise ValidationError("IMS recording must be a regular file")
    if metadata.st_size > max_file_bytes:
        raise ValidationError("IMS recording exceeds file-size limit")
    return FileIdentity(
        size_bytes=metadata.st_size,
        modification_time_ns=metadata.st_mtime_ns,
        device=metadata.st_dev,
        inode=metadata.st_ino,
    )


def _parse_row(line: str, row_number: int, expected_channel_count: int) -> tuple[float, ...]:
    fields = line.split()
    if len(fields) != expected_channel_count:
        raise ValidationError(
            f"malformed IMS row {row_number}: expected {expected_channel_count} "
            f"columns, received {len(fields)}"
        )
    try:
        values = tuple(float(field) for field in fields)
    except ValueError as error:
        raise ValidationError(f"malformed IMS row {row_number}: non-numeric value") from error
    if not all(np.isfinite(value) for value in values):
        raise ValidationError(f"malformed IMS row {row_number}: non-finite value")
    return values


def _validate_parse_size(rows: int, channels: int, limits: ValidationLimits) -> None:
    if rows > limits.max_samples_per_window:
        raise ValidationError("IMS recording exceeds sample limit")
    elements = rows * channels
    if elements > limits.max_total_elements:
        raise ValidationError("IMS recording exceeds total element limit")
    if elements * np.dtype(np.float64).itemsize > limits.max_total_bytes:
        raise ValidationError("IMS recording exceeds total byte limit")


def _validate_expected_channels(expected_channel_count: int, limits: ValidationLimits) -> None:
    if type(expected_channel_count) is not int:
        raise ValidationError("expected channel count must be an integer")
    if expected_channel_count < 2 or expected_channel_count > limits.max_channels:
        raise ValidationError(f"expected channel count must be between 2 and {limits.max_channels}")

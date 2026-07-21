# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import numpy as np
import pytest

from mcift import MCIFTMonitor
from mcift.adapters.vibration import fit_vibration_scales
from mcift.calibration import fit_channel_scales
from mcift.exceptions import ValidationError
from mcift.profiles import TELEMETRY_PROFILE_ID, VIBRATION_PROFILE_ID


def _reference() -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.normal(size=(8, 32, 3)) + np.array([2.0, -1.0, 0.5])


def test_telemetry_profile_preserves_stacked_robust_scaling() -> None:
    windows = _reference()
    monitor = MCIFTMonitor.fit(
        windows,
        sampling_rate_hz=100.0,
        channel_names=["a", "b", "c"],
        profile=TELEMETRY_PROFILE_ID,
    )
    expected, _ = fit_channel_scales(tuple(windows))

    assert monitor.processing_profile == TELEMETRY_PROFILE_ID
    np.testing.assert_array_equal(monitor.channel_scales, expected)


def test_vibration_profile_uses_median_centered_window_rms() -> None:
    windows = _reference()
    monitor = MCIFTMonitor.fit(
        windows,
        sampling_rate_hz=20_000.0,
        channel_names=["a", "b", "c"],
        profile=VIBRATION_PROFILE_ID,
    )
    expected, _ = fit_vibration_scales(tuple(windows))

    assert monitor.processing_profile == VIBRATION_PROFILE_ID
    np.testing.assert_array_equal(monitor.channel_scales, expected)


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown processing profile"):
        MCIFTMonitor.fit(
            _reference(),
            sampling_rate_hz=100.0,
            channel_names=["a", "b", "c"],
            profile="mcift.exchange.future.v9",
        )

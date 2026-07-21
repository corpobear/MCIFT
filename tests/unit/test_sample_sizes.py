# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import numpy as np
import pytest

from mcift import MCIFTMonitor
from mcift.exceptions import ValidationError


def test_reference_requires_eight_windows_by_default() -> None:
    windows = np.random.default_rng(1).normal(size=(7, 16, 2))

    with pytest.raises(ValidationError, match="at least 8 reference windows"):
        MCIFTMonitor.fit(windows, sampling_rate_hz=100.0, channel_names=["a", "b"])


def test_small_reference_override_is_visible_everywhere() -> None:
    windows = np.random.default_rng(2).normal(size=(3, 16, 2))
    monitor = MCIFTMonitor.fit(
        windows,
        sampling_rate_hz=100.0,
        channel_names=["a", "b"],
        allow_small_sample=True,
    )
    result = monitor.evaluate(windows[0])

    assert any("small-sample" in item for item in monitor.warnings)
    assert any("small_sample" in item for item in monitor.diagnostics)
    assert any("small-sample" in item for item in result.warnings)


def test_calibration_requires_twenty_windows_by_default() -> None:
    rng = np.random.default_rng(3)
    monitor = MCIFTMonitor.fit(
        rng.normal(size=(8, 16, 2)), sampling_rate_hz=100.0, channel_names=["a", "b"]
    )

    with pytest.raises(ValidationError, match="at least 20 calibration windows"):
        monitor.calibrate(rng.normal(size=(19, 16, 2)))

    overridden = monitor.calibrate(
        rng.normal(size=(4, 16, 2)), allow_small_sample=True
    )
    assert any("small-sample" in item for item in overridden.warnings)

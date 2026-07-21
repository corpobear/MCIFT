# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import json
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

from mcift.observables import compute_observables

FFT_RTOL = 5e-12
FFT_ATOL = 1e-12


def _window(name: str, samples: int, sampling_rate_hz: float) -> np.ndarray:
    time = np.arange(samples, dtype=np.float64) / sampling_rate_hz
    if name == "even_16_fs64":
        return np.column_stack(
            (
                np.sin(2.0 * np.pi * 8.0 * time),
                0.5 * np.sin(2.0 * np.pi * 8.0 * time + 0.3),
                np.cos(2.0 * np.pi * 12.0 * time),
            )
        )
    if name == "odd_15_fs75":
        return np.column_stack(
            (
                np.sin(2.0 * np.pi * 10.0 * time),
                0.75 * np.sin(2.0 * np.pi * 10.0 * time - 0.4),
                0.4 * np.cos(2.0 * np.pi * 15.0 * time)
                + 0.2 * np.cos(2.0 * np.pi * 10.0 * time + 0.7),
            )
        )
    raise AssertionError(f"unknown frozen FFT fixture {name}")


def _cases() -> list[dict[str, Any]]:
    fixture = Path(__file__).with_name("fft_observables_v1.json")
    payload = cast(dict[str, Any], json.loads(fixture.read_text(encoding="utf-8")))
    assert payload["profile"] == "mcift.observables.fft-golden.v1"
    return cast(list[dict[str, Any]], payload["cases"])


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["name"]))
def test_fft_observables_cover_even_odd_lengths_and_sampling_rates(
    case: dict[str, Any],
) -> None:
    window = _window(str(case["name"]), int(case["samples"]), float(case["sampling_rate_hz"]))
    result = compute_observables(
        window,
        np.asarray(case["channel_scales"], dtype=np.float64),
        float(case["sampling_rate_hz"]),
    )

    np.testing.assert_allclose(result.information, case["information"], rtol=1e-13)
    np.testing.assert_allclose(result.omega, case["omega"], rtol=FFT_RTOL, atol=FFT_ATOL)
    circular_delta = np.angle(
        np.exp(1j * (result.phase - np.asarray(case["phase"], dtype=np.float64)))
    )
    np.testing.assert_allclose(circular_delta, 0.0, rtol=0.0, atol=FFT_ATOL)
    assert result.shared_bin == case["shared_bin"]

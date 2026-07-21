# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import numpy as np
import pytest

from mcift.exceptions import ValidationError
from mcift.validation import validate_channel_names, validate_window


def test_validate_window_returns_float64_without_mutating_input() -> None:
    source = np.arange(12, dtype=np.float32).reshape(6, 2)

    result = validate_window(source, expected_channels=2)

    assert result.dtype == np.float64
    np.testing.assert_array_equal(source, np.arange(12, dtype=np.float32).reshape(6, 2))


@pytest.mark.parametrize(
    "window",
    [
        np.ones((3, 2)),
        np.ones((4, 1)),
        np.array([[1.0, np.nan], [1.0, 2.0], [2.0, 3.0], [3.0, 4.0]]),
        np.array([[object(), object()]], dtype=object),
    ],
)
def test_validate_window_rejects_invalid_arrays(window: np.ndarray) -> None:
    with pytest.raises(ValidationError):
        validate_window(window)


def test_validate_channel_names_rejects_duplicates() -> None:
    with pytest.raises(ValidationError, match="unique"):
        validate_channel_names(["sensor", "sensor"], channel_count=2)

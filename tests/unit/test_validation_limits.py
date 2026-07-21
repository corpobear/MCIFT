# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import numpy as np
import pytest

from mcift.exceptions import ValidationError
from mcift.validation import ValidationLimits, validate_windows


def test_aggregate_limit_fails_before_float64_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    source = np.broadcast_to(np.zeros(1, dtype=np.float32), (100, 100, 2))
    limits = ValidationLimits(max_total_elements=100, max_total_bytes=800)

    def forbidden_copy(*args: object, **kwargs: object) -> np.ndarray:
        raise AssertionError("float64 copy must not be attempted")

    monkeypatch.setattr("mcift.validation.np.array", forbidden_copy)
    with pytest.raises(ValidationError, match="total element limit"):
        validate_windows(source, limits=limits)


def test_total_byte_limit_is_enforced() -> None:
    source = np.ones((8, 16, 2), dtype=np.float32)
    with pytest.raises(ValidationError, match="total byte limit"):
        validate_windows(source, limits=ValidationLimits(max_total_bytes=128))

# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from mcift.gates import persistence_gate, robust_progression_slope


def test_persistence_requires_current_and_three_of_five() -> None:
    assert persistence_gate([False, True, True, False, True]).passed
    assert not persistence_gate([True, True, True, False]).passed
    assert not persistence_gate([True, True]).passed


def test_robust_progression_slope_uses_pairwise_median() -> None:
    assert robust_progression_slope([1.0, 2.0, 100.0]) == pytest.approx(49.5)

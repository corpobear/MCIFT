# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import numpy as np

from mcift.scoring import (
    edge_residuals,
    global_exchange_score,
    node_incident_damage_ratio,
)


def test_global_score_is_rms_over_unique_edges() -> None:
    reference = np.zeros((3, 3), dtype=np.float64)
    current = np.array([[0.0, 1.0, 2.0], [1.0, 0.0, 2.0], [2.0, 2.0, 0.0]])

    score = global_exchange_score(current, reference)

    assert score == np.sqrt(3.0)


def test_node_incident_damage_ratio_uses_unique_edge_denominator() -> None:
    current = np.array([[0.0, 2.0, 0.0], [2.0, 0.0, 1.0], [0.0, 1.0, 0.0]])
    residuals = edge_residuals(current, np.zeros((3, 3)), np.ones((3, 3)))

    ratio = node_incident_damage_ratio(residuals)

    np.testing.assert_allclose(ratio, np.array([2.0 / 3.0, 1.0, 1.0 / 3.0]))
    assert ratio.sum() == 2.0

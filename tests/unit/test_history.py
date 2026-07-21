# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import numpy as np
import pytest

from mcift.exceptions import ValidationError
from mcift.gates import (
    directional_consistency_gate,
    persistence_gate,
    progression_gate,
    robust_progression_slope,
)
from mcift.history import HistoryEntry, MCIFTHistory


def _entry(
    index: int,
    *,
    global_positive: bool = False,
    local_positive: bool = True,
    edge: tuple[int, int] | None = (0, 1),
    sign: int = 1,
    score: float | None = None,
) -> HistoryEntry:
    return HistoryEntry(
        global_score=float(index if score is None else score),
        global_positive=global_positive,
        local_score=float(index + 1),
        local_positive=local_positive,
        base_positive=global_positive or local_positive,
        top_edge=edge,
        relationship_change_sign=sign,
        model_version="0.1.0a1",
        processing_profile="mcift.exchange.telemetry.v1",
        gate_profile="mcift.gates.exchange-screening.v1",
        channel_count=3,
        sequence_index=index,
    )


def test_history_append_is_immutable_bounded_and_ordered() -> None:
    history = MCIFTHistory(maxlen=3)
    updated = history
    for index in range(5):
        updated = updated.append(_entry(index))

    assert history.entries == ()
    assert [item.sequence_index for item in updated.entries] == [2, 3, 4]

    with pytest.raises(ValidationError, match="strictly increasing"):
        updated.append(_entry(4))


def test_persistence_uses_base_positive_and_reports_availability() -> None:
    local_only = [_entry(index).base_positive for index in range(3)]
    result = persistence_gate(local_only)

    assert result.available
    assert result.passed
    assert not persistence_gate([True, True]).available


def test_directional_consistency_uses_only_eligible_local_evidence() -> None:
    entries = [
        _entry(0, global_positive=True, local_positive=False, edge=None, sign=0),
        _entry(1, edge=(0, 1)),
        _entry(2, edge=(0, 2)),
        _entry(3, edge=(0, 1)),
    ]
    result = directional_consistency_gate(entries)

    assert result.available
    assert result.passed
    assert result.evidence["eligible_sequence_indices"] == (1, 2, 3)
    assert result.evidence["rejected_entries"] == (
        {
            "sequence_index": 0,
            "reasons": ("local_not_positive", "missing_top_edge", "zero_direction"),
        },
    )


@pytest.mark.parametrize(
    ("entries", "available", "passed"),
    [
        ([_entry(0), _entry(1)], False, False),
        ([_entry(0), _entry(1), _entry(2, sign=-1)], True, False),
        ([_entry(0), _entry(1), _entry(2, sign=0)], False, False),
        ([_entry(0, edge=(0, 1)), _entry(1, edge=(1, 2)), _entry(2, edge=(0, 2))], True, True),
    ],
)
def test_directional_eligibility_and_consistency(
    entries: list[HistoryEntry], available: bool, passed: bool
) -> None:
    result = directional_consistency_gate(entries)
    assert result.available is available
    assert result.passed is passed


def test_directional_consistency_does_not_reuse_stale_local_evidence() -> None:
    entries = [_entry(index) for index in range(3)]
    entries.extend(_entry(index, local_positive=False, edge=None, sign=0) for index in range(3, 8))

    result = directional_consistency_gate(entries)

    assert not result.available
    assert result.evidence["recent_sequence_indices"] == (3, 4, 5, 6, 7)


def test_robust_progression_slope_supports_irregular_time() -> None:
    assert robust_progression_slope([1.0, 3.0, 7.0], times=[0.0, 1.0, 3.0]) == pytest.approx(2.0)


@pytest.mark.parametrize(
    ("values", "times", "match"),
    [
        ([1.0, np.nan], None, "finite"),
        ([[1.0, 2.0]], None, "one-dimensional"),
        ([1.0, 2.0], [0.0], "same length"),
        ([1.0, 2.0], [0.0, 0.0], "strictly increasing"),
        ([1.0, 2.0], [0.0, np.inf], "finite"),
    ],
)
def test_robust_progression_rejects_invalid_inputs(
    values: object, times: object, match: str
) -> None:
    with pytest.raises(ValidationError, match=match):
        robust_progression_slope(values, times=times)


def test_progression_availability_requires_threshold_and_history() -> None:
    assert not progression_gate([1.0, 2.0, 3.0], threshold=None).available
    assert not progression_gate([1.0, 2.0], threshold=0.1).available
    result = progression_gate([1.0, 1.2, 1.4, 1.8], threshold=0.1)
    assert result.available
    assert result.passed

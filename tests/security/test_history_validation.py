# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

from dataclasses import replace
from typing import Any, cast

import numpy as np
import pytest

from mcift import MCIFTHistory, MCIFTMonitor
from mcift.exceptions import ValidationError
from mcift.history import HistoryEntry


def _entry(**changes: object) -> HistoryEntry:
    values: dict[str, object] = {
        "global_score": 1.0,
        "global_positive": True,
        "local_score": 2.0,
        "local_positive": False,
        "base_positive": True,
        "top_edge": None,
        "relationship_change_sign": 0,
        "model_version": "0.1.0a1",
        "processing_profile": "mcift.exchange.telemetry.v1",
        "gate_profile": "mcift.gates.exchange-screening.v1",
        "channel_count": 3,
        "sequence_index": 0,
    }
    values.update(changes)
    return HistoryEntry(**cast(Any, values))


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"global_score": np.nan}, "finite"),
        ({"local_score": np.inf}, "finite"),
        ({"relationship_change_sign": 2}, "-1, 0, or 1"),
        ({"top_edge": (-1, 1), "local_positive": True, "base_positive": True}, "non-negative"),
        ({"top_edge": (0, 3), "local_positive": True, "base_positive": True}, "channel count"),
        ({"top_edge": (1, 1), "local_positive": True, "base_positive": True}, "distinct"),
        ({"top_edge": (2, 1), "local_positive": True, "base_positive": True}, "ordered"),
        ({"global_positive": 1}, "actual booleans"),
        ({"base_positive": False}, "logical OR"),
    ],
)
def test_history_entry_rejects_untrusted_values(changes: dict[str, object], match: str) -> None:
    with pytest.raises(ValidationError, match=match):
        _entry(**changes)


def test_history_rejects_duplicate_decreasing_and_oversized_indices() -> None:
    first = _entry(sequence_index=1)
    duplicate = replace(first, sequence_index=1)
    decreasing = replace(first, sequence_index=0)

    with pytest.raises(ValidationError, match="strictly increasing"):
        MCIFTHistory(entries=(first, duplicate))
    with pytest.raises(ValidationError, match="strictly increasing"):
        MCIFTHistory(entries=(first, decreasing))
    with pytest.raises(ValidationError, match="maxlen"):
        MCIFTHistory(maxlen=1, entries=(first, replace(first, sequence_index=2)))


def test_monitor_rejects_history_identity_and_configuration_mismatches() -> None:
    rng = np.random.default_rng(810)
    window = rng.normal(size=(16, 3))
    monitor = MCIFTMonitor.fit(
        rng.normal(size=(8, 16, 3)), sampling_rate_hz=100.0, channel_names=["a", "b", "c"]
    )

    mismatches = [
        _entry(model_version="other"),
        _entry(processing_profile="mcift.exchange.vibration.v1"),
        _entry(gate_profile="other"),
        _entry(channel_count=4),
    ]
    for entry in mismatches:
        with pytest.raises(ValidationError, match="history"):
            monitor.evaluate_with_history(window, history=MCIFTHistory(entries=(entry,)))

    _, bound = monitor.evaluate_with_history(window, history=MCIFTHistory())
    different = MCIFTMonitor.fit(
        rng.normal(size=(8, 16, 3)), sampling_rate_hz=100.0, channel_names=["a", "b", "c"]
    )
    with pytest.raises(ValidationError, match="configured monitor"):
        different.evaluate_with_history(window, history=bound)

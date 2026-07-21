# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

from dataclasses import replace

import numpy as np

from mcift import EvaluationResult, MCIFTHistory, MCIFTMonitor
from mcift.profiles import GATE_PROFILE_ID


def _monitor() -> tuple[MCIFTMonitor, np.ndarray]:
    rng = np.random.default_rng(91)
    reference = rng.normal(size=(8, 32, 3))
    calibration = rng.normal(size=(20, 32, 3))
    current = rng.normal(size=(32, 3))
    monitor = MCIFTMonitor.fit(
        reference, sampling_rate_hz=100.0, channel_names=["a", "b", "c"]
    ).calibrate(calibration, sequence_order="unordered")
    return monitor, current


def _evaluate_three(
    monitor: MCIFTMonitor, current: np.ndarray
) -> tuple[EvaluationResult, MCIFTHistory]:
    history = MCIFTHistory(maxlen=32)
    evaluation = None
    for sequence_index in range(3):
        evaluation, history = monitor.evaluate_with_history(
            current,
            history=history,
            sequence_index=sequence_index,
        )
    assert evaluation is not None
    return evaluation, history


def test_evaluate_with_history_returns_new_explicit_history() -> None:
    monitor, current = _monitor()
    history = MCIFTHistory(maxlen=32)

    evaluation, updated = monitor.evaluate_with_history(current, history=history)

    assert history.entries == ()
    assert len(updated.entries) == 1
    assert evaluation.gate_profile_version == GATE_PROFILE_ID
    assert {gate.name for gate in evaluation.gate_results} == {
        "global_deformation",
        "local_relationship_damage",
        "persistence",
        "directional_consistency",
        "robust_progression",
    }


def test_persistent_local_only_anomaly_can_warn() -> None:
    monitor, current = _monitor()
    local_only = replace(
        monitor,
        global_threshold=1e100,
        local_edge_threshold=0.0,
        progression_slope_threshold=None,
        calibration_sequence_mode="unordered",
    )

    evaluation, history = _evaluate_three(local_only, current)

    assert all(not entry.global_positive and entry.local_positive for entry in history.entries)
    assert evaluation.final_decision == "persistent_exchange_warning"
    assert evaluation.confidence_evidence["persistent_positive"] is True
    assert evaluation.confidence_evidence["corroborating_gate_names"] == (
        "directional_consistency",
    )


def test_persistent_global_only_anomaly_has_no_fake_directional_evidence() -> None:
    monitor, current = _monitor()
    global_only = replace(
        monitor,
        global_threshold=0.0,
        local_edge_threshold=1e100,
        progression_slope_threshold=None,
        calibration_sequence_mode="unordered",
    )

    evaluation, history = _evaluate_three(global_only, current)

    assert all(entry.global_positive and not entry.local_positive for entry in history.entries)
    directional = next(
        gate for gate in evaluation.gate_results if gate.name == "directional_consistency"
    )
    assert not directional.available
    assert evaluation.final_decision == "screening_positive"


def test_mixed_global_and_local_anomaly_does_not_double_count_base_evidence() -> None:
    monitor, current = _monitor()
    mixed = replace(
        monitor,
        global_threshold=0.0,
        local_edge_threshold=0.0,
        progression_slope_threshold=None,
        calibration_sequence_mode="unordered",
    )

    evaluation, history = _evaluate_three(mixed, current)

    assert all(entry.global_positive and entry.local_positive for entry in history.entries)
    assert evaluation.final_decision == "persistent_exchange_warning"
    assert evaluation.confidence_evidence["base_positive"] is True
    assert evaluation.confidence_evidence["passed_gate_count"] == 4
    assert "robust_progression" not in evaluation.confidence_evidence["available_gate_names"]
    assert evaluation.confidence_evidence["available_gate_count"] == 4

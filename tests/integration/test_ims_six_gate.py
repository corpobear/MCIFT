# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

from dataclasses import replace

import numpy as np
import pytest

from mcift import MCIFTHistory, MCIFTMonitor
from mcift.exceptions import ValidationError
from mcift.profiles import (
    GATE_PROFILE_ID,
    IMS_SIX_GATE_PROFILE_ID,
    VIBRATION_PROFILE_ID,
)
from mcift.vibration_features import FEATURE_NAMES, compute_vibration_features


def _data() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(6006)
    return (
        rng.normal(size=(8, 32, 3)),
        rng.normal(size=(20, 32, 3)),
        rng.normal(size=(32, 3)),
    )


def _fit_six(*, calibrated: bool = True) -> tuple[MCIFTMonitor, np.ndarray, np.ndarray]:
    reference, calibration, current = _data()
    monitor = MCIFTMonitor.fit(
        reference,
        sampling_rate_hz=20_000.0,
        channel_names=["bearing_1", "bearing_2", "bearing_3"],
        profile=VIBRATION_PROFILE_ID,
        gate_profile=IMS_SIX_GATE_PROFILE_ID,
    )
    if calibrated:
        monitor = monitor.calibrate(calibration, sequence_order="chronological")
    return monitor, calibration, current


def _gate(result: object, name: str) -> object:
    return next(gate for gate in result.gate_results if gate.name == name)  # type: ignore[attr-defined]


def _thresholds_for(
    monitor: MCIFTMonitor,
    current: np.ndarray,
    triggers: dict[str, tuple[int, ...]],
) -> MCIFTMonitor:
    values = compute_vibration_features(
        current, numerical_floor=monitor.conventional_numerical_floor
    )
    thresholds: dict[str, np.ndarray] = {}
    for name in FEATURE_NAMES:
        feature = getattr(values, name)
        upper = feature + np.maximum(1.0, np.abs(feature))
        for channel in triggers.get(name, ()):
            upper[channel] = feature[channel] - max(1e-9, abs(feature[channel]) * 0.5)
        thresholds[name] = upper
    return replace(
        monitor,
        conventional_rms_thresholds=thresholds["centered_rms"],
        conventional_excess_kurtosis_thresholds=thresholds["excess_kurtosis"],
        conventional_crest_factor_thresholds=thresholds["crest_factor"],
    )


def test_six_gate_requires_vibration_and_unknown_gate_profiles_fail() -> None:
    reference, _, _ = _data()
    with pytest.raises(ValidationError, match="requires the vibration"):
        MCIFTMonitor.fit(
            reference,
            sampling_rate_hz=100.0,
            channel_names=["a", "b", "c"],
            gate_profile=IMS_SIX_GATE_PROFILE_ID,
        )
    with pytest.raises(ValidationError, match="unknown gate profile"):
        MCIFTMonitor.fit(
            reference,
            sampling_rate_hz=100.0,
            channel_names=["a", "b", "c"],
            gate_profile="mcift.gates.unknown.v9",
        )


def test_calibration_uses_only_calibration_features_and_profile_quantile() -> None:
    monitor, calibration, current = _fit_six()
    expected_rows = [compute_vibration_features(window) for window in calibration]
    for name, actual in (
        ("centered_rms", monitor.conventional_rms_thresholds),
        ("excess_kurtosis", monitor.conventional_excess_kurtosis_thresholds),
        ("crest_factor", monitor.conventional_crest_factor_thresholds),
    ):
        assert actual is not None
        values = np.asarray([getattr(row, name) for row in expected_rows])
        expected = np.quantile(values, 0.995, axis=0, method="linear")
        np.testing.assert_allclose(actual, expected)
        assert actual.shape == (3,)
        assert actual.dtype == np.float64
        assert not actual.flags.writeable
    before = tuple(
        array.copy()
        for array in (
            monitor.conventional_rms_thresholds,
            monitor.conventional_excess_kurtosis_thresholds,
            monitor.conventional_crest_factor_thresholds,
        )
        if array is not None
    )
    monitor.evaluate(current * 1e6)
    after = (
        monitor.conventional_rms_thresholds,
        monitor.conventional_excess_kurtosis_thresholds,
        monitor.conventional_crest_factor_thresholds,
    )
    for expected, actual in zip(before, after, strict=True):
        assert actual is not None
        np.testing.assert_array_equal(actual, expected)


def test_six_gate_calibration_sample_rules_and_override_warnings() -> None:
    reference, calibration, _ = _data()
    monitor = MCIFTMonitor.fit(
        reference,
        sampling_rate_hz=20_000.0,
        channel_names=["a", "b", "c"],
        profile=VIBRATION_PROFILE_ID,
        gate_profile=IMS_SIX_GATE_PROFILE_ID,
    )
    with pytest.raises(ValidationError, match="at least 20 calibration windows"):
        monitor.calibrate(calibration[:4])
    overridden = monitor.calibrate(
        calibration[:4], quantile=1.0, allow_small_sample=True
    )
    assert any("small-sample" in warning for warning in overridden.warnings)
    expected = np.max(
        np.asarray([compute_vibration_features(window).centered_rms for window in calibration[:4]]),
        axis=0,
    )
    np.testing.assert_allclose(overridden.conventional_rms_thresholds, expected)


@pytest.mark.parametrize(
    "feature_name",
    ["centered_rms", "excess_kurtosis", "crest_factor"],
)
def test_each_approved_feature_can_trigger_g6(feature_name: str) -> None:
    monitor, _, current = _fit_six()
    monitor = _thresholds_for(monitor, current, {feature_name: (1,)})
    result = monitor.evaluate(current)
    gate = _gate(result, "conventional_vibration_agreement")

    assert gate.available and gate.passed
    assert gate.evidence["triggered_features"] == (feature_name,)
    assert gate.evidence["triggered_channels"] == ("bearing_2",)
    assert gate.evidence["comparison_rule"] == (
        "value_strictly_greater_than_healthy_upper_threshold"
    )


def test_g6_reports_multi_feature_and_multi_channel_evidence() -> None:
    monitor, _, current = _fit_six()
    monitor = _thresholds_for(
        monitor,
        current,
        {"centered_rms": (0, 1), "excess_kurtosis": (0,), "crest_factor": (0,)},
    )
    gate = _gate(monitor.evaluate(current), "conventional_vibration_agreement")

    assert gate.evidence["triggered_feature_count"] == 3
    assert gate.evidence["triggered_channel_count"] == 2
    assert gate.evidence["same_channel_multi_feature_agreement"] is True


def test_g6_no_trigger_and_uncalibrated_availability() -> None:
    monitor, _, current = _fit_six()
    quiet = _thresholds_for(monitor, current, {})
    quiet_gate = _gate(quiet.evaluate(current), "conventional_vibration_agreement")
    assert quiet_gate.available and not quiet_gate.passed

    exact = compute_vibration_features(current)
    equal = replace(
        monitor,
        conventional_rms_thresholds=exact.centered_rms,
        conventional_excess_kurtosis_thresholds=exact.excess_kurtosis,
        conventional_crest_factor_thresholds=exact.crest_factor,
    )
    equal_gate = _gate(equal.evaluate(current), "conventional_vibration_agreement")
    assert equal_gate.available and not equal_gate.passed

    uncalibrated, _, current = _fit_six(calibrated=False)
    result = uncalibrated.evaluate(current)
    gate = _gate(result, "conventional_vibration_agreement")
    assert not gate.available and not gate.passed
    assert result.conventional_vibration is not None
    assert all(feature.thresholds is None for feature in result.conventional_vibration.features)


def test_normal_evaluate_reports_six_gates_with_history_unavailable() -> None:
    monitor, _, current = _fit_six()
    result = monitor.evaluate(current)

    assert [gate.name for gate in result.gate_results] == [
        "global_deformation",
        "local_relationship_damage",
        "persistence",
        "directional_consistency",
        "robust_progression",
        "conventional_vibration_agreement",
    ]
    assert all(not _gate(result, name).available for name in (
        "persistence",
        "directional_consistency",
        "robust_progression",
    ))
    assert result.confidence_evidence["high_confidence_ims_warning"] is None
    explained = monitor.explain(result)
    assert explained["conventional_vibration"] is not None
    assert explained["confidence_evidence"]["decision_profile"] == IMS_SIX_GATE_PROFILE_ID


def test_high_confidence_requires_persistence_g6_and_five_passes() -> None:
    monitor, _, current = _fit_six()
    monitor = _thresholds_for(monitor, current, {"centered_rms": (0,)})
    monitor = replace(monitor, global_threshold=0.0, local_edge_threshold=0.0)
    history = MCIFTHistory()
    result = None
    for index in range(3):
        result, history = monitor.evaluate_with_history(
            current, history=history, sequence_index=index
        )
    assert result is not None
    assert result.final_decision == "high_confidence_ims_warning"
    evidence = result.confidence_evidence
    assert evidence["screening_positive"] is True
    assert evidence["persistent_mcift_warning"] is True
    assert evidence["high_confidence_ims_warning"] is True
    assert evidence["passed_gate_count"] >= 5
    assert evidence["missing_mandatory_gate_names"] == ()


def test_persistent_warning_does_not_require_g6_to_pass() -> None:
    monitor, _, current = _fit_six()
    monitor = _thresholds_for(monitor, current, {})
    monitor = replace(monitor, global_threshold=0.0, local_edge_threshold=0.0)
    history = MCIFTHistory()
    result = None
    for index in range(3):
        result, history = monitor.evaluate_with_history(
            current, history=history, sequence_index=index
        )
    assert result is not None
    assert result.final_decision == "persistent_mcift_warning"
    assert result.confidence_evidence["persistent_mcift_warning"] is True
    assert result.confidence_evidence["high_confidence_ims_warning"] is False


def test_high_confidence_is_unavailable_without_g6_or_persistence() -> None:
    fitted, _, current = _fit_six(calibrated=False)
    fitted = replace(fitted, global_threshold=0.0, local_edge_threshold=0.0)
    history = MCIFTHistory()
    result = None
    for index in range(3):
        result, history = fitted.evaluate_with_history(
            current, history=history, sequence_index=index
        )
    assert result is not None
    assert result.confidence_evidence["high_confidence_ims_warning"] is None
    assert "conventional_vibration_agreement" in result.confidence_evidence[
        "missing_mandatory_gate_names"
    ]

    calibrated, _, current = _fit_six()
    single = calibrated.evaluate(current)
    assert single.confidence_evidence["high_confidence_ims_warning"] is None
    assert "persistence" in single.confidence_evidence["missing_mandatory_gate_names"]


def test_existing_five_gate_profile_behavior_remains_unchanged() -> None:
    reference, calibration, current = _data()
    default = MCIFTMonitor.fit(
        reference, sampling_rate_hz=100.0, channel_names=["a", "b", "c"]
    ).calibrate(calibration)
    explicit = MCIFTMonitor.fit(
        reference,
        sampling_rate_hz=100.0,
        channel_names=["a", "b", "c"],
        gate_profile=GATE_PROFILE_ID,
    ).calibrate(calibration)
    default_result = default.evaluate(current)
    explicit_result = explicit.evaluate(current)

    assert default_result.gate_profile_version == GATE_PROFILE_ID
    assert explicit_result.conventional_vibration is None
    assert len(explicit_result.gate_results) == 5
    np.testing.assert_array_equal(default_result.exchange_matrix, explicit_result.exchange_matrix)
    assert default_result.final_decision == explicit_result.final_decision

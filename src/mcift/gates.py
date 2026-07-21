# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Deterministic structured gate primitives."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .exceptions import ValidationError
from .history import HistoryEntry
from .types import ConventionalVibrationResult, FloatArray, GateResult


def threshold_gate(name: str, value: float, threshold: float | None) -> GateResult:
    """Create a structured strict-threshold gate result."""
    available = threshold is not None
    return GateResult(
        name=name,
        available=available,
        passed=False if threshold is None else value > threshold,
        value=float(value),
        threshold=threshold,
        evidence={"calibrated": available, "comparison": "strictly_greater"},
    )


def persistence_gate(positives: Sequence[bool]) -> GateResult:
    """Apply the current-positive and three-of-most-recent-five rule."""
    if any(type(item) is not bool for item in positives):
        raise ValidationError("persistence evidence must contain booleans")
    recent = tuple(positives[-5:])
    available = len(recent) >= 3
    evidence: dict[str, object] = {
        "history_length": len(recent),
        "current_positive": bool(recent and recent[-1]),
    }
    if not available:
        evidence["reason"] = "insufficient_history"
    return GateResult(
        name="persistence",
        available=available,
        passed=bool(available and recent[-1] and sum(recent) >= 3),
        value=sum(recent),
        threshold=3,
        evidence=evidence,
    )


def robust_progression_slope(
    values: Sequence[float] | FloatArray, *, times: Sequence[float] | FloatArray | None = None
) -> float:
    """Return the median of pairwise slopes over validated sequence coordinates."""
    try:
        data = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise ValidationError("progression values must be numeric") from error
    if data.ndim != 1:
        raise ValidationError("progression values must be one-dimensional")
    if not np.all(np.isfinite(data)):
        raise ValidationError("progression values must be finite")
    if data.size < 2:
        return 0.0
    if times is None:
        coordinates = np.arange(data.size, dtype=np.float64)
    else:
        try:
            coordinates = np.asarray(times, dtype=np.float64)
        except (TypeError, ValueError) as error:
            raise ValidationError("progression times must be numeric") from error
        if coordinates.ndim != 1:
            raise ValidationError("progression times must be one-dimensional")
        if coordinates.size != data.size:
            raise ValidationError("progression values and times must have the same length")
        if not np.all(np.isfinite(coordinates)):
            raise ValidationError("progression times must be finite")
        if np.any(np.diff(coordinates) <= 0.0):
            raise ValidationError("progression times must be strictly increasing")
    slopes = [
        (data[second] - data[first]) / (coordinates[second] - coordinates[first])
        for first in range(data.size)
        for second in range(first + 1, data.size)
    ]
    return float(np.median(np.asarray(slopes, dtype=np.float64)))


def directional_consistency_gate(entries: Sequence[HistoryEntry]) -> GateResult:
    """Require three eligible local-positive edges with a consistent direction."""
    eligible: list[HistoryEntry] = []
    rejected: list[dict[str, object]] = []
    recent_entries = entries[-5:]
    for entry in recent_entries:
        reasons: list[str] = []
        if not entry.local_positive:
            reasons.append("local_not_positive")
        if entry.top_edge is None:
            reasons.append("missing_top_edge")
        if entry.relationship_change_sign == 0:
            reasons.append("zero_direction")
        if reasons:
            rejected.append({"sequence_index": entry.sequence_index, "reasons": tuple(reasons)})
        else:
            eligible.append(entry)
    selected = tuple(eligible[-3:])
    evidence: dict[str, object] = {
        "recent_sequence_indices": tuple(entry.sequence_index for entry in recent_entries),
        "eligible_sequence_indices": tuple(entry.sequence_index for entry in selected),
        "rejected_entries": tuple(rejected),
    }
    if len(selected) < 3:
        evidence["reason"] = "fewer_than_three_eligible_local_windows"
        return GateResult(
            name="directional_consistency",
            available=False,
            passed=False,
            value=len(selected),
            threshold=3,
            evidence=evidence,
        )
    edges = tuple(entry.top_edge for entry in selected)
    repeated_edge = any(edges.count(edge) >= 2 for edge in set(edges))
    nodes = [node for edge in edges if edge is not None for node in edge]
    shared_node = any(nodes.count(node) >= 2 for node in set(nodes))
    signs = tuple(entry.relationship_change_sign for entry in selected)
    consistent_sign = len(set(signs)) == 1
    evidence.update({"repeated_edge": repeated_edge, "shared_node": shared_node, "signs": signs})
    return GateResult(
        name="directional_consistency",
        available=True,
        passed=(repeated_edge or shared_node) and consistent_sign,
        value="consistent" if consistent_sign else "inconsistent",
        threshold="related_edges_and_same_nonzero_sign",
        evidence=evidence,
    )


def progression_gate(
    values: Sequence[float] | FloatArray,
    threshold: float | None,
    *,
    times: Sequence[float] | FloatArray | None = None,
    unavailable_reason: str = "uncalibrated",
) -> GateResult:
    """Require robust positive slope and current score above the recent median."""
    try:
        data = np.asarray(values, dtype=np.float64)
        coordinates = (
            np.arange(data.size, dtype=np.float64)
            if times is None
            else np.asarray(times, dtype=np.float64)
        )
    except (TypeError, ValueError) as error:
        raise ValidationError("progression values and times must be numeric") from error
    if data.ndim != 1 or not np.all(np.isfinite(data)):
        raise ValidationError("progression values must be finite and one-dimensional")
    recent = data[-5:]
    recent_times = coordinates[-5:]
    evidence: dict[str, object] = {
        "history_length": int(recent.size),
        "calibrated": threshold is not None,
    }
    if threshold is None:
        evidence["reason"] = unavailable_reason
        return GateResult(
            name="robust_progression",
            available=False,
            passed=False,
            value=None,
            threshold=None,
            evidence=evidence,
        )
    if not np.isfinite(threshold) or threshold < 0.0:
        raise ValidationError("progression threshold must be finite and non-negative")
    if recent.size < 3:
        evidence["reason"] = "insufficient_history"
        return GateResult(
            name="robust_progression",
            available=False,
            passed=False,
            value=None,
            threshold=threshold,
            evidence=evidence,
        )
    slope = robust_progression_slope(recent, times=recent_times)
    current_above_median = bool(recent[-1] > np.median(recent, overwrite_input=False))
    evidence["current_above_recent_median"] = current_above_median
    return GateResult(
        name="robust_progression",
        available=True,
        passed=bool(slope > threshold and current_above_median),
        value=slope,
        threshold=threshold,
        evidence=evidence,
    )


def unavailable_history_gate(name: str) -> GateResult:
    """Return explicit evidence that caller-owned history was not supplied."""
    return GateResult(
        name=name,
        available=False,
        passed=False,
        value=None,
        threshold=None,
        evidence={"history_available": False, "reason": "history_not_supplied"},
    )


def conventional_vibration_agreement_gate(
    result: ConventionalVibrationResult, channel_names: tuple[str, ...]
) -> GateResult:
    """Pass when any approved feature strictly exceeds its healthy channel threshold."""
    if any(feature.values.shape != (len(channel_names),) for feature in result.features):
        raise ValidationError("conventional feature channel count does not match channel names")
    triggered_features = tuple(
        feature.feature_name for feature in result.features if np.any(feature.positive_flags)
    )
    triggered_channels = tuple(
        channel_names[channel]
        for channel in range(len(channel_names))
        if any(feature.positive_flags[channel] for feature in result.features)
    )
    per_channel_counts = np.sum(
        np.asarray([feature.positive_flags for feature in result.features], dtype=np.int64),
        axis=0,
    )
    values_by_feature_and_channel = {
        feature.feature_name: {
            name: float(feature.values[index]) for index, name in enumerate(channel_names)
        }
        for feature in result.features
    }
    thresholds_by_feature_and_channel = {
        feature.feature_name: (
            None
            if feature.thresholds is None
            else {
                name: float(feature.thresholds[index])
                for index, name in enumerate(channel_names)
            }
        )
        for feature in result.features
    }
    evidence: dict[str, object] = {
        "feature_version": result.version,
        "values_by_feature_and_channel": values_by_feature_and_channel,
        "thresholds_by_feature_and_channel": thresholds_by_feature_and_channel,
        "triggered_features": triggered_features,
        "triggered_channels": triggered_channels,
        "triggered_feature_count": len(triggered_features),
        "triggered_channel_count": len(triggered_channels),
        "same_channel_multi_feature_agreement": bool(np.any(per_channel_counts >= 2)),
        "comparison_rule": "value_strictly_greater_than_healthy_upper_threshold",
        "gate_rule": "any_channel_exceeds_any_approved_feature_threshold",
        "numerical_floor": result.numerical_floor,
        "numerical_fallback_diagnostics": result.diagnostics,
    }
    if not result.available:
        evidence["reason"] = "healthy_calibration_unavailable"
    return GateResult(
        name="conventional_vibration_agreement",
        available=result.available,
        passed=bool(result.available and triggered_features),
        value=len(triggered_features),
        threshold=1,
        evidence=evidence,
    )

# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Immutable public result types."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
import numpy.typing as npt

from .exceptions import ValidationError

FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]


def _readonly_float64(values: npt.ArrayLike) -> FloatArray:
    result = np.array(values, dtype=np.float64, copy=True)
    result.setflags(write=False)
    return result


def _readonly_bool(values: npt.ArrayLike) -> BoolArray:
    result = np.array(values, dtype=np.bool_, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class ObservableResult:
    information: FloatArray
    omega: FloatArray
    phase: FloatArray
    shared_bin: int
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateResult:
    name: str
    available: bool
    passed: bool
    value: float | int | str | None
    threshold: float | int | str | None
    evidence: Mapping[str, object]

    def __post_init__(self) -> None:
        if type(self.available) is not bool or type(self.passed) is not bool:
            raise ValidationError("gate availability and outcome must be booleans")
        if self.passed and not self.available:
            raise ValidationError("an unavailable gate cannot pass")
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))


@dataclass(frozen=True)
class ConventionalFeatureResult:
    """Immutable per-feature conventional vibration evidence."""

    feature_name: str
    values: FloatArray
    thresholds: FloatArray | None
    positive_flags: BoolArray
    triggered_channel_names: tuple[str, ...]
    available: bool
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = _readonly_float64(self.values)
        positives = _readonly_bool(self.positive_flags)
        thresholds = (
            None if self.thresholds is None else _readonly_float64(self.thresholds)
        )
        if not self.feature_name:
            raise ValidationError("conventional feature name must be non-empty")
        if values.ndim != 1 or not np.all(np.isfinite(values)):
            raise ValidationError("conventional feature values must be finite and one-dimensional")
        if positives.shape != values.shape:
            raise ValidationError("conventional positive flags must match feature values")
        if thresholds is not None and (
            thresholds.shape != values.shape or not np.all(np.isfinite(thresholds))
        ):
            raise ValidationError("conventional thresholds must be finite and match feature values")
        if self.available != (thresholds is not None):
            raise ValidationError("conventional feature availability must match thresholds")
        if not self.available and np.any(positives):
            raise ValidationError("an unavailable conventional feature cannot be positive")
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "thresholds", thresholds)
        object.__setattr__(self, "positive_flags", positives)


@dataclass(frozen=True)
class ConventionalVibrationResult:
    """Immutable conventional vibration feature collection for one window."""

    version: str
    numerical_floor: float
    features: tuple[ConventionalFeatureResult, ...]
    available: bool
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.version:
            raise ValidationError("conventional feature version must be non-empty")
        if not np.isfinite(self.numerical_floor) or self.numerical_floor <= 0.0:
            raise ValidationError("conventional numerical floor must be finite and positive")
        if not self.features:
            raise ValidationError("conventional vibration result must contain features")
        if self.available != all(feature.available for feature in self.features):
            raise ValidationError("conventional result availability must match its features")


@dataclass(frozen=True)
class EvaluationResult:
    model_version: str
    profile_version: str
    gate_profile_version: str
    window_metadata: Mapping[str, object]
    exchange_matrix: FloatArray
    global_exchange_score: float
    edge_residuals: FloatArray
    node_incident_damage_ratio: FloatArray
    gate_results: tuple[GateResult, ...]
    final_decision: str
    candidate_nodes: tuple[str, ...]
    candidate_edges: tuple[tuple[str, str], ...]
    confidence_evidence: Mapping[str, object]
    warnings: tuple[str, ...]
    diagnostics: tuple[str, ...]
    conventional_vibration: ConventionalVibrationResult | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_metadata", MappingProxyType(dict(self.window_metadata)))
        object.__setattr__(
            self, "confidence_evidence", MappingProxyType(dict(self.confidence_evidence))
        )

    @property
    def node_concentration(self) -> FloatArray:
        """Compatibility alias for the explicitly named incident-damage ratio."""
        return self.node_incident_damage_ratio

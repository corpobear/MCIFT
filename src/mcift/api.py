# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Public immutable fit, calibrate, evaluate, explain, and save/load API."""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

from ._version import __version__
from .adapters.vibration import fit_vibration_scales
from .calibration import (
    calibration_quantile,
    calibration_quantiles,
    fit_channel_scales,
    fit_exchange_reference,
)
from .exceptions import ValidationError
from .exchange import compute_exchange_matrix
from .gates import (
    conventional_vibration_agreement_gate,
    directional_consistency_gate,
    persistence_gate,
    progression_gate,
    robust_progression_slope,
    threshold_gate,
    unavailable_history_gate,
)
from .history import HistoryEntry, MCIFTHistory
from .observables import DEFAULT_EPSILON, compute_observables
from .profiles import (
    GATE_PROFILE_ID,
    IMS_SIX_GATE_PROFILE_ID,
    TELEMETRY_PROFILE_ID,
    VIBRATION_PROFILE_ID,
    get_processing_profile,
    validate_gate_profile,
)
from .scoring import edge_residuals, global_exchange_score, node_incident_damage_ratio
from .types import (
    ConventionalFeatureResult,
    ConventionalVibrationResult,
    EvaluationResult,
    FloatArray,
    GateResult,
)
from .validation import (
    DEFAULT_LIMITS,
    ValidationLimits,
    validate_channel_names,
    validate_channel_units,
    validate_sampling_rate,
    validate_window,
    validate_windows,
)
from .vibration_features import (
    CONVENTIONAL_FEATURE_VERSION,
    DEFAULT_NUMERICAL_FLOOR,
    FEATURE_NAMES,
    compute_vibration_features,
)

MODEL_VERSION = __version__
MINIMUM_REFERENCE_WINDOWS = 8
MINIMUM_CALIBRATION_WINDOWS = 20
NODE_METRIC_ID = "mcift.node-incident-damage-ratio.v1"
SequenceMode = Literal["unordered", "chronological"]


@dataclass(frozen=True)
class MCIFTMonitor:
    """Immutable fitted stable-v1 exchange monitor."""

    sampling_rate_hz: float
    channel_names: tuple[str, ...]
    channel_units: tuple[str, ...]
    channel_scales: FloatArray
    sigma_i: float
    sigma_omega: float
    reference_exchange: FloatArray
    edge_scales: FloatArray
    processing_profile: str = TELEMETRY_PROFILE_ID
    gate_profile_version: str = GATE_PROFILE_ID
    node_metric_identifier: str = NODE_METRIC_ID
    calibration_sequence_mode: SequenceMode = "unordered"
    global_threshold: float | None = None
    local_edge_threshold: float | None = None
    progression_slope_threshold: float | None = None
    conventional_rms_thresholds: FloatArray | None = None
    conventional_excess_kurtosis_thresholds: FloatArray | None = None
    conventional_crest_factor_thresholds: FloatArray | None = None
    conventional_feature_version: str = CONVENTIONAL_FEATURE_VERSION
    conventional_numerical_floor: float = DEFAULT_NUMERICAL_FLOOR
    g: float = 1.0
    eta: float = 1.0
    epsilon: float = DEFAULT_EPSILON
    model_version: str = MODEL_VERSION
    diagnostics: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    reference_window_count: int = 0
    calibration_window_count: int = 0
    minimum_reference_windows: int = MINIMUM_REFERENCE_WINDOWS
    minimum_calibration_windows: int = MINIMUM_CALIBRATION_WINDOWS
    small_sample_override_used: bool = False
    numpy_version_at_fit: str = np.__version__
    python_version_at_fit: str = field(default_factory=platform.python_version)

    def __post_init__(self) -> None:
        channel_count = len(self.channel_names)
        validate_sampling_rate(self.sampling_rate_hz)
        validate_channel_names(self.channel_names, channel_count=channel_count)
        validate_channel_units(self.channel_units, channel_count=channel_count)
        get_processing_profile(self.processing_profile)
        validate_gate_profile(self.gate_profile_version)
        if (
            self.gate_profile_version == IMS_SIX_GATE_PROFILE_ID
            and self.processing_profile != VIBRATION_PROFILE_ID
        ):
            raise ValidationError("IMS six-gate profile requires the vibration processing profile")
        if self.node_metric_identifier != NODE_METRIC_ID:
            raise ValidationError("unknown node metric identifier")
        if self.calibration_sequence_mode not in ("unordered", "chronological"):
            raise ValidationError("calibration sequence mode is invalid")
        if (
            self.calibration_sequence_mode == "unordered"
            and self.progression_slope_threshold is not None
        ):
            raise ValidationError("unordered calibration cannot define a progression threshold")
        scales = _frozen_array(self.channel_scales)
        reference = _frozen_array(self.reference_exchange)
        fitted_edge_scales = _frozen_array(self.edge_scales)
        if (
            scales.shape != (channel_count,)
            or not np.all(np.isfinite(scales))
            or np.any(scales <= 0.0)
        ):
            raise ValidationError("fitted channel scales are invalid")
        expected_matrix_shape = (channel_count, channel_count)
        if (
            reference.shape != expected_matrix_shape
            or fitted_edge_scales.shape != expected_matrix_shape
        ):
            raise ValidationError("fitted relationship arrays have invalid shapes")
        if (
            not np.all(np.isfinite(reference))
            or not np.allclose(reference, reference.T)
            or np.any(reference < 0.0)
        ):
            raise ValidationError("reference exchange matrix is invalid")
        if (
            not np.all(np.isfinite(fitted_edge_scales))
            or not np.allclose(fitted_edge_scales, fitted_edge_scales.T)
            or np.any(fitted_edge_scales < 0.0)
        ):
            raise ValidationError("edge scale matrix is invalid")
        if not np.allclose(np.diag(reference), 0.0) or not np.allclose(
            np.diag(fitted_edge_scales), 0.0
        ):
            raise ValidationError("fitted relationship matrix diagonals must be zero")
        for numeric_value, name in (
            (self.sigma_i, "sigma_i"),
            (self.sigma_omega, "sigma_omega"),
            (self.g, "g"),
            (self.epsilon, "epsilon"),
        ):
            if not np.isfinite(numeric_value) or numeric_value <= 0.0:
                raise ValidationError(f"{name} must be finite and positive")
        if not np.isfinite(self.eta):
            raise ValidationError("eta must be finite")
        for threshold, name in (
            (self.global_threshold, "global_threshold"),
            (self.local_edge_threshold, "local_edge_threshold"),
            (self.progression_slope_threshold, "progression_slope_threshold"),
        ):
            if threshold is not None and (not np.isfinite(threshold) or threshold < 0.0):
                raise ValidationError(f"{name} must be finite and non-negative")
        if self.conventional_feature_version != CONVENTIONAL_FEATURE_VERSION:
            raise ValidationError("unknown conventional feature version")
        if (
            not np.isfinite(self.conventional_numerical_floor)
            or self.conventional_numerical_floor <= 0.0
        ):
            raise ValidationError("conventional numerical floor must be finite and positive")
        conventional_thresholds = tuple(
            _optional_frozen_array(value)
            for value in (
                self.conventional_rms_thresholds,
                self.conventional_excess_kurtosis_thresholds,
                self.conventional_crest_factor_thresholds,
            )
        )
        present = tuple(value is not None for value in conventional_thresholds)
        if any(present) and not all(present):
            raise ValidationError("conventional threshold arrays must be all present or all absent")
        if all(present):
            rms_thresholds, kurtosis_thresholds, crest_thresholds = conventional_thresholds
            if (
                rms_thresholds is None
                or kurtosis_thresholds is None
                or crest_thresholds is None
            ):  # pragma: no cover - guarded by all(present)
                raise ValidationError("conventional threshold state is inconsistent")
            for value in (rms_thresholds, kurtosis_thresholds, crest_thresholds):
                if value.shape != (channel_count,) or not np.all(np.isfinite(value)):
                    raise ValidationError(
                        "conventional threshold arrays must be finite with one value per channel"
                    )
            if np.any(rms_thresholds < 0.0) or np.any(crest_thresholds < 0.0):
                raise ValidationError("RMS and crest-factor thresholds must be non-negative")
        if self.gate_profile_version == GATE_PROFILE_ID and any(present):
            raise ValidationError(
                "exchange-screening profile cannot contain conventional thresholds"
            )
        for count_value, name in (
            (self.reference_window_count, "reference_window_count"),
            (self.calibration_window_count, "calibration_window_count"),
        ):
            if type(count_value) is not int or count_value < 0:
                raise ValidationError(f"{name} must be a non-negative integer")
        for minimum_value, name in (
            (self.minimum_reference_windows, "minimum_reference_windows"),
            (self.minimum_calibration_windows, "minimum_calibration_windows"),
        ):
            if type(minimum_value) is not int or minimum_value <= 0:
                raise ValidationError(f"{name} must be a positive integer")
        if type(self.small_sample_override_used) is not bool:
            raise ValidationError("small_sample_override_used must be a boolean")
        for version_value, name in (
            (self.numpy_version_at_fit, "numpy_version_at_fit"),
            (self.python_version_at_fit, "python_version_at_fit"),
        ):
            if not isinstance(version_value, str) or not version_value:
                raise ValidationError(f"{name} must be a non-empty string")
        if self.gate_profile_version == IMS_SIX_GATE_PROFILE_ID:
            if self.calibration_window_count == 0 and any(present):
                raise ValidationError(
                    "uncalibrated IMS monitor cannot contain conventional thresholds"
                )
            if self.calibration_window_count > 0 and not all(present):
                raise ValidationError("calibrated IMS monitor requires conventional thresholds")
        object.__setattr__(self, "channel_scales", scales)
        object.__setattr__(self, "reference_exchange", reference)
        object.__setattr__(self, "edge_scales", fitted_edge_scales)
        object.__setattr__(self, "conventional_rms_thresholds", conventional_thresholds[0])
        object.__setattr__(
            self, "conventional_excess_kurtosis_thresholds", conventional_thresholds[1]
        )
        object.__setattr__(
            self, "conventional_crest_factor_thresholds", conventional_thresholds[2]
        )

    @property
    def profile_version(self) -> str:
        """Compatibility name for the exact processing-profile identifier."""
        return self.processing_profile

    @property
    def gate_profile(self) -> str:
        """Exact gate-profile identifier."""
        return self.gate_profile_version

    @property
    def configuration_fingerprint(self) -> str:
        """Return a deterministic identity for history binding."""
        scalar_state = {
            "model_version": self.model_version,
            "processing_profile": self.processing_profile,
            "gate_profile": self.gate_profile,
            "node_metric_identifier": self.node_metric_identifier,
            "calibration_sequence_mode": self.calibration_sequence_mode,
            "sampling_rate_hz": self.sampling_rate_hz,
            "channel_names": self.channel_names,
            "channel_units": self.channel_units,
            "sigma_i": self.sigma_i,
            "sigma_omega": self.sigma_omega,
            "global_threshold": self.global_threshold,
            "local_edge_threshold": self.local_edge_threshold,
            "progression_slope_threshold": self.progression_slope_threshold,
            "conventional_feature_version": self.conventional_feature_version,
            "conventional_numerical_floor": self.conventional_numerical_floor,
            "g": self.g,
            "eta": self.eta,
            "epsilon": self.epsilon,
        }
        digest = hashlib.sha256(
            json.dumps(scalar_state, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        arrays = [self.channel_scales, self.reference_exchange, self.edge_scales]
        arrays.extend(
            array
            for array in (
                self.conventional_rms_thresholds,
                self.conventional_excess_kurtosis_thresholds,
                self.conventional_crest_factor_thresholds,
            )
            if array is not None
        )
        for array in arrays:
            digest.update(str(array.shape).encode("ascii"))
            digest.update(np.ascontiguousarray(array, dtype=np.float64).tobytes())
        return digest.hexdigest()

    @classmethod
    def fit(
        cls,
        healthy_windows: npt.ArrayLike,
        *,
        sampling_rate_hz: float,
        channel_names: list[str] | tuple[str, ...],
        channel_units: list[str] | tuple[str, ...] | None = None,
        profile: str = TELEMETRY_PROFILE_ID,
        gate_profile: str = GATE_PROFILE_ID,
        allow_small_sample: bool = False,
        validation_limits: ValidationLimits = DEFAULT_LIMITS,
    ) -> MCIFTMonitor:
        """Fit frozen channel scales and a healthy relationship reference."""
        profile_definition = get_processing_profile(profile)
        gate_profile_identifier = validate_gate_profile(gate_profile)
        if (
            gate_profile_identifier == IMS_SIX_GATE_PROFILE_ID
            and profile_definition.identifier != VIBRATION_PROFILE_ID
        ):
            raise ValidationError("IMS six-gate profile requires the vibration processing profile")
        windows = validate_windows(healthy_windows, limits=validation_limits)
        diagnostics: list[str] = []
        warnings: list[str] = []
        small_sample_used = _check_sample_count(
            len(windows),
            MINIMUM_REFERENCE_WINDOWS,
            kind="reference",
            allow_small_sample=allow_small_sample,
            diagnostics=diagnostics,
            warnings=warnings,
        )
        channel_count = windows[0].shape[1]
        names = validate_channel_names(channel_names, channel_count=channel_count)
        if channel_units is None:
            units = tuple("unspecified" for _ in range(channel_count))
            diagnostics.append("channel_units:explicitly_unspecified")
        else:
            units = validate_channel_units(channel_units, channel_count=channel_count)
        sampling_rate = validate_sampling_rate(sampling_rate_hz)
        if profile_definition.channel_scaler == "stacked_robust_mad":
            scales, scale_diagnostics = fit_channel_scales(windows)
        elif profile_definition.channel_scaler == "median_centered_window_rms":
            scales, scale_diagnostics = fit_vibration_scales(
                windows, scale_epsilon=profile_definition.robust_scale_floor
            )
        else:  # pragma: no cover
            raise ValidationError("processing profile has an unsupported channel scaler")
        sigma_i, sigma_omega, reference, fitted_edge_scales, reference_diagnostics = (
            fit_exchange_reference(
                windows, scales, sampling_rate, scale_epsilon=profile_definition.robust_scale_floor
            )
        )
        diagnostics.extend(scale_diagnostics)
        diagnostics.extend(reference_diagnostics)
        return cls(
            sampling_rate_hz=sampling_rate,
            channel_names=names,
            channel_units=units,
            channel_scales=scales,
            sigma_i=sigma_i,
            sigma_omega=sigma_omega,
            reference_exchange=reference,
            edge_scales=fitted_edge_scales,
            processing_profile=profile_definition.identifier,
            gate_profile_version=gate_profile_identifier,
            conventional_numerical_floor=profile_definition.robust_scale_floor,
            diagnostics=tuple(diagnostics),
            warnings=tuple(warnings),
            reference_window_count=len(windows),
            small_sample_override_used=small_sample_used,
        )

    def calibrate(
        self,
        calibration_windows: npt.ArrayLike,
        *,
        quantile: float | None = None,
        sequence_order: SequenceMode = "unordered",
        allow_small_sample: bool = False,
        validation_limits: ValidationLimits = DEFAULT_LIMITS,
    ) -> MCIFTMonitor:
        """Return a new monitor with thresholds fitted on calibration data only."""
        if sequence_order not in ("unordered", "chronological"):
            raise ValidationError("sequence_order must be 'unordered' or 'chronological'")
        profile = get_processing_profile(self.processing_profile)
        probability = profile.calibration_quantile if quantile is None else quantile
        if not 0.0 < probability <= 1.0:
            raise ValidationError("quantile must be in (0, 1]")
        windows = validate_windows(
            calibration_windows, expected_channels=len(self.channel_names), limits=validation_limits
        )
        diagnostics = list(self.diagnostics)
        warnings = list(self.warnings)
        small_sample_used = _check_sample_count(
            len(windows),
            MINIMUM_CALIBRATION_WINDOWS,
            kind="calibration",
            allow_small_sample=allow_small_sample,
            diagnostics=diagnostics,
            warnings=warnings,
        )
        global_scores = np.empty(len(windows), dtype=np.float64)
        local_scores = np.empty(len(windows), dtype=np.float64)
        conventional_rows: dict[str, FloatArray] | None = None
        if self.gate_profile == IMS_SIX_GATE_PROFILE_ID:
            conventional_rows = {
                name: np.empty((len(windows), len(self.channel_names)), dtype=np.float64)
                for name in FEATURE_NAMES
            }
        upper = np.triu_indices(len(self.channel_names), k=1)
        for index, window in enumerate(windows):
            matrix, _ = self._exchange_for_validated_window(window)
            global_scores[index] = global_exchange_score(matrix, self.reference_exchange)
            residuals = edge_residuals(matrix, self.reference_exchange, self.edge_scales)
            local_scores[index] = float(np.max(residuals[upper]))
            if conventional_rows is not None:
                feature_values = compute_vibration_features(
                    window, numerical_floor=self.conventional_numerical_floor
                )
                for name in FEATURE_NAMES:
                    conventional_rows[name][index] = getattr(feature_values, name)
                diagnostics.extend(
                    f"calibration_window={index}:{item}" for item in feature_values.diagnostics
                )
        method = profile.calibration_quantile_method
        progression_threshold: float | None = None
        if sequence_order == "chronological":
            slopes = np.asarray(
                [
                    robust_progression_slope(global_scores[max(0, index - 4) : index + 1])
                    for index in range(2, len(global_scores))
                ],
                dtype=np.float64,
            )
            if slopes.size == 0:
                slopes = np.zeros(1, dtype=np.float64)
                diagnostics.append("progression_threshold:zero_small_sample_fallback")
            progression_threshold = max(
                0.0, calibration_quantile(slopes, probability, method=method)
            )
        else:
            diagnostics.append("progression_threshold:unavailable:unordered_calibration")
        conventional_thresholds: dict[str, FloatArray | None] = {
            name: None for name in FEATURE_NAMES
        }
        if conventional_rows is not None:
            conventional_thresholds = {
                name: calibration_quantiles(values, probability, method=method)
                for name, values in conventional_rows.items()
            }
        return replace(
            self,
            global_threshold=calibration_quantile(global_scores, probability, method=method),
            local_edge_threshold=calibration_quantile(local_scores, probability, method=method),
            progression_slope_threshold=progression_threshold,
            conventional_rms_thresholds=conventional_thresholds["centered_rms"],
            conventional_excess_kurtosis_thresholds=conventional_thresholds[
                "excess_kurtosis"
            ],
            conventional_crest_factor_thresholds=conventional_thresholds["crest_factor"],
            calibration_sequence_mode=sequence_order,
            diagnostics=tuple(dict.fromkeys(diagnostics)),
            warnings=tuple(dict.fromkeys(warnings)),
            calibration_window_count=len(windows),
            small_sample_override_used=self.small_sample_override_used or small_sample_used,
        )

    def evaluate(
        self, current_window: npt.ArrayLike, *, validation_limits: ValidationLimits = DEFAULT_LIMITS
    ) -> EvaluationResult:
        """Score one window without hidden history or mutable fitted state."""
        result, _, _, _ = self._evaluate_base(current_window, validation_limits)
        return result

    def evaluate_with_history(
        self,
        current_window: npt.ArrayLike,
        *,
        history: MCIFTHistory,
        sequence_index: int | None = None,
        validation_limits: ValidationLimits = DEFAULT_LIMITS,
    ) -> tuple[EvaluationResult, MCIFTHistory]:
        """Score one window and return a new caller-owned history."""
        if not isinstance(history, MCIFTHistory):
            raise ValidationError("history must be an MCIFTHistory")
        history.validate_for_monitor(
            model_version=self.model_version,
            processing_profile=self.processing_profile,
            gate_profile=self.gate_profile,
            channel_count=len(self.channel_names),
            monitor_fingerprint=self.configuration_fingerprint,
        )
        base, raw_top_edge, relationship_sign, max_edge = self._evaluate_base(
            current_window, validation_limits
        )
        global_gate, local_gate = base.gate_results[:2]
        next_index = 0 if not history.entries else history.entries[-1].sequence_index + 1
        actual_index = next_index if sequence_index is None else sequence_index
        entry = HistoryEntry(
            global_score=base.global_exchange_score,
            global_positive=global_gate.passed,
            local_score=max_edge,
            local_positive=local_gate.passed,
            base_positive=global_gate.passed or local_gate.passed,
            top_edge=raw_top_edge if local_gate.passed else None,
            relationship_change_sign=relationship_sign if local_gate.passed else 0,
            model_version=self.model_version,
            processing_profile=self.processing_profile,
            gate_profile=self.gate_profile,
            channel_count=len(self.channel_names),
            sequence_index=actual_index,
        )
        updated = history.append(entry, monitor_fingerprint=self.configuration_fingerprint)
        persistence = persistence_gate([item.base_positive for item in updated.entries])
        directional = directional_consistency_gate(updated.entries)
        progression = progression_gate(
            [item.global_score for item in updated.entries],
            self.progression_slope_threshold,
            times=[item.sequence_index for item in updated.entries],
            unavailable_reason="chronological_calibration_unavailable"
            if self.calibration_sequence_mode == "unordered"
            else "uncalibrated",
        )
        gates: tuple[GateResult, ...]
        if self.gate_profile == IMS_SIX_GATE_PROFILE_ID:
            conventional = next(
                gate
                for gate in base.gate_results
                if gate.name == "conventional_vibration_agreement"
            )
            gates = (
                global_gate,
                local_gate,
                persistence,
                directional,
                progression,
                conventional,
            )
            confidence = _ims_six_gate_confidence(gates)
            if not (
                global_gate.available and local_gate.available and conventional.available
            ):
                decision = "not_calibrated"
            elif confidence["high_confidence_ims_warning"] is True:
                decision = "high_confidence_ims_warning"
            elif confidence["persistent_mcift_warning"] is True:
                decision = "persistent_mcift_warning"
            elif confidence["screening_positive"] is True:
                decision = "screening_positive"
            else:
                decision = "screening_negative"
            result = replace(
                base,
                gate_results=gates,
                final_decision=decision,
                confidence_evidence={**confidence, "history_length": len(updated.entries)},
                warnings=tuple(
                    warning
                    for warning in base.warnings
                    if not warning.startswith("Single-window screening")
                ),
            )
            return result, updated

        gates = (global_gate, local_gate, persistence, directional, progression)
        calibrated = global_gate.available and local_gate.available
        base_positive = entry.base_positive
        corroborating = tuple(
            gate.name for gate in (directional, progression) if gate.available and gate.passed
        )
        persistent_warning = bool(
            calibrated and base_positive and persistence.passed and corroborating
        )
        available_gate_names = tuple(gate.name for gate in gates if gate.available)
        passed_gate_names = tuple(gate.name for gate in gates if gate.available and gate.passed)
        if not calibrated:
            decision = "not_calibrated"
        elif persistent_warning:
            decision = "persistent_exchange_warning"
        elif base_positive:
            decision = "screening_positive"
        else:
            decision = "screening_negative"
        result = replace(
            base,
            gate_results=gates,
            final_decision=decision,
            confidence_evidence={
                "base_positive": base_positive,
                "persistent_positive": persistence.passed,
                "corroborating_gate_names": corroborating,
                "available_gate_names": available_gate_names,
                "passed_gate_names": passed_gate_names,
                "passed_gate_count": len(passed_gate_names),
                "available_gate_count": len(available_gate_names),
                "stable_warning": persistent_warning,
                "gate_profile": self.gate_profile,
                "decision_profile": self.gate_profile,
                "history_length": len(updated.entries),
            },
            warnings=tuple(
                warning
                for warning in base.warnings
                if not warning.startswith("Single-window screening")
            ),
        )
        return result, updated

    def explain(self, result: EvaluationResult) -> dict[str, Any]:
        """Return a compact JSON-compatible evidence summary."""
        if result.model_version != self.model_version:
            raise ValueError("result model version does not match monitor")
        return {
            "decision": result.final_decision,
            "processing_profile": result.profile_version,
            "gate_profile": result.gate_profile_version,
            "global_exchange_score": result.global_exchange_score,
            "candidate_nodes": list(result.candidate_nodes),
            "candidate_edges": [list(edge) for edge in result.candidate_edges],
            "node_metric": NODE_METRIC_ID,
            "gates": [
                {
                    "name": gate.name,
                    "available": gate.available,
                    "passed": gate.passed,
                    "value": gate.value,
                    "threshold": gate.threshold,
                    "evidence": dict(gate.evidence),
                }
                for gate in result.gate_results
            ],
            "warnings": list(result.warnings),
            "confidence_evidence": dict(result.confidence_evidence),
            "conventional_vibration": _explain_conventional(result.conventional_vibration),
        }

    def save(self, path: str | Path) -> None:
        """Save an inspectable checksum-protected model directory."""
        from .serialization import save_monitor

        save_monitor(self, Path(path))

    @classmethod
    def load(cls, path: str | Path) -> MCIFTMonitor:
        """Load and verify an inspectable model directory without code execution."""
        from .serialization import load_monitor

        return load_monitor(Path(path))

    def _evaluate_base(
        self, current_window: npt.ArrayLike, validation_limits: ValidationLimits
    ) -> tuple[EvaluationResult, tuple[int, int], int, float]:
        window = validate_window(
            current_window, expected_channels=len(self.channel_names), limits=validation_limits
        )
        matrix, observable_diagnostics = self._exchange_for_validated_window(window)
        global_score = global_exchange_score(matrix, self.reference_exchange)
        residuals = edge_residuals(matrix, self.reference_exchange, self.edge_scales)
        ratios = node_incident_damage_ratio(residuals)
        upper = np.triu_indices(len(self.channel_names), k=1)
        edge_values = residuals[upper]
        top_edge_position = int(np.argmax(edge_values))
        first, second = int(upper[0][top_edge_position]), int(upper[1][top_edge_position])
        top_edge = (first, second)
        max_edge = float(edge_values[top_edge_position])
        relationship_sign = int(
            np.sign(matrix[first, second] - self.reference_exchange[first, second])
        )
        global_gate = threshold_gate("global_deformation", global_score, self.global_threshold)
        local_gate = threshold_gate(
            "local_relationship_damage", max_edge, self.local_edge_threshold
        )
        history_gates: tuple[GateResult, ...] = (
            unavailable_history_gate("persistence"),
            unavailable_history_gate("directional_consistency"),
            unavailable_history_gate("robust_progression"),
        )
        conventional_result: ConventionalVibrationResult | None = None
        conventional_gate: GateResult | None = None
        if self.gate_profile == IMS_SIX_GATE_PROFILE_ID:
            conventional_result = self._conventional_result(window)
            conventional_gate = conventional_vibration_agreement_gate(
                conventional_result, self.channel_names
            )
        calibrated = global_gate.available and local_gate.available
        if not calibrated:
            decision = "not_calibrated"
        elif global_gate.passed or local_gate.passed:
            decision = "screening_positive"
        else:
            decision = "screening_negative"
        candidate_edges: tuple[tuple[str, str], ...] = ()
        candidate_nodes: tuple[str, ...] = ()
        if local_gate.passed:
            candidate_edges = ((self.channel_names[first], self.channel_names[second]),)
            candidate_nodes = (self.channel_names[int(np.argmax(ratios))],)
        warnings = tuple(
            dict.fromkeys(
                (
                    *self.warnings,
                    "Single-window screening is not a stable warning; use "
                    "evaluate_with_history for persistence evidence.",
                )
            )
        )
        base_gates = (
            (global_gate, local_gate)
            if conventional_gate is None
            else (global_gate, local_gate, conventional_gate)
        )
        available_gate_names = tuple(gate.name for gate in base_gates if gate.available)
        passed_gate_names = tuple(
            gate.name for gate in base_gates if gate.available and gate.passed
        )
        gate_results = (
            (global_gate, local_gate, *history_gates)
            if conventional_gate is None
            else (global_gate, local_gate, *history_gates, conventional_gate)
        )
        confidence_evidence: dict[str, object]
        if conventional_gate is None:
            confidence_evidence = {
                "base_positive": global_gate.passed or local_gate.passed,
                "persistent_positive": False,
                "corroborating_gate_names": (),
                "available_gate_names": available_gate_names,
                "passed_gate_names": passed_gate_names,
                "passed_gate_count": len(passed_gate_names),
                "available_gate_count": len(available_gate_names),
                "stable_warning": False,
                "gate_profile": self.gate_profile,
                "decision_profile": self.gate_profile,
                "history_length": 0,
            }
        else:
            confidence_evidence = {
                **_ims_six_gate_confidence(gate_results),
                "history_length": 0,
            }
        result = EvaluationResult(
            model_version=self.model_version,
            profile_version=self.processing_profile,
            gate_profile_version=self.gate_profile,
            window_metadata={
                "samples": window.shape[0],
                "channels": window.shape[1],
                "sampling_rate_hz": self.sampling_rate_hz,
            },
            exchange_matrix=_frozen_array(matrix),
            global_exchange_score=global_score,
            edge_residuals=_frozen_array(residuals),
            node_incident_damage_ratio=_frozen_array(ratios),
            gate_results=gate_results,
            final_decision=decision,
            candidate_nodes=candidate_nodes,
            candidate_edges=candidate_edges,
            confidence_evidence=confidence_evidence,
            warnings=warnings,
            diagnostics=tuple((*self.diagnostics, *observable_diagnostics)),
            conventional_vibration=conventional_result,
        )
        return result, top_edge, relationship_sign, max_edge

    def _exchange_for_validated_window(
        self, window: FloatArray
    ) -> tuple[FloatArray, tuple[str, ...]]:
        observables = compute_observables(
            window, self.channel_scales, self.sampling_rate_hz, epsilon=self.epsilon
        )
        matrix = compute_exchange_matrix(
            observables.information,
            observables.omega,
            observables.phase,
            sigma_i=self.sigma_i,
            sigma_omega=self.sigma_omega,
            g=self.g,
        )
        return matrix, observables.diagnostics

    def _conventional_result(self, window: FloatArray) -> ConventionalVibrationResult:
        values = compute_vibration_features(
            window, numerical_floor=self.conventional_numerical_floor
        )
        thresholds_by_name = {
            "centered_rms": self.conventional_rms_thresholds,
            "excess_kurtosis": self.conventional_excess_kurtosis_thresholds,
            "crest_factor": self.conventional_crest_factor_thresholds,
        }
        feature_results: list[ConventionalFeatureResult] = []
        for name in FEATURE_NAMES:
            feature_values = getattr(values, name)
            thresholds = thresholds_by_name[name]
            positives = (
                np.zeros(feature_values.shape, dtype=np.bool_)
                if thresholds is None
                else feature_values > thresholds
            )
            feature_results.append(
                ConventionalFeatureResult(
                    feature_name=name,
                    values=feature_values,
                    thresholds=thresholds,
                    positive_flags=positives,
                    triggered_channel_names=tuple(
                        self.channel_names[index]
                        for index in np.flatnonzero(positives).tolist()
                    ),
                    available=thresholds is not None,
                    diagnostics=values.diagnostics,
                )
            )
        return ConventionalVibrationResult(
            version=self.conventional_feature_version,
            numerical_floor=self.conventional_numerical_floor,
            features=tuple(feature_results),
            available=all(feature.available for feature in feature_results),
            diagnostics=values.diagnostics,
        )


def _check_sample_count(
    actual: int,
    minimum: int,
    *,
    kind: str,
    allow_small_sample: bool,
    diagnostics: list[str],
    warnings: list[str],
) -> bool:
    if minimum <= 0:
        raise ValidationError(f"minimum_{kind}_windows must be positive")
    if actual >= minimum:
        return False
    if not allow_small_sample:
        raise ValidationError(f"at least {minimum} {kind} windows are required")
    diagnostics.append(f"small_sample_override:{kind}:actual={actual}:minimum={minimum}")
    warnings.append(
        f"Research small-sample override used for {kind} fitting "
        f"({actual} windows; normal minimum {minimum})."
    )
    return True


def _frozen_array(values: npt.ArrayLike) -> FloatArray:
    result = np.array(values, dtype=np.float64, copy=True)
    result.setflags(write=False)
    return result


def _optional_frozen_array(values: npt.ArrayLike | None) -> FloatArray | None:
    return None if values is None else _frozen_array(values)


def _ims_six_gate_confidence(gates: tuple[GateResult, ...]) -> dict[str, object]:
    by_name = {gate.name: gate for gate in gates}
    expected = {
        "global_deformation",
        "local_relationship_damage",
        "persistence",
        "directional_consistency",
        "robust_progression",
        "conventional_vibration_agreement",
    }
    if set(by_name) != expected:
        raise ValidationError("IMS six-gate decision requires exactly the six approved gates")
    global_gate = by_name["global_deformation"]
    local_gate = by_name["local_relationship_damage"]
    persistence = by_name["persistence"]
    directional = by_name["directional_consistency"]
    progression = by_name["robust_progression"]
    conventional = by_name["conventional_vibration_agreement"]
    screening_positive = global_gate.passed or local_gate.passed
    corroborating_positive = directional.passed or progression.passed
    persistent_warning = bool(
        persistence.available
        and persistence.passed
        and screening_positive
        and corroborating_positive
    )
    available_gate_names = tuple(gate.name for gate in gates if gate.available)
    passed_gate_names = tuple(gate.name for gate in gates if gate.available and gate.passed)
    mandatory_gate_names = (
        "persistence",
        "conventional_vibration_agreement",
        "global_deformation|local_relationship_damage",
        "directional_consistency|robust_progression",
    )
    missing_mandatory: list[str] = []
    if not persistence.available:
        missing_mandatory.append("persistence")
    if not conventional.available:
        missing_mandatory.append("conventional_vibration_agreement")
    if not (global_gate.available or local_gate.available):
        missing_mandatory.append("global_deformation|local_relationship_damage")
    if not (directional.available or progression.available):
        missing_mandatory.append("directional_consistency|robust_progression")
    high_confidence_available = persistence.available and conventional.available
    high_confidence = bool(
        high_confidence_available
        and persistence.passed
        and conventional.passed
        and screening_positive
        and corroborating_positive
        and len(passed_gate_names) >= 5
    )
    return {
        "decision_profile": IMS_SIX_GATE_PROFILE_ID,
        "available_gate_names": available_gate_names,
        "passed_gate_names": passed_gate_names,
        "mandatory_gate_names": mandatory_gate_names,
        "missing_mandatory_gate_names": tuple(missing_mandatory),
        "passed_gate_count": len(passed_gate_names),
        "available_gate_count": len(available_gate_names),
        "screening_positive": screening_positive,
        "persistent_mcift_warning": persistent_warning,
        "high_confidence_ims_warning": high_confidence if high_confidence_available else None,
    }


def _explain_conventional(
    result: ConventionalVibrationResult | None,
) -> dict[str, object] | None:
    if result is None:
        return None
    return {
        "version": result.version,
        "numerical_floor": result.numerical_floor,
        "available": result.available,
        "diagnostics": list(result.diagnostics),
        "features": [
            {
                "feature_name": feature.feature_name,
                "values": feature.values.tolist(),
                "thresholds": (
                    None if feature.thresholds is None else feature.thresholds.tolist()
                ),
                "positive_flags": feature.positive_flags.tolist(),
                "triggered_channel_names": list(feature.triggered_channel_names),
                "available": feature.available,
                "diagnostics": list(feature.diagnostics),
            }
            for feature in result.features
        ],
    }

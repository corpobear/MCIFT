# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Immutable, versioned processing-profile definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .exceptions import ValidationError

TELEMETRY_PROFILE_ID = "mcift.exchange.telemetry.v1"
VIBRATION_PROFILE_ID = "mcift.exchange.vibration.v1"
GATE_PROFILE_ID = "mcift.gates.exchange-screening.v1"
IMS_SIX_GATE_PROFILE_ID = "mcift.gates.ims-six-gate.v1"

_GATE_PROFILE_IDS = frozenset({GATE_PROFILE_ID, IMS_SIX_GATE_PROFILE_ID})


@dataclass(frozen=True)
class ProcessingProfile:
    """Behavior that cannot change without a new profile identifier."""

    identifier: str
    channel_scaler: str
    calibration_quantile: float
    calibration_quantile_method: Literal["higher", "linear"]
    robust_scale_floor: float


_PROFILES = {
    TELEMETRY_PROFILE_ID: ProcessingProfile(
        identifier=TELEMETRY_PROFILE_ID,
        channel_scaler="stacked_robust_mad",
        calibration_quantile=0.99,
        calibration_quantile_method="higher",
        robust_scale_floor=2.220446049250313e-16,
    ),
    VIBRATION_PROFILE_ID: ProcessingProfile(
        identifier=VIBRATION_PROFILE_ID,
        channel_scaler="median_centered_window_rms",
        calibration_quantile=0.995,
        calibration_quantile_method="linear",
        robust_scale_floor=1e-12,
    ),
}


def get_processing_profile(identifier: str) -> ProcessingProfile:
    """Return a known frozen profile or fail closed."""
    try:
        return _PROFILES[identifier]
    except KeyError as error:
        raise ValidationError(f"unknown processing profile: {identifier}") from error


def processing_profile_ids() -> tuple[str, ...]:
    """Return known identifiers in deterministic order."""
    return tuple(sorted(_PROFILES))


def validate_gate_profile(identifier: str) -> str:
    """Return a known frozen gate-profile identifier or fail closed."""
    if identifier not in _GATE_PROFILE_IDS:
        raise ValidationError(f"unknown gate profile: {identifier}")
    return identifier


def gate_profile_ids() -> tuple[str, ...]:
    """Return known gate-profile identifiers in deterministic order."""
    return tuple(sorted(_GATE_PROFILE_IDS))

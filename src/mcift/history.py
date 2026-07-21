# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Explicit immutable evaluation history."""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise

from .exceptions import ValidationError


def _require_bool(value: object, name: str) -> None:
    if type(value) is not bool:
        raise ValidationError(f"{name} must use actual booleans")


@dataclass(frozen=True)
class HistoryEntry:
    """Validated evidence retained from one evaluated window."""

    global_score: float
    global_positive: bool
    local_score: float
    local_positive: bool
    base_positive: bool
    top_edge: tuple[int, int] | None
    relationship_change_sign: int
    model_version: str
    processing_profile: str
    gate_profile: str
    channel_count: int
    sequence_index: int

    def __post_init__(self) -> None:
        for name in ("global_score", "local_score"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ValidationError(f"history {name} must be a real number")
            normalized = float(value)
            if not math.isfinite(normalized):
                raise ValidationError(f"history {name} must be finite")
            object.__setattr__(self, name, normalized)
        for name in ("global_positive", "local_positive", "base_positive"):
            _require_bool(getattr(self, name), f"history {name}")
        if self.base_positive != (self.global_positive or self.local_positive):
            raise ValidationError("history base_positive must equal the logical OR of base gates")
        if type(self.channel_count) is not int or self.channel_count < 2:
            raise ValidationError("history channel_count must be an integer of at least two")
        if type(self.sequence_index) is not int or self.sequence_index < 0:
            raise ValidationError("history sequence_index must be a non-negative integer")
        if type(self.relationship_change_sign) is not int or self.relationship_change_sign not in (
            -1,
            0,
            1,
        ):
            raise ValidationError("history relationship_change_sign must be -1, 0, or 1")
        if self.top_edge is not None:
            edge = self.top_edge
            if type(edge) is not tuple or len(edge) != 2:
                raise ValidationError("history top_edge must be a two-integer tuple or None")
            first, second = edge
            if type(first) is not int or type(second) is not int:
                raise ValidationError("history top_edge endpoints must be integers")
            if first < 0 or second < 0:
                raise ValidationError("history top_edge endpoints must be non-negative")
            if first == second:
                raise ValidationError("history top_edge endpoints must be distinct")
            if first > second:
                raise ValidationError("history top_edge endpoints must be ordered")
            if second >= self.channel_count:
                raise ValidationError("history top_edge exceeds the channel count")
        for name in ("model_version", "processing_profile", "gate_profile"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValidationError(f"history {name} must be a non-empty string")


@dataclass(frozen=True)
class MCIFTHistory:
    """Caller-owned bounded history, bound to one fitted monitor configuration."""

    maxlen: int = 32
    entries: tuple[HistoryEntry, ...] = ()
    monitor_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if type(self.maxlen) is not int or self.maxlen < 1:
            raise ValidationError("history maxlen must be a positive integer")
        if type(self.entries) is not tuple:
            raise ValidationError("history entries must be a tuple")
        if len(self.entries) > self.maxlen:
            raise ValidationError("history contains more entries than maxlen")
        if any(not isinstance(entry, HistoryEntry) for entry in self.entries):
            raise ValidationError("history entries must contain only HistoryEntry values")
        indices = tuple(entry.sequence_index for entry in self.entries)
        if any(later <= earlier for earlier, later in pairwise(indices)):
            raise ValidationError("history sequence indices must be strictly increasing")
        if self.monitor_fingerprint is not None:
            fingerprint = self.monitor_fingerprint
            if (
                not isinstance(fingerprint, str)
                or len(fingerprint) != 64
                or any(character not in "0123456789abcdef" for character in fingerprint)
            ):
                raise ValidationError("history monitor fingerprint must be lowercase SHA-256")

    def append(
        self, entry: HistoryEntry, *, monitor_fingerprint: str | None = None
    ) -> MCIFTHistory:
        """Return a validated history containing the newest entry."""
        if not isinstance(entry, HistoryEntry):
            raise ValidationError("history append requires a HistoryEntry")
        if self.entries and entry.sequence_index <= self.entries[-1].sequence_index:
            raise ValidationError("history sequence indices must be strictly increasing")
        if (
            self.monitor_fingerprint is not None
            and monitor_fingerprint is not None
            and self.monitor_fingerprint != monitor_fingerprint
        ):
            raise ValidationError("history belongs to a differently configured monitor")
        binding = self.monitor_fingerprint or monitor_fingerprint
        return MCIFTHistory(
            maxlen=self.maxlen,
            entries=(*self.entries, entry)[-self.maxlen :],
            monitor_fingerprint=binding,
        )

    def validate_for_monitor(
        self,
        *,
        model_version: str,
        processing_profile: str,
        gate_profile: str,
        channel_count: int,
        monitor_fingerprint: str,
    ) -> None:
        """Reject evidence produced by another version, profile, or fitted monitor."""
        for entry in self.entries:
            if not (
                entry.model_version == model_version
                and entry.processing_profile == processing_profile
                and entry.gate_profile == gate_profile
                and entry.channel_count == channel_count
            ):
                raise ValidationError("history metadata does not match this monitor")
        if self.entries and self.monitor_fingerprint is None:
            raise ValidationError("history is not bound to a fitted monitor configuration")
        if self.monitor_fingerprint is not None and self.monitor_fingerprint != monitor_fingerprint:
            raise ValidationError("history belongs to a differently configured monitor")

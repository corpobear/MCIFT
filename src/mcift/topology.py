# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Stable topology data structures; fitted topology behavior is not yet released."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class DirectedEdge:
    """One predeclared directed relationship between named groups."""

    source: str
    destination: str

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.destination.strip():
            raise ValueError("topology endpoints must be non-empty")
        if self.source == self.destination:
            raise ValueError("topology self-edges are not allowed")

# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from mcift import MCIFTMonitor
from mcift.exceptions import SerializationError


def test_load_rejects_checksum_tampering(tmp_path: Path) -> None:
    rng = np.random.default_rng(7)
    windows = rng.normal(size=(8, 16, 2))
    model_path = tmp_path / "monitor.mcift"
    MCIFTMonitor.fit(
        windows, sampling_rate_hz=100.0, channel_names=["a", "b"]
    ).save(model_path)
    with (model_path / "manifest.json").open("ab") as stream:
        stream.write(b" ")

    with pytest.raises(SerializationError, match="checksum"):
        MCIFTMonitor.load(model_path)


def test_load_rejects_object_arrays_even_with_matching_checksum(tmp_path: Path) -> None:
    rng = np.random.default_rng(8)
    windows = rng.normal(size=(8, 16, 2))
    model_path = tmp_path / "monitor.mcift"
    MCIFTMonitor.fit(
        windows, sampling_rate_hz=100.0, channel_names=["a", "b"]
    ).save(model_path)
    arrays_path = model_path / "arrays.npz"
    np.savez(
        arrays_path,
        channel_scales=np.array([object(), object()], dtype=object),
        reference_exchange=np.zeros((2, 2)),
        edge_scales=np.ones((2, 2)),
    )
    checksums_path = model_path / "checksums.json"
    checksums = json.loads(checksums_path.read_text(encoding="utf-8"))
    checksums["arrays.npz"] = hashlib.sha256(arrays_path.read_bytes()).hexdigest()
    checksums_path.write_text(json.dumps(checksums), encoding="utf-8")

    with pytest.raises(SerializationError, match="object arrays"):
        MCIFTMonitor.load(model_path)

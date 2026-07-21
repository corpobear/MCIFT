# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from mcift.adapters import ims
from mcift.adapters.ims import adapt_ims_array, load_ims_file
from mcift.exceptions import ValidationError
from mcift.validation import ValidationLimits


def test_ims_defaults_are_laptop_bounded() -> None:
    assert ims.DEFAULT_MAX_IMS_FILE_BYTES == 64 * 1024 * 1024
    assert ims.DEFAULT_IMS_LIMITS.max_samples_per_window == 250_000
    assert ims.DEFAULT_IMS_LIMITS.max_total_bytes == 128 * 1024 * 1024


def test_load_local_ims_file_preserves_channel_order(tmp_path: Path) -> None:
    path = tmp_path / "recording.txt"
    path.write_text("1\t2\t3\n4\t5\t6\n7\t8\t9\n10\t11\t12\n", encoding="ascii")

    recording = load_ims_file(path, expected_channel_count=3, sampling_rate_hz=20_000.0)

    np.testing.assert_array_equal(
        recording.values,
        np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0], [10.0, 11.0, 12.0]]),
    )
    assert recording.sampling_rate_hz == 20_000.0


def test_ims_adapter_rejects_malformed_rows_and_wrong_channels(tmp_path: Path) -> None:
    malformed = tmp_path / "bad.txt"
    malformed.write_text("1 2\n3 nope\n4 5\n6 7\n", encoding="ascii")
    with pytest.raises(ValidationError, match="row 2"):
        load_ims_file(malformed, expected_channel_count=2, sampling_rate_hz=20_000.0)

    with pytest.raises(ValidationError, match="expected 3 channels"):
        adapt_ims_array(np.ones((8, 2)), expected_channel_count=3, sampling_rate_hz=20_000.0)


def test_ims_file_size_limit_is_enforced_before_parse(tmp_path: Path) -> None:
    path = tmp_path / "large.txt"
    path.write_text("1 2\n" * 8, encoding="ascii")
    with pytest.raises(ValidationError, match="file-size limit"):
        load_ims_file(
            path,
            expected_channel_count=2,
            sampling_rate_hz=20_000.0,
            max_file_bytes=4,
        )


def test_ims_parser_rejects_excessive_rows_and_elements(tmp_path: Path) -> None:
    path = tmp_path / "rows.txt"
    path.write_text("1 2\n" * 5, encoding="ascii")

    with pytest.raises(ValidationError, match="sample limit"):
        load_ims_file(
            path,
            expected_channel_count=2,
            sampling_rate_hz=20_000.0,
            validation_limits=ValidationLimits(max_samples_per_window=4),
        )
    with pytest.raises(ValidationError, match="element limit"):
        load_ims_file(
            path,
            expected_channel_count=2,
            sampling_rate_hz=20_000.0,
            validation_limits=ValidationLimits(max_total_elements=8),
        )


def test_ims_parser_rejects_invalid_utf8_and_nonfinite_values(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.txt"
    invalid.write_bytes(b"1 2\n3 \xff\n4 5\n6 7\n")
    with pytest.raises(ValidationError, match="UTF-8"):
        load_ims_file(invalid, expected_channel_count=2, sampling_rate_hz=20_000.0)

    nonfinite = tmp_path / "nonfinite.txt"
    nonfinite.write_text("1 2\n3 inf\n4 5\n6 7\n", encoding="ascii")
    with pytest.raises(ValidationError, match="non-finite"):
        load_ims_file(nonfinite, expected_channel_count=2, sampling_rate_hz=20_000.0)


def test_ims_parser_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("1 2\n3 4\n5 6\n7 8\n", encoding="ascii")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("file symlinks are unavailable")

    with pytest.raises(ValidationError, match="symlink"):
        load_ims_file(link, expected_channel_count=2, sampling_rate_hz=20_000.0)


def test_ims_parser_rejects_file_changed_between_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "changed.txt"
    path.write_text("1 2\n3 4\n5 6\n7 8\n", encoding="ascii")
    original = ims._file_identity(path, max_file_bytes=ims.DEFAULT_MAX_IMS_FILE_BYTES)
    calls = 0

    def changed_identity(source: Path, *, max_file_bytes: int) -> ims.FileIdentity:
        nonlocal calls
        calls += 1
        if calls == 1:
            return original
        return replace(original, modification_time_ns=original.modification_time_ns + 1)

    monkeypatch.setattr(ims, "_file_identity", changed_identity)
    with pytest.raises(ValidationError, match="changed between parsing passes"):
        load_ims_file(path, expected_channel_count=2, sampling_rate_hz=20_000.0)

# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Atomic, inspectable, corruption-detecting model serialization."""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import stat
import struct
import tempfile
import zipfile
from contextlib import suppress
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, cast

import numpy as np

from .exceptions import SerializationError, ValidationError

if TYPE_CHECKING:
    from .api import MCIFTMonitor, SequenceMode
    from .types import FloatArray

SCHEMA_VERSION = 4
LEGACY_SCHEMA_VERSION = 3
LEGACY_MODEL_VERSION = "0.1.0.dev2"
MAX_COMPONENT_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_COMPRESSED_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 1_000.0
MAX_ARRAY_ELEMENTS = 1_000_000
MAX_ARRAY_DIMENSION = 256
MAX_NPY_HEADER_BYTES = 16 * 1024
EXPECTED_COMPONENTS = frozenset({"manifest.json", "arrays.npz", "checksums.json"})
BASE_ARRAYS = frozenset({"channel_scales", "reference_exchange", "edge_scales"})
CONVENTIONAL_ARRAYS = frozenset(
    {
        "conventional_rms_thresholds",
        "conventional_excess_kurtosis_thresholds",
        "conventional_crest_factor_thresholds",
    }
)
LEGACY_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "model_version",
        "processing_profile",
        "gate_profile",
        "node_metric_identifier",
        "calibration_sequence_mode",
        "sampling_rate_hz",
        "channel_names",
        "channel_units",
        "sigma_i",
        "sigma_omega",
        "global_threshold",
        "local_edge_threshold",
        "progression_slope_threshold",
        "g",
        "eta",
        "epsilon",
        "diagnostics",
        "warnings",
        "reference_window_count",
        "calibration_window_count",
        "minimum_reference_windows",
        "minimum_calibration_windows",
        "small_sample_override_used",
        "numpy_version_at_fit",
        "python_version_at_fit",
    }
)
EXPECTED_MANIFEST_FIELDS = LEGACY_MANIFEST_FIELDS | frozenset(
    {
        "conventional_feature_version",
        "conventional_numerical_floor",
        "conventional_thresholds_available",
    }
)


def save_monitor(monitor: MCIFTMonitor, path: Path) -> None:
    """Write a private temporary sibling and atomically install it."""
    target = path.absolute()
    _reject_existing_destination(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        with suppress(OSError):
            os.chmod(temporary, 0o700)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "model_version": monitor.model_version,
            "processing_profile": monitor.processing_profile,
            "gate_profile": monitor.gate_profile,
            "node_metric_identifier": monitor.node_metric_identifier,
            "calibration_sequence_mode": monitor.calibration_sequence_mode,
            "sampling_rate_hz": monitor.sampling_rate_hz,
            "channel_names": list(monitor.channel_names),
            "channel_units": list(monitor.channel_units),
            "sigma_i": monitor.sigma_i,
            "sigma_omega": monitor.sigma_omega,
            "global_threshold": monitor.global_threshold,
            "local_edge_threshold": monitor.local_edge_threshold,
            "progression_slope_threshold": monitor.progression_slope_threshold,
            "conventional_feature_version": monitor.conventional_feature_version,
            "conventional_numerical_floor": monitor.conventional_numerical_floor,
            "conventional_thresholds_available": (
                monitor.conventional_rms_thresholds is not None
            ),
            "g": monitor.g,
            "eta": monitor.eta,
            "epsilon": monitor.epsilon,
            "diagnostics": list(monitor.diagnostics),
            "warnings": list(monitor.warnings),
            "reference_window_count": monitor.reference_window_count,
            "calibration_window_count": monitor.calibration_window_count,
            "minimum_reference_windows": monitor.minimum_reference_windows,
            "minimum_calibration_windows": monitor.minimum_calibration_windows,
            "small_sample_override_used": monitor.small_sample_override_used,
            "numpy_version_at_fit": monitor.numpy_version_at_fit,
            "python_version_at_fit": monitor.python_version_at_fit,
        }
        manifest_path = temporary / "manifest.json"
        arrays_path = temporary / "arrays.npz"
        checksums_path = temporary / "checksums.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        arrays: dict[str, FloatArray] = {
            "channel_scales": monitor.channel_scales,
            "reference_exchange": monitor.reference_exchange,
            "edge_scales": monitor.edge_scales,
        }
        if monitor.conventional_rms_thresholds is not None:
            kurtosis_thresholds = monitor.conventional_excess_kurtosis_thresholds
            crest_thresholds = monitor.conventional_crest_factor_thresholds
            if kurtosis_thresholds is None or crest_thresholds is None:
                raise SerializationError("conventional threshold state is inconsistent")
            arrays.update(
                {
                    "conventional_rms_thresholds": monitor.conventional_rms_thresholds,
                    "conventional_excess_kurtosis_thresholds": kurtosis_thresholds,
                    "conventional_crest_factor_thresholds": crest_thresholds,
                }
            )
        np.savez(arrays_path, **cast(dict[str, Any], arrays))
        checksums = {"manifest.json": _sha256(manifest_path), "arrays.npz": _sha256(arrays_path)}
        checksums_path.write_text(
            json.dumps(checksums, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        for component in (manifest_path, arrays_path, checksums_path):
            _fsync_file(component)
        _fsync_directory(temporary)
        _reject_existing_destination(target)
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    except Exception as error:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
        if isinstance(error, SerializationError):
            raise
        raise SerializationError("failed to save model atomically") from error


def load_monitor(path: Path) -> MCIFTMonitor:
    """Verify and load a model bundle using ``allow_pickle=False``."""
    from .api import MODEL_VERSION, MCIFTMonitor
    from .profiles import GATE_PROFILE_ID
    from .vibration_features import CONVENTIONAL_FEATURE_VERSION, DEFAULT_NUMERICAL_FLOOR

    target = path.absolute()
    _require_regular_bundle_directory(target)
    actual_components = frozenset(item.name for item in target.iterdir())
    if actual_components != EXPECTED_COMPONENTS:
        raise SerializationError("model bundle contains missing or unexpected components")
    component_paths = {name: target / name for name in EXPECTED_COMPONENTS}
    for component in component_paths.values():
        _require_regular_component(component)
    checksums = _read_json(component_paths["checksums.json"])
    if set(checksums) != {"manifest.json", "arrays.npz"}:
        raise SerializationError("checksum manifest has unexpected fields")
    for name in ("manifest.json", "arrays.npz"):
        checksum = checksums[name]
        if not isinstance(checksum, str) or _sha256(component_paths[name]) != checksum:
            raise SerializationError(f"checksum verification failed for {name}")
    manifest = _read_json(component_paths["manifest.json"])
    schema_version = _required_int(manifest.get("schema_version"), "schema_version", minimum=1)
    migrated_legacy = schema_version == LEGACY_SCHEMA_VERSION
    if schema_version == SCHEMA_VERSION:
        expected_manifest_fields = EXPECTED_MANIFEST_FIELDS
        if manifest.get("model_version") != MODEL_VERSION:
            raise SerializationError("unsupported package/model version")
    elif migrated_legacy:
        expected_manifest_fields = LEGACY_MANIFEST_FIELDS
        if manifest.get("model_version") != LEGACY_MODEL_VERSION:
            raise SerializationError("unsupported legacy package/model version")
        if manifest.get("gate_profile") != GATE_PROFILE_ID:
            raise SerializationError("legacy schema supports only exchange-screening models")
    else:
        raise SerializationError(
            "unsupported model schema version; schemas before 3 require explicit external migration"
        )
    if set(manifest) != expected_manifest_fields:
        raise SerializationError("manifest contains missing or unknown critical fields")
    channel_names = _string_list(manifest["channel_names"], "channel_names")
    channel_units = _string_list(manifest["channel_units"], "channel_units")
    if len(channel_names) != len(channel_units) or len(channel_names) < 2:
        raise SerializationError("manifest channel metadata is inconsistent")
    expected_shapes = {
        "channel_scales.npy": (len(channel_names),),
        "reference_exchange.npy": (len(channel_names), len(channel_names)),
        "edge_scales.npy": (len(channel_names), len(channel_names)),
    }
    thresholds_available = False
    if not migrated_legacy:
        thresholds_available = _required_bool(
            manifest["conventional_thresholds_available"],
            "conventional_thresholds_available",
        )
    if thresholds_available:
        expected_shapes.update(
            {
                f"{name}.npy": (len(channel_names),) for name in CONVENTIONAL_ARRAYS
            }
        )
    _inspect_npz(component_paths["arrays.npz"], expected_shapes=expected_shapes)
    expected_arrays = frozenset(name.removesuffix(".npy") for name in expected_shapes)
    try:
        with np.load(component_paths["arrays.npz"], allow_pickle=False) as archive:
            if set(archive.files) != expected_arrays:
                raise SerializationError("array archive contains unexpected fields")
            arrays = {
                name: np.array(archive[name], dtype=np.float64, copy=True) for name in archive.files
            }
    except (OSError, ValueError, TypeError, zipfile.BadZipFile) as error:
        raise SerializationError("array archive is malformed") from error
    warnings = _string_list(manifest["warnings"], "warnings", allow_empty=True)
    numpy_fit = _required_string(manifest["numpy_version_at_fit"], "numpy_version_at_fit")
    python_fit = _required_string(manifest["python_version_at_fit"], "python_version_at_fit")
    runtime_warnings = list(warnings)
    if numpy_fit != np.__version__:
        runtime_warnings.append(
            f"NumPy runtime version {np.__version__} differs from fit version {numpy_fit}."
        )
    if python_fit != platform.python_version():
        runtime_warnings.append(
            f"Python runtime version {platform.python_version()} differs from fit "
            f"version {python_fit}."
        )
    sequence_mode_text = _required_string(
        manifest["calibration_sequence_mode"], "calibration_sequence_mode"
    )
    if sequence_mode_text not in ("unordered", "chronological"):
        raise SerializationError("calibration sequence mode is invalid")
    sequence_mode = cast("SequenceMode", sequence_mode_text)
    diagnostics = list(_string_list(manifest["diagnostics"], "diagnostics", allow_empty=True))
    if migrated_legacy:
        diagnostics.append(
            "serialization_migration:schema3_to_schema4:conventional_gate_unavailable"
        )
    conventional_feature_version = (
        CONVENTIONAL_FEATURE_VERSION
        if migrated_legacy
        else _required_string(
            manifest["conventional_feature_version"], "conventional_feature_version"
        )
    )
    conventional_numerical_floor = (
        DEFAULT_NUMERICAL_FLOOR
        if migrated_legacy
        else _required_float(
            manifest["conventional_numerical_floor"], "conventional_numerical_floor"
        )
    )
    try:
        return MCIFTMonitor(
            sampling_rate_hz=float(manifest["sampling_rate_hz"]),
            channel_names=channel_names,
            channel_units=channel_units,
            channel_scales=arrays["channel_scales"],
            sigma_i=float(manifest["sigma_i"]),
            sigma_omega=float(manifest["sigma_omega"]),
            reference_exchange=arrays["reference_exchange"],
            edge_scales=arrays["edge_scales"],
            processing_profile=_required_string(
                manifest["processing_profile"], "processing_profile"
            ),
            gate_profile_version=_required_string(manifest["gate_profile"], "gate_profile"),
            node_metric_identifier=_required_string(
                manifest["node_metric_identifier"], "node_metric_identifier"
            ),
            calibration_sequence_mode=sequence_mode,
            global_threshold=_optional_float(manifest["global_threshold"]),
            local_edge_threshold=_optional_float(manifest["local_edge_threshold"]),
            progression_slope_threshold=_optional_float(manifest["progression_slope_threshold"]),
            conventional_rms_thresholds=arrays.get("conventional_rms_thresholds"),
            conventional_excess_kurtosis_thresholds=arrays.get(
                "conventional_excess_kurtosis_thresholds"
            ),
            conventional_crest_factor_thresholds=arrays.get(
                "conventional_crest_factor_thresholds"
            ),
            conventional_feature_version=conventional_feature_version,
            conventional_numerical_floor=conventional_numerical_floor,
            g=float(manifest["g"]),
            eta=float(manifest["eta"]),
            epsilon=float(manifest["epsilon"]),
            model_version=(
                MODEL_VERSION
                if migrated_legacy
                else _required_string(manifest["model_version"], "model_version")
            ),
            diagnostics=tuple(dict.fromkeys(diagnostics)),
            warnings=tuple(dict.fromkeys(runtime_warnings)),
            reference_window_count=_required_int(
                manifest["reference_window_count"], "reference_window_count", minimum=0
            ),
            calibration_window_count=_required_int(
                manifest["calibration_window_count"], "calibration_window_count", minimum=0
            ),
            minimum_reference_windows=_required_int(
                manifest["minimum_reference_windows"], "minimum_reference_windows", minimum=1
            ),
            minimum_calibration_windows=_required_int(
                manifest["minimum_calibration_windows"], "minimum_calibration_windows", minimum=1
            ),
            small_sample_override_used=_required_bool(
                manifest["small_sample_override_used"], "small_sample_override_used"
            ),
            numpy_version_at_fit=numpy_fit,
            python_version_at_fit=python_fit,
        )
    except (TypeError, ValueError, KeyError, ValidationError) as error:
        raise SerializationError(f"model metadata or arrays are invalid: {error}") from error


def _inspect_npz(path: Path, *, expected_shapes: dict[str, tuple[int, ...]]) -> None:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise SerializationError("array archive contains duplicate member names")
            for info in infos:
                _validate_archive_member_path(info.filename)
            if frozenset(names) != frozenset(expected_shapes):
                raise SerializationError("array archive contains unexpected members")
            compressed = sum(info.compress_size for info in infos)
            uncompressed = sum(info.file_size for info in infos)
            if compressed > MAX_ARCHIVE_COMPRESSED_BYTES:
                raise SerializationError("array archive exceeds compressed byte limit")
            if uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise SerializationError("array archive exceeds uncompressed byte limit")
            for info in infos:
                mode = info.external_attr >> 16
                if info.is_dir() or info.flag_bits & 0x1 or stat.S_ISLNK(mode):
                    raise SerializationError("array archive member is not a plain file")
                if info.file_size / max(1, info.compress_size) > MAX_ARCHIVE_COMPRESSION_RATIO:
                    raise SerializationError("array archive compression ratio is excessive")
                with archive.open(info, "r") as stream:
                    shape, dtype, payload_offset = _read_npy_header(stream)
                if dtype.hasobject:
                    raise SerializationError("object arrays are forbidden")
                if dtype != np.dtype(np.float64):
                    raise SerializationError("model arrays must use float64 dtype")
                if len(shape) > 2 or any(
                    dimension < 0 or dimension > MAX_ARRAY_DIMENSION for dimension in shape
                ):
                    raise SerializationError("array dimensions exceed permitted limits")
                elements = int(np.prod(shape, dtype=np.int64))
                if elements > MAX_ARRAY_ELEMENTS:
                    raise SerializationError("array exceeds element limit")
                if shape != expected_shapes[info.filename]:
                    raise SerializationError("array shape does not match manifest channel metadata")
                expected_payload = elements * dtype.itemsize
                if info.file_size - payload_offset != expected_payload:
                    raise SerializationError("array payload size does not match declared shape")
    except zipfile.BadZipFile as error:
        raise SerializationError("array archive is malformed") from error


def _validate_archive_member_path(name: str) -> None:
    if name.startswith(("/", "\\")) or (len(name) >= 2 and name[1] == ":"):
        raise SerializationError("array archive contains an absolute member path")
    if "\\" in name:
        raise SerializationError("array archive member paths must use safe separators")
    parts = PurePosixPath(name).parts
    if ".." in parts:
        raise SerializationError("array archive member path contains traversal")
    if len(parts) != 1:
        raise SerializationError("array archive contains a nested member path")


def _read_npy_header(stream: Any) -> tuple[tuple[int, ...], np.dtype[Any], int]:
    prefix = stream.read(8)
    if len(prefix) != 8 or prefix[:6] != b"\x93NUMPY":
        raise SerializationError("array member has an invalid NPY header")
    version = (prefix[6], prefix[7])
    length_size = 2 if version == (1, 0) else 4 if version in ((2, 0), (3, 0)) else 0
    if length_size == 0:
        raise SerializationError("unsupported NPY member version")
    encoded_length = stream.read(length_size)
    if len(encoded_length) != length_size:
        raise SerializationError("array member has a truncated NPY header")
    header_length = struct.unpack("<H" if length_size == 2 else "<I", encoded_length)[0]
    if header_length > MAX_NPY_HEADER_BYTES:
        raise SerializationError("array member NPY header exceeds size limit")
    header = stream.read(header_length)
    if len(header) != header_length:
        raise SerializationError("array member has a truncated NPY header")
    encoded = io.BytesIO(prefix + encoded_length + header)
    try:
        parsed_version = np.lib.format.read_magic(encoded)
        if parsed_version == (1, 0):
            shape, _, dtype = np.lib.format.read_array_header_1_0(encoded)
        else:
            shape, _, dtype = np.lib.format.read_array_header_2_0(encoded)
    except (ValueError, UnicodeError, SyntaxError) as error:
        raise SerializationError("array member has an invalid NPY header") from error
    return tuple(int(dimension) for dimension in shape), dtype, 8 + length_size + header_length


def _reject_existing_destination(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    except OSError as error:
        raise SerializationError("cannot inspect model destination") from error
    if stat.S_ISLNK(metadata.st_mode):
        raise SerializationError("model destination must not be a symlink")
    raise SerializationError("model destination already exists")


def _require_regular_bundle_directory(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise SerializationError("model path is unavailable") from error
    if stat.S_ISLNK(metadata.st_mode):
        raise SerializationError("model path must not be a symlink")
    if not stat.S_ISDIR(metadata.st_mode):
        raise SerializationError("model path must be a directory")


def _require_regular_component(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise SerializationError("model component is unavailable") from error
    if stat.S_ISLNK(metadata.st_mode):
        raise SerializationError("model component must not be a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise SerializationError("model component must be a regular file")
    if metadata.st_size > MAX_COMPONENT_BYTES:
        raise SerializationError("model component exceeds size limit")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SerializationError(f"invalid JSON component: {path.name}") from error
    if not isinstance(value, dict):
        raise SerializationError(f"JSON component must be an object: {path.name}")
    return value


def _required_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise SerializationError(f"{name} must be a non-empty string")
    return value


def _string_list(value: object, name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or any(not isinstance(item, str) for item in value)
    ):
        raise SerializationError(f"{name} must be a list of strings")
    return tuple(value)


def _required_int(value: object, name: str, *, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        raise SerializationError(f"{name} must be an integer of at least {minimum}")
    return value


def _required_bool(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise SerializationError(f"{name} must be a boolean")
    return value


def _required_float(value: object, name: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise SerializationError(f"{name} must be numeric")
    result = float(value)
    if not np.isfinite(result):
        raise SerializationError(f"{name} must be finite")
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fsync_file(path: Path) -> None:
    with path.open("r+b") as stream:
        stream.flush()
        os.fsync(stream.fileno())


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise SerializationError("optional threshold must be numeric or null")
    return float(value)

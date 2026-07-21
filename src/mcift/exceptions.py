# Copyright (C) 2026 Martin Kasala
# SPDX-License-Identifier: AGPL-3.0-only

"""Package-specific exceptions."""


class MCIFTError(Exception):
    """Base class for package errors."""


class ValidationError(MCIFTError, ValueError):
    """Raised when untrusted input violates the public data contract."""


class CalibrationError(MCIFTError, RuntimeError):
    """Raised when evaluation requires calibration that is not available."""


class SerializationError(MCIFTError, OSError):
    """Raised when a model bundle is malformed or fails integrity checks."""

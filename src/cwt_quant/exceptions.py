"""Custom exceptions for clear fail-fast behaviour."""

from __future__ import annotations


class CWTQuantError(Exception):
    """Base for all package errors."""


class ConfigError(CWTQuantError):
    """Invalid or inconsistent configuration."""


class DataError(CWTQuantError):
    """Missing, malformed, or insufficient input data."""


class CalendarError(CWTQuantError):
    """Session mapping or exchange calendar failure."""


class LeakageError(CWTQuantError):
    """Detected or potential look-ahead / point-in-time violation."""


class CoverageError(CWTQuantError):
    """Influence or feature coverage gate not satisfied."""


class ProvenanceError(CWTQuantError):
    """Missing or inconsistent source hashes / timestamps."""

"""
CWT Quant — research-grade, leakage-safe daily equity + X-sentiment forecasting.

Status: EXPERIMENTAL / PRE-CODEX reference implementation.
"""

from .config import Config, PACKAGE_VERSION

__version__ = PACKAGE_VERSION
__status__ = "EXPERIMENTAL / PRE-CODEX"

from .calendar import XNYSCalendar
from .pipeline import run_pipeline
from .exceptions import (
    CWTQuantError,
    ConfigError,
    DataError,
    CalendarError,
    LeakageError,
    CoverageError,
    ProvenanceError,
)

__all__ = [
    "Config",
    "XNYSCalendar",
    "run_pipeline",
    "CWTQuantError",
    "ConfigError",
    "DataError",
    "CalendarError",
    "LeakageError",
    "CoverageError",
    "ProvenanceError",
    "__version__",
]

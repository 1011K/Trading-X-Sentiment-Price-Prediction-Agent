"""
CWT Quant — research-grade, leakage-safe daily equity + X-sentiment forecasting.

Status: EXPERIMENTAL / PRE-CODEX reference implementation.
"""

__version__ = "0.1.1-experimental"
__status__ = "EXPERIMENTAL / PRE-CODEX"

from .config import Config
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

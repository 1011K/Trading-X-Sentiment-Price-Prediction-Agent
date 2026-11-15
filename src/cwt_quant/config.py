"""Central configuration. All research decisions live here."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .exceptions import ConfigError

PACKAGE_VERSION = "0.1.3-experimental"


@dataclass(frozen=True)
class Config:
    # ---- Universe & horizon ----
    ticker: str = "AAPL"
    exchange: str = "XNYS"
    history_calendar_days: int = 180
    forecast_horizons: List[int] = field(default_factory=lambda: [1, 2, 3, 4, 5])

    # ---- Session mapping ----
    assign_exact_close_to_next: bool = True

    # ---- Sentiment ----
    use_lexical_sentiment: bool = True
    allow_prescored_sentiment: bool = False  # require verified as-of score provenance before enabling
    reply_weight: float = 0.4
    post_weight: float = 0.6

    # ---- Influence (EXPERIMENTAL) ----
    enable_influence: bool = True
    min_posts_for_sentiment: int = 30
    min_sessions_with_sentiment: int = 20
    min_posts_for_influence: int = 50
    min_sessions_with_posts: int = 20
    reach_cap_followers: float = 1_000_000.0
    engagement_cap: float = 10_000.0
    reach_coef: float = 0.3
    engagement_coef: float = 0.2
    weight_cap: float = 1.5

    # ---- Author / spam controls ----
    max_posts_per_author_per_session: int = 3  # cap repeated known authors

    # ---- Models ----
    ridge_alpha: float = 10.0
    use_standard_scaler: bool = True

    # ---- Walk-forward / leakage ----
    min_train_sessions: int = 40
    expanding_window: bool = True

    # ---- Missing data policy ----
    # Fail fast on missing price sessions (halts / outages) rather than silently
    # treating adjacent bars as consecutive.
    fail_on_missing_sessions: bool = False
    max_allowed_missing_sessions: int = 2  # soft audit threshold before hard fail

    # ---- Trading diagnostic ----
    diagnostic_roundtrip_cost_bps: float = 10.0
    report_trading_diagnostic: bool = True

    # ---- Paths & reproducibility ----
    seed: int = 42
    fixtures_dir: Path = Path("fixtures")
    outputs_dir: Path = Path("outputs")
    require_source_hashes: bool = True
    log_level: str = "INFO"

    # ---- Honesty flags ----
    real_data_present: bool = False
    claim_predictive_skill: bool = False

    def validate(self) -> None:
        errors: List[str] = []

        if not self.ticker or not isinstance(self.ticker, str):
            errors.append("ticker must be a non-empty string")
        if self.exchange != "XNYS":
            errors.append("only XNYS is supported in this reference release")
        if self.history_calendar_days < 30:
            errors.append("history_calendar_days must be >= 30")
        if not self.forecast_horizons:
            errors.append("forecast_horizons cannot be empty")
        if any(h < 1 for h in self.forecast_horizons):
            errors.append("all horizons must be >= 1")
        if max(self.forecast_horizons) > 20:
            errors.append("horizons > 20 are unreasonable for 180-day sample")
        if abs(self.post_weight + self.reply_weight - 1.0) > 1e-9:
            errors.append("post_weight + reply_weight must equal 1.0")
        if not (0.0 <= self.reply_weight <= 1.0):
            errors.append("reply_weight must be in [0, 1]")
        if self.ridge_alpha <= 0:
            errors.append("ridge_alpha must be > 0")
        if self.min_train_sessions < 20:
            errors.append("min_train_sessions too small for Ridge stability (< 20)")
        if self.min_posts_for_sentiment < 1 or self.min_sessions_with_sentiment < 1:
            errors.append("sentiment coverage thresholds must be positive")
        if self.min_posts_for_influence < 10:
            errors.append("min_posts_for_influence too low")
        if self.weight_cap < 1.0:
            errors.append("weight_cap must be >= 1.0")
        if self.diagnostic_roundtrip_cost_bps < 0:
            errors.append("diagnostic_roundtrip_cost_bps cannot be negative")
        if self.max_posts_per_author_per_session < 1:
            errors.append("max_posts_per_author_per_session must be >= 1")
        if self.claim_predictive_skill and not self.real_data_present:
            errors.append(
                "claim_predictive_skill=True is forbidden while real_data_present=False"
            )
        if self.log_level.upper() not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            errors.append(f"invalid log_level: {self.log_level}")

        if errors:
            raise ConfigError("Config validation failed:\n  - " + "\n  - ".join(errors))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["fixtures_dir"] = str(self.fixtures_dir)
        d["outputs_dir"] = str(self.outputs_dir)
        return d

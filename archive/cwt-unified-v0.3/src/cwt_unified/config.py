from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    ticker: str = "AAPL"
    exchange_calendar: str = "XNYS"
    history_days: int = 180  # calendar days, not 180 observations
    horizons: tuple[int, ...] = (1, 2, 3, 4, 5)
    min_train_rows: int = 40
    min_bars: int = 85
    first_test_fraction: float = 0.65
    ridge_alpha: float = 10.0  # fixed a priori, not fitted on held-out dates
    max_author_posts_per_day: int = 3
    allow_influence: bool = False  # true only with point-in-time engagement snapshots
    round_trip_cost_bps: float = 20.0  # total for entry + exit; assumption, not calibrated

    def __post_init__(self):
        if self.history_days < 40 or self.min_train_rows < 20 or not (0.5 <= self.first_test_fraction < 0.9):
            raise ValueError("Invalid training/data configuration")
        if self.round_trip_cost_bps < 0:
            raise ValueError("Transaction cost cannot be negative")

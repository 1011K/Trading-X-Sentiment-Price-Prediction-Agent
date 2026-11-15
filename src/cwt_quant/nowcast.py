"""An independent, price-only n+0 benchmark with an opening-time origin."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from .calendar import XNYSCalendar
from .config import Config
from .models import RidgeModel


def open_nowcasts(prices: pd.DataFrame, cfg: Config, start: date) -> pd.DataFrame:
    """Forecast the current day's close using the opening print and earlier sessions."""
    previous_close = prices["close"].shift(1)
    previous_return = np.log(prices["close"]).diff()
    features = pd.DataFrame({
        "opening_gap": np.log(prices["open"] / previous_close),
        "prior_return": previous_return.shift(1),
        "prior_week_return": np.log(prices["close"] / prices["close"].shift(5)).shift(1),
        "prior_volatility": previous_return.rolling(10, min_periods=5).std().shift(1),
    }, index=prices.index)
    realized = np.log(prices["close"] / prices["open"])
    complete = np.isfinite(features).all(axis=1) & np.isfinite(realized)
    calendar = XNYSCalendar()
    rows = []
    for i, (day, opening, close) in enumerate(
        prices[["session_date", "open", "close"]].itertuples(index=False, name=None)
    ):
        if day < start or not np.isfinite(features.iloc[i]).all():
            continue
        # Prior same-session targets had already settled before today's open.
        train = complete.iloc[:i]
        if train.sum() < cfg.min_train_sessions:
            continue
        model = RidgeModel(alpha=cfg.ridge_alpha, use_scaler=cfg.use_standard_scaler)
        model.fit(features.iloc[:i].loc[train], realized.iloc[:i].loc[train])
        ridge = float(model.predict(features.iloc[[i]])[0])
        for name, estimate in (("no_change", 0.0), ("price_only", ridge)):
            rows.append({
                "origin": calendar.session_open_dt(day), "target_session": day,
                "model": name, "horizon": 0, "kind": "forecast_at_open",
                "open_t": float(opening), "forecast_close": float(opening * np.exp(estimate)),
                "actual_close": float(close), "y_hat": estimate, "y_true": float(realized.iloc[i]),
            })
    return pd.DataFrame(rows)

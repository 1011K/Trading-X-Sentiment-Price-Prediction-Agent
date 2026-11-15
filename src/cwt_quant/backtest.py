"""
Leakage-safe walk-forward evaluation.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List

import numpy as np
import pandas as pd

from .calendar import XNYSCalendar
from .config import Config
from .exceptions import DataError, LeakageError
from .logging_utils import get_logger
from .models import NoChangeModel, RidgeModel, get_feature_sets
from .validation import assert_no_future_labels

log = get_logger(__name__)


class TradingFillError(DataError):
    """A dated fill failure that withholds the entire risk calculation."""

    def __init__(self, session: date, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.issues = [{"session_date": session.isoformat(), "reason": reason, "detail": detail}]


def walk_forward(
    panel: pd.DataFrame,
    cfg: Config,
    enable_influence: bool = False,
    enable_sentiment: bool = True,
    model_start_dates: dict[str, date] | None = None,
) -> Dict[str, pd.DataFrame]:
    """
    Expanding-window walk-forward.

    For each test origin t and horizon h:
      - train only on origins i where i + h <= t (label already known)
      - features at i use only information available at i
    """
    if panel is None or panel.empty:
        raise DataError("Cannot run walk-forward on empty panel")
    if (
        not isinstance(panel.index, pd.DatetimeIndex) or not panel.index.is_unique
        or not panel.index.is_monotonic_increasing
    ):
        raise DataError("Walk-forward requires unique, chronological session timestamps")

    feature_sets = get_feature_sets(cfg)
    model_start_dates = model_start_dates or {}
    if not enable_sentiment:
        feature_sets.pop("price_sentiment", None)
    if not enable_influence:
        feature_sets.pop("price_influence", None)

    horizons = cfg.forecast_horizons
    results: Dict[str, List[dict]] = {name: [] for name in ["no_change"] + list(feature_sets)}

    max_h = max(horizons)
    if len(panel) <= max_h + cfg.min_train_sessions:
        raise DataError(
            f"Panel length {len(panel)} insufficient for max_h={max_h} "
            f"and min_train={cfg.min_train_sessions}"
        )

    valid_idx = panel.index[:-max_h]
    log.info(
        "Walk-forward: %d candidate origins, horizons=%s, influence=%s",
        len(valid_idx),
        horizons,
        enable_influence,
    )

    for t_idx, t in enumerate(valid_idx):
        if t_idx < cfg.min_train_sessions:
            continue

        for h in horizons:
            ycol = f"y_{h}"
            if ycol not in panel.columns:
                continue

            train_mask = np.arange(len(panel)) + h <= t_idx
            train_mask = train_mask & panel[ycol].notna().values
            train_mask[t_idx:] = False

            if train_mask.sum() < cfg.min_train_sessions:
                continue

            train = panel.iloc[train_mask]
            test_row = panel.loc[[t]]

            # Hard leakage check
            try:
                assert_no_future_labels(train.index, t, h)
            except LeakageError:
                log.error("Leakage guard triggered at origin %s h=%d", t, h)
                raise

            y_true = test_row[ycol].iloc[0]
            if np.isnan(y_true):
                continue

            results["no_change"].append(
                {
                    "origin": t,
                    "horizon": h,
                    "y_true": y_true,
                    "y_hat": 0.0,
                    "close_t": float(test_row["close"].iloc[0]),
                }
            )

            for name, feats in feature_sets.items():
                start_date = model_start_dates.get(name)
                if start_date is not None and t.date() < start_date:
                    continue
                usable = [
                    f for f in feats
                    if f in train.columns and train[f].notna().any()
                ]
                if not usable:
                    continue
                X_train = train[usable].fillna(0.0)
                y_train = train[ycol]
                X_test = test_row[usable].fillna(0.0)

                try:
                    model = RidgeModel(
                        alpha=cfg.ridge_alpha, use_scaler=cfg.use_standard_scaler
                    )
                    model.fit(X_train, y_train)
                    y_hat = float(model.predict(X_test)[0])
                except Exception as exc:
                    log.warning("Ridge fit/predict failed for %s h=%d: %s", name, h, exc)
                    continue

                results[name].append(
                    {
                        "origin": t,
                        "horizon": h,
                        "y_true": y_true,
                        "y_hat": y_hat,
                        "close_t": float(test_row["close"].iloc[0]),
                    }
                )

    out = {}
    for name, rows in results.items():
        out[name] = (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(columns=["origin", "horizon", "y_true", "y_hat", "close_t"])
        )
        log.info("Model %s produced %d predictions", name, len(out[name]))
    return out


def trading_diagnostic(
    preds: pd.DataFrame,
    panel: pd.DataFrame,
    cfg: Config,
) -> pd.DataFrame:
    """Trade a close-to-close forecast signal at the next XNYS open and close."""
    if preds is None or preds.empty or not cfg.report_trading_diagnostic:
        return pd.DataFrame()

    if not preds.columns.is_unique or not {"horizon", "origin", "y_hat"}.issubset(preds):
        raise DataError("Trading diagnostic requires unique horizon, origin and y_hat columns")
    p1 = preds.loc[preds["horizon"].eq(1), ["origin", "y_hat"]].copy()
    if p1.empty:
        return pd.DataFrame()

    cal = XNYSCalendar()
    if not isinstance(panel.index, pd.DatetimeIndex) or panel.index.tz is None:
        raise DataError("Trading bars require a timezone-aware XNYS session-close index")
    bar_dates = pd.Index(panel.index.tz_convert(cal.tz).date)
    if bar_dates.hasnans or bar_dates.has_duplicates:
        raise DataError("Trading bars contain a missing or duplicate session date")
    if not panel.columns.is_unique or not {"open", "close"}.issubset(panel):
        raise DataError("Trading bars require unique open and close price columns")
    origins = pd.Index(p1["origin"])
    if not isinstance(origins, pd.DatetimeIndex) or origins.tz is None or origins.hasnans:
        raise DataError("Trading signals require timezone-aware session-close origins")
    p1["origin"] = origins.tz_convert(cal.tz)
    if p1["origin"].duplicated().any():
        raise DataError("Trading signals contain duplicate origins")
    p1["y_hat"] = pd.to_numeric(p1["y_hat"], errors="coerce")
    if not np.isfinite(p1["y_hat"].to_numpy(dtype=float, na_value=np.nan)).all():
        raise DataError("Trading signals contain a nonfinite forecast")

    records = []
    cost = cfg.diagnostic_roundtrip_cost_bps / 10_000.0
    if not np.isfinite(cost) or cost < 0:
        raise DataError("Trading cost must be finite and nonnegative")

    equity = 1.0
    previous_fill = None
    for origin, y_hat in p1.sort_values("origin").itertuples(index=False, name=None):
        origin_date = origin.date()
        try:
            signal_close = cal.session_close_dt(origin_date)
            fill_date = cal.next_trading_day(origin_date)
        except ValueError as exc:
            raise DataError(str(exc)) from exc
        if origin != signal_close or origin not in panel.index:
            raise DataError(f"Trading origin {origin} does not match a priced XNYS close")
        if previous_fill is not None and previous_fill != origin_date:
            raise DataError(f"Trading signals have a gap at XNYS session {previous_fill}")

        session_open = cal.session_open_dt(fill_date)
        session_close = cal.session_close_dt(fill_date)
        if session_close not in panel.index:
            raise TradingFillError(
                fill_date, "missing_fill_bar", f"Trading fill missing for next XNYS session {fill_date}",
            )
        prices = pd.to_numeric(panel.loc[session_close, ["open", "close"]], errors="coerce")
        open_price, close_price = prices.to_numpy(dtype=float, na_value=np.nan)
        if not np.isfinite([open_price, close_price]).all() or min(open_price, close_price) <= 0:
            raise TradingFillError(
                fill_date, "invalid_fill_prices", f"Trading fill prices must be finite and positive on {fill_date}",
            )

        position = int(y_hat > 0)
        raw_ret = float(close_price) / float(open_price) - 1.0
        charged_cost = cost * position
        net_ret = raw_ret - charged_cost if position else 0.0
        equity *= 1.0 + net_ret
        if not np.isfinite([raw_ret, equity]).all() or equity <= 0:
            raise DataError(f"Trading return or equity is invalid on {fill_date}")
        records.append(
            {
                "origin": origin,
                "horizon": 1,
                "y_hat": y_hat,
                "fill_date": fill_date,
                "session_open": session_open,
                "session_close": session_close,
                "open_price": open_price,
                "close_price": close_price,
                "entry_at": session_open if position else pd.NaT,
                "exit_at": session_close if position else pd.NaT,
                "entry_price": open_price if position else np.nan,
                "exit_price": close_price if position else np.nan,
                "signal": position,
                "position": position,
                "raw_oc_ret": raw_ret,
                "gross_ret": raw_ret if position else 0.0,
                "cost": charged_cost,
                "cash_ret": 0.0,
                "net_ret": net_ret,
                "equity": equity,
            }
        )
        previous_fill = fill_date

    ledger = pd.DataFrame(records)
    ledger.attrs["roundtrip_cost_bps"] = cfg.diagnostic_roundtrip_cost_bps
    return ledger

"""Honest metrics. No cherry-picking."""

from __future__ import annotations

from math import isclose, isfinite
from typing import Dict

import numpy as np
import pandas as pd

from .calendar import XNYSCalendar
from .config import Config
from .exceptions import DataError


def forecast_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """MAE, RMSE, skill vs naïve (no-change), direction accuracy."""
    if df.empty or "y_true" not in df.columns:
        return {}
    y = df["y_true"].values
    yhat = df["y_hat"].values
    mae = float(np.mean(np.abs(y - yhat)))
    rmse = float(np.sqrt(np.mean((y - yhat) ** 2)))
    # Skill vs zero (no-change): 1 - MSE_model / MSE_naive
    mse_m = np.mean((y - yhat) ** 2)
    mse_n = np.mean(y ** 2)  # naïve predicts 0
    skill = 1.0 - (mse_m / mse_n) if mse_n > 0 else np.nan
    # Direction: only meaningful when model makes non-zero calls
    nonzero = np.abs(yhat) > 1e-12
    dir_acc = float(np.mean(np.sign(y[nonzero]) == np.sign(yhat[nonzero]))) if nonzero.any() else np.nan
    return {
        "n": len(df),
        "mae": mae,
        "rmse": rmse,
        "skill_vs_naive": skill,
        "direction_accuracy": dir_acc,
        "direction_call_fraction": float(np.mean(nonzero)),
    }


def summarize_by_horizon(preds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for h, g in preds.groupby("horizon"):
        m = forecast_metrics(g)
        m["horizon"] = h
        rows.append(m)
    return pd.DataFrame(rows)


def matched_predictions(predictions: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Return model predictions on the same finite OOS origin/horizon pairs."""
    keys = ["origin", "horizon"]
    values = ["y_true", "y_hat"]
    indexed = {}
    common = None
    for name, frame in predictions.items():
        if frame.empty:
            frame = frame.reindex(columns=list(dict.fromkeys([*frame.columns, *keys, *values])))
        if not set(keys + values).issubset(frame):
            raise DataError(f"Predictions for {name} lack required OOS fields")
        if frame[keys].isna().any().any() or frame.duplicated(keys).any():
            raise DataError(f"Predictions for {name} have missing or duplicate OOS keys")
        frame = frame.copy()
        frame[values] = frame[values].apply(pd.to_numeric, errors="coerce")
        finite = np.isfinite(frame[values].to_numpy(dtype=float, na_value=np.nan)).all(axis=1)
        indexed[name] = frame.loc[finite].set_index(keys)
        index = indexed[name].index
        common = index if common is None else common.intersection(index)

    if common is None:
        return {}
    common = common.sort_values()
    aligned = {name: frame.reindex(common).reset_index() for name, frame in indexed.items()}
    outcomes = [frame["y_true"].to_numpy() for frame in aligned.values()]
    if any(not np.array_equal(outcomes[0], other) for other in outcomes[1:]):
        raise DataError("Matched OOS predictions disagree on realized outcomes")
    return aligned


def _reconcile_daily_ledger(trades: pd.DataFrame, roundtrip_cost_bps: float) -> tuple[np.ndarray, ...]:
    required = {
        "origin", "horizon", "y_hat", "fill_date", "session_open", "session_close",
        "open_price", "close_price", "entry_at", "exit_at", "entry_price", "exit_price",
        "signal", "position", "raw_oc_ret", "gross_ret", "cost", "cash_ret", "net_ret", "equity",
    }
    if not trades.columns.is_unique or not required.issubset(trades):
        raise DataError("Trading ledger lacks unique daily fill and accounting fields")
    cost = float(roundtrip_cost_bps) / 10_000.0
    if not isfinite(cost) or cost < 0:
        raise DataError("Trading cost must be finite and nonnegative")

    cal = XNYSCalendar()
    previous_fill = None
    returns, positions, equity = [], [], [1.0]
    for row in trades.itertuples(index=False):
        origin = pd.Timestamp(row.origin)
        if pd.isna(origin) or origin.tzinfo is None or float(row.horizon) != 1:
            raise DataError("Trading ledger requires timezone-aware one-session signals")
        origin_day = origin.tz_convert(cal.tz).date()
        fill_day = cal.next_trading_day(origin_day)
        session_open = cal.session_open_dt(fill_day)
        session_close = cal.session_close_dt(fill_day)
        if (
            origin != cal.session_close_dt(origin_day)
            or (previous_fill is not None and previous_fill != origin_day)
            or str(row.fill_date) != fill_day.isoformat()
            or pd.Timestamp(row.session_open) != session_open
            or pd.Timestamp(row.session_close) != session_close
        ):
            raise DataError("Trading ledger is not a contiguous chronological next-session series")

        open_price, close_price, forecast = map(float, (row.open_price, row.close_price, row.y_hat))
        if not all(map(isfinite, (open_price, close_price, forecast))) or min(open_price, close_price) <= 0:
            raise DataError("Trading ledger has invalid prices or forecast")
        position = int(forecast > 0)
        if float(row.signal) != position or float(row.position) != position:
            raise DataError("Trading position does not reconcile with the forecast")
        if position:
            if (
                pd.Timestamp(row.entry_at) != session_open or pd.Timestamp(row.exit_at) != session_close
                or float(row.entry_price) != open_price or float(row.exit_price) != close_price
            ):
                raise DataError("Long-position fills do not reconcile with session prices and times")
        elif any(pd.notna(value) for value in (row.entry_at, row.exit_at, row.entry_price, row.exit_price)):
            raise DataError("Cash sessions must have no executed fills")

        raw_return = close_price / open_price - 1.0
        gross_return = raw_return if position else 0.0
        charged_cost = cost if position else 0.0
        net_return = gross_return - charged_cost
        balance = equity[-1] * (1.0 + net_return)
        expected = (raw_return, gross_return, charged_cost, 0.0, net_return, balance)
        actual = (row.raw_oc_ret, row.gross_ret, row.cost, row.cash_ret, row.net_ret, row.equity)
        if balance <= 0 or any(
            not isfinite(value) or not isclose(float(observed), value, rel_tol=1e-12, abs_tol=1e-14)
            for observed, value in zip(actual, expected)
        ):
            raise DataError("Trading ledger returns, costs, cash, or equity do not reconcile")
        returns.append(net_return)
        positions.append(position)
        equity.append(balance)
        previous_fill = fill_day
    return np.array(returns), np.array(positions), np.array(equity)


def trading_summary(
    trades: pd.DataFrame, *, roundtrip_cost_bps: float | None = None,
) -> dict[str, float | str | list[dict[str, str]]]:
    """Summarize reconciled XNYS session returns, including cash periods."""
    result = {
        "n_sessions": 0,
        "n_trades": 0,
        "n_cash_sessions": "WITHHELD",
        "mean_net_ret": "WITHHELD",
        "cumulative_net_ret": "WITHHELD",
        "hit_rate": "WITHHELD",
        "approx_sharpe": "WITHHELD",
        "approx_sortino": "WITHHELD",
        "max_drawdown": "WITHHELD",
        "note": "Hypothetical intraday fills. Excludes capacity, taxes and overnight exposure.",
    }
    if trades.empty:
        result["withheld_reason"] = trades.attrs.get("withheld_reason", "No eligible daily sessions")
        if trades.attrs.get("fill_issues"):
            result["fill_issues"] = trades.attrs["fill_issues"]
        return result

    cost = (
        trades.attrs.get("roundtrip_cost_bps", Config.diagnostic_roundtrip_cost_bps)
        if roundtrip_cost_bps is None else roundtrip_cost_bps
    )
    try:
        rets, positions, equity = _reconcile_daily_ledger(trades, cost)
    except DataError as exc:
        result["withheld_reason"] = str(exc)
        return result
    except (ValueError, TypeError, OverflowError):
        result["withheld_reason"] = "Trading ledger contains a malformed timestamp or number"
        return result

    active = positions == 1
    mean = float(np.mean(rets))
    result.update(
        n_sessions=len(rets),
        n_trades=int(np.count_nonzero(active)),
        n_cash_sessions=int(np.count_nonzero(~active)),
        first_fill_session=str(trades["fill_date"].iloc[0]),
        last_fill_session=str(trades["fill_date"].iloc[-1]),
        mean_net_ret=mean,
        cumulative_net_ret=float(equity[-1] - 1.0),
        max_drawdown=float(np.min(equity / np.maximum.accumulate(equity) - 1.0)),
    )
    if active.any():
        result["hit_rate"] = float(np.mean(rets[active] > 0))
    if len(rets) > 1:
        # Daily risk-free rate and downside target are both zero for this diagnostic.
        std = float(np.std(rets, ddof=1))
        downside = float(np.sqrt(np.mean(np.minimum(rets, 0.0) ** 2)))
        if std > 0:
            result["approx_sharpe"] = float(np.sqrt(252) * mean / std)
        if downside > 0:
            result["approx_sortino"] = float(np.sqrt(252) * mean / downside)
    return result

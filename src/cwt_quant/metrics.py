"""Honest metrics. No cherry-picking."""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

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


def trading_summary(trades: pd.DataFrame) -> Dict[str, float | str]:
    """Summarize chronological session returns, cash included in risk measures."""
    result = {
        "n_sessions": 0,
        "n_trades": 0,
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
        return result

    rets = trades["net_ret"].to_numpy(dtype=float)
    positions = trades["position"].to_numpy()
    equity = np.r_[1.0, trades["equity"].to_numpy(dtype=float)]
    if not np.isfinite(rets).all() or not np.isfinite(equity).all() or (equity <= 0).any():
        result["withheld_reason"] = "Invalid session return or equity"
        return result

    active = positions == 1
    mean = float(np.mean(rets))
    result.update(
        n_sessions=len(rets),
        n_trades=int(np.count_nonzero(active)),
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

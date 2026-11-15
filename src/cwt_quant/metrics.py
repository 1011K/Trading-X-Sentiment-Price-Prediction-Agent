"""Honest metrics. No cherry-picking."""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


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


def trading_summary(trades: pd.DataFrame) -> Dict[str, float]:
    if trades.empty:
        return {"n_trades": 0}
    rets = trades["net_ret"].values
    n = len(rets)
    mean = float(np.mean(rets))
    std = float(np.std(rets, ddof=1)) if n > 1 else 0.0
    sharpe = (mean / std * np.sqrt(252)) if std > 0 else np.nan  # rough daily
    hit = float(np.mean(rets > 0))
    return {
        "n_trades": n,
        "mean_net_ret": mean,
        "hit_rate": hit,
        "approx_sharpe": sharpe,
        "note": "IDEALIZED diagnostic only; overnight gaps, capacity, taxes unresolved",
    }

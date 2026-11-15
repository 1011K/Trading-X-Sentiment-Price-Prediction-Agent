"""
Forward valuation: produce n+1 … n+5 forecasts from the latest available origin.

This is the "working model" path for a personal research bot.
It reuses the same Ridge models trained under the leakage-safe walk-forward rules.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .config import Config
from .logging_utils import get_logger
from .models import RidgeModel, NoChangeModel, get_feature_sets

log = get_logger(__name__)


def fit_latest_models(
    panel: pd.DataFrame,
    cfg: Config,
    enable_influence: bool = False,
    enable_sentiment: bool = True,
) -> Dict[str, Dict[int, object]]:
    """
    For each horizon, fit models on all origins where the label is already known
    (i.e. the most recent complete history). Returns {model_name: {h: fitted_model}}.
    """
    feature_sets = get_feature_sets(cfg)
    if not enable_sentiment:
        feature_sets.pop("price_sentiment", None)
    if not enable_influence:
        feature_sets.pop("price_influence", None)

    fitted: Dict[str, Dict[int, object]] = {"no_change": {}}
    for name in feature_sets:
        fitted[name] = {}

    max_h = max(cfg.forecast_horizons)
    # Use all rows that have a complete y_h
    for h in cfg.forecast_horizons:
        ycol = f"y_{h}"
        if ycol not in panel.columns:
            continue
        # Train on every row where y_h is known (label available)
        train = panel[panel[ycol].notna()].copy()
        if len(train) < cfg.min_train_sessions:
            log.warning("Horizon %d: only %d train rows — skipping", h, len(train))
            continue

        fitted["no_change"][h] = NoChangeModel().fit(train, train[ycol])

        for name, feats in feature_sets.items():
            usable = [f for f in feats if f in train.columns and train[f].notna().any()]
            if not usable:
                continue
            X = train[usable].fillna(0.0)
            y = train[ycol]
            model = RidgeModel(alpha=cfg.ridge_alpha, use_scaler=cfg.use_standard_scaler)
            model.fit(X, y)
            fitted[name][h] = model

    return fitted


def forecast_forward(
    panel: pd.DataFrame,
    fitted: Dict[str, Dict[int, object]],
    cfg: Config,
) -> pd.DataFrame:
    """
    Generate forecasts for the *latest* origin (last row with features).
    Returns a tidy DataFrame: model, horizon, y_hat, close_t, forecast_close.
    """
    if panel.empty:
        return pd.DataFrame()

    latest = panel.iloc[[-1]]
    close_t = float(latest["close"].iloc[0])
    origin = latest.index[0]
    rows = []

    feature_sets = get_feature_sets(cfg)

    for name, models_by_h in fitted.items():
        for h, model in models_by_h.items():
            if name == "no_change":
                y_hat = 0.0
            else:
                feats = feature_sets.get(name, [])
                usable = [f for f in feats if f in latest.columns]
                X = latest[usable].fillna(0.0)
                try:
                    y_hat = float(model.predict(X)[0])
                except Exception as exc:
                    log.warning("Forward predict failed %s h=%d: %s", name, h, exc)
                    continue
            forecast_close = close_t * float(np.exp(y_hat))
            rows.append(
                {
                    "origin": origin,
                    "model": name,
                    "horizon": h,
                    "y_hat": y_hat,
                    "close_t": close_t,
                    "forecast_close": forecast_close,
                }
            )

    out = pd.DataFrame(rows)
    log.info("Forward forecasts produced: %d rows from origin %s", len(out), origin)
    return out

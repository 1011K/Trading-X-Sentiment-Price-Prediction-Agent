"""
Leakage-safe walk-forward evaluation.
"""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from .config import Config
from .exceptions import DataError, LeakageError
from .logging_utils import get_logger
from .models import NoChangeModel, RidgeModel, get_feature_sets
from .validation import assert_no_future_labels

log = get_logger(__name__)


def walk_forward(
    panel: pd.DataFrame,
    cfg: Config,
    enable_influence: bool = False,
    enable_sentiment: bool = True,
) -> Dict[str, pd.DataFrame]:
    """
    Expanding-window walk-forward.

    For each test origin t and horizon h:
      - train only on origins i where i + h <= t (label already known)
      - features at i use only information available at i
    """
    if panel is None or panel.empty:
        raise DataError("Cannot run walk-forward on empty panel")

    feature_sets = get_feature_sets(cfg)
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
    """
    Idealized next-open long-or-cash diagnostic.
    Signal at close t → position from next open to next close.
    """
    if preds is None or preds.empty or not cfg.report_trading_diagnostic:
        return pd.DataFrame()

    p1 = preds[preds["horizon"] == 1].copy()
    if p1.empty:
        return pd.DataFrame()

    records = []
    cost = cfg.diagnostic_roundtrip_cost_bps / 10_000.0

    for _, row in p1.iterrows():
        t = row["origin"]
        if t not in panel.index:
            continue
        loc = panel.index.get_loc(t)
        if isinstance(loc, slice) or (isinstance(loc, np.ndarray) and len(loc) != 1):
            continue
        if loc + 1 >= len(panel):
            continue
        next_row = panel.iloc[loc + 1]
        if "open" not in next_row or next_row["open"] <= 0:
            continue

        signal = 1 if row["y_hat"] > 0 else 0
        o = float(next_row["open"])
        c = float(next_row["close"])
        raw_ret = (c / o) - 1.0
        net_ret = signal * raw_ret - signal * cost
        records.append(
            {
                "origin": t,
                "signal": signal,
                "raw_oc_ret": raw_ret,
                "net_ret": net_ret,
                "y_hat": row["y_hat"],
            }
        )

    return pd.DataFrame(records)

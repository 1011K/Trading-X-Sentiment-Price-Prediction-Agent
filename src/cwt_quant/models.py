"""
Baseline models. Pure numpy — no sklearn required for the reference package.
No hyper-parameter search on the evaluation period.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


class NoChangeModel:
    """y_hat = 0 for every horizon (close stays the same)."""

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "NoChangeModel":
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return np.zeros(len(X))


class RidgeModel:
    """
    Closed-form Ridge with optional column standardization.
    Scaler statistics are fit on the training fold only.
    """

    def __init__(self, alpha: float = 10.0, use_scaler: bool = True):
        self.alpha = alpha
        self.use_scaler = use_scaler
        self.coef_: Optional[np.ndarray] = None
        self.intercept_: float = 0.0
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None
        self.feature_names: List[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "RidgeModel":
        self.feature_names = list(X.columns)
        Xv = np.asarray(X.values, dtype=float)
        yv = np.asarray(y.values, dtype=float)

        if self.use_scaler:
            self.mean_ = Xv.mean(axis=0)
            self.std_ = Xv.std(axis=0)
            self.std_[self.std_ < 1e-12] = 1.0
            Xv = (Xv - self.mean_) / self.std_

        # Closed-form: beta = (X'X + αI)^{-1} X'y  (with intercept via augmented design)
        n, p = Xv.shape
        X_aug = np.hstack([np.ones((n, 1)), Xv])
        XtX = X_aug.T @ X_aug
        # Do not regularize the intercept
        reg = self.alpha * np.eye(p + 1)
        reg[0, 0] = 0.0
        beta = np.linalg.solve(XtX + reg, X_aug.T @ yv)
        self.intercept_ = float(beta[0])
        self.coef_ = beta[1:]
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        Xv = np.asarray(X[self.feature_names].values, dtype=float)
        if self.use_scaler and self.mean_ is not None:
            Xv = (Xv - self.mean_) / self.std_
        return self.intercept_ + Xv @ self.coef_


def get_feature_sets(cfg) -> Dict[str, List[str]]:
    """Pre-registered feature sets. No post-hoc selection."""
    price_feats = ["ret_1", "ret_5", "vol_10", "mom_10"]
    sent_feats = price_feats + ["daily_mean", "post_count", "no_post"]
    infl_feats = price_feats + [
        "daily_influence",
        "influence_pressure",
        "post_count",
        "no_post",
    ]
    return {
        "price_only": price_feats,
        "price_sentiment": sent_feats,
        "price_influence": infl_feats,
    }

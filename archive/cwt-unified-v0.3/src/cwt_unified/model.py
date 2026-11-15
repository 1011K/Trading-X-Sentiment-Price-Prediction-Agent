"""Forecast and validation logic. All transforms are fitted within each train slice."""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from .config import Config

PRICE_FEATURES = ["ret_1", "ret_3", "ret_5", "vol_5"]
TEXT_FEATURES = ["sentiment_mean", "log_post_count", "sentiment_lag1"]
INFLUENCE_FEATURES = ["sentiment_influence", "influence_pressure"]


def build_features(prices: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    df = prices.merge(daily, on="date", how="left", validate="one_to_one")
    close = df.close.astype(float)
    df["ret_1"] = np.log(close / close.shift(1))
    df["ret_3"] = np.log(close / close.shift(3))
    df["ret_5"] = np.log(close / close.shift(5))
    df["vol_5"] = df.ret_1.rolling(5).std()
    df["log_post_count"] = np.log1p(df.post_count)
    df["sentiment_lag1"] = df.sentiment_mean.shift(1).fillna(0.)
    for c in PRICE_FEATURES+TEXT_FEATURES+INFLUENCE_FEATURES:
        if not np.isfinite(df[c].iloc[6:].to_numpy(dtype=float)).all():
            raise ValueError("Invalid non-finite feature column: " + c)
    return df


def variants(influence_eligible: bool):
    defs = {"price_only": PRICE_FEATURES,
            "price_plus_sentiment": PRICE_FEATURES + TEXT_FEATURES}
    if influence_eligible:
        defs["price_plus_influence"] = PRICE_FEATURES + TEXT_FEATURES + INFLUENCE_FEATURES
    return defs


def training_indices(asof: int, h: int, earliest: int = 6) -> np.ndarray:
    # The label at index i+h must have been observed by the origin close at 'asof'.
    return np.arange(earliest, max(earliest, asof-h+1), dtype=int)


def _fit_predict(df: pd.DataFrame, asof: int, h: int, columns: list[str], cfg: Config) -> tuple[float, int, int]:
    tr = training_indices(asof, h)
    if len(tr) < cfg.min_train_rows:
        raise ValueError("Insufficient training observations for horizon")
    c = df.close.to_numpy(dtype=float)
    ytr = np.log(c[tr+h] / c[tr])
    # No model/transform is fitted on the test date's inputs or future labels.
    fit = make_pipeline(StandardScaler(), Ridge(alpha=cfg.ridge_alpha))
    fit.fit(df.iloc[tr][columns].to_numpy(dtype=float), ytr)
    pred = float(fit.predict(df.iloc[[asof]][columns].to_numpy(dtype=float))[0])
    return pred, len(tr), int(tr.max()+h)


def walkforward(df: pd.DataFrame, cfg: Config, influence_eligible: bool = False) -> pd.DataFrame:
    n = len(df)
    if n < cfg.min_bars: raise ValueError(f"Need at least {cfg.min_bars} daily bars; received {n}")
    first_test = max(70, int(n*cfg.first_test_fraction))
    if first_test + max(cfg.horizons) >= n: raise ValueError("Insufficient held-out data")
    c = df.close.to_numpy(dtype=float)
    rows = []
    for t in range(first_test, n-1):
        for h in cfg.horizons:
            if t+h >= n: continue
            common = {"asof_index": t, "asof_date": str(df.date.iloc[t]),
                      "target_index": t+h, "target_date": str(df.date.iloc[t+h]), "horizon": h,
                      "origin_close": float(c[t]), "actual_close": float(c[t+h]),
                      "actual_logreturn": float(np.log(c[t+h]/c[t]))}
            rows.append({**common, "model": "naive_no_change", "pred_close": float(c[t]),
                         "pred_logreturn": 0., "train_count": 0,
                         "latest_train_label_index": -1})
            for name, cols in variants(influence_eligible).items():
                pred, count, last = _fit_predict(df, t, h, cols, cfg)
                rows.append({**common, "model": name,
                             "pred_close": float(c[t]*np.exp(pred)), "pred_logreturn": pred,
                             "train_count": count, "latest_train_label_index": last})
    return pd.DataFrame(rows)


def forecast_latest(df: pd.DataFrame, cfg: Config, influence_eligible: bool = False) -> pd.DataFrame:
    if len(df) < cfg.min_bars: raise ValueError("Not enough observations")
    t = len(df)-1
    rows = [{"asof_date": str(df.date.iloc[t]), "model": "observed", "horizon": 0,
             "forecast_close": float(df.close.iloc[t]), "status": "OBSERVED_NOT_FORECAST"}]
    for h in cfg.horizons:
        rows.append({"asof_date": str(df.date.iloc[t]), "model": "naive_no_change", "horizon": h,
                     "forecast_close": float(df.close.iloc[t]), "status": "FORECAST"})
        for name, cols in variants(influence_eligible).items():
            p, _, _ = _fit_predict(df, t, h, cols, cfg)
            rows.append({"asof_date": str(df.date.iloc[t]), "model": name, "horizon": h,
                         "forecast_close": float(df.close.iloc[t]*np.exp(p)), "status": "FORECAST"})
    return pd.DataFrame(rows)


def summarize(preds: pd.DataFrame) -> list[dict]:
    rows=[]
    for (model,h), d in preds.groupby(["model", "horizon"],sort=True):
        predicted=d.pred_close.to_numpy(float)
        actual=d.actual_close.to_numpy(float)
        error=predicted-actual
        reference=d.loc[:,"origin_close"].to_numpy(float)-actual
        directional=float(np.mean(np.sign(d.pred_logreturn) == np.sign(d.actual_logreturn)))
        rrmse=float(np.sqrt(np.mean(reference**2)))
        rmse=float(np.sqrt(np.mean(error**2)))
        rows.append({"model":model,"horizon":int(h),"test_n":int(len(d)),
                     "mae_price":float(np.mean(np.abs(error))),"rmse_price":rmse,
                     "naive_rmse_price":rrmse,"rmse_skill_vs_naive":float(1-rmse/rrmse) if rrmse>0 else None,
                     "directional_accuracy":directional,
                     "overlapping_horizon_warning":bool(h>1)})
    return rows


def research_pnl(preds: pd.DataFrame, prices: pd.DataFrame, cfg: Config, model: str = "price_plus_sentiment") -> dict:
    # Signal computed AFTER close(t), enter NEXT session's open, exit that session's close.
    # Must NOT be confused with close(t) -> close(t+1) forecast target.
    if "open" not in prices:
        return {"status":"WITHHELD","reason":"open prices absent: no executable next-open entry diagnostic"}
    p=preds.loc[(preds.horizon==1)&(preds.model==model)].sort_values("asof_index")
    if len(p)<10:
        return {"status":"WITHHELD","reason":"Fewer than ten out-of-sample origin dates"}
    next_ix = p.target_index.to_numpy(int)
    position = (p.pred_logreturn.to_numpy(float)>0).astype(float)
    # Daily bar executions are idealized; cost is a declared fixed estimate.
    raw_ret=prices.close.to_numpy(float)[next_ix]/prices.open.to_numpy(float)[next_ix]-1
    pnl=position*raw_ret-position*cfg.round_trip_cost_bps/10_000.
    equity=np.cumprod(1+pnl)
    peaks=np.maximum.accumulate(np.r_[1.,equity])[1:]
    std=float(np.std(pnl,ddof=1))
    downside=float(np.sqrt(np.mean(np.minimum(pnl,0)**2)))
    return {"status":"EXPERIMENTAL_IDEALIZED_EXECUTION","model":model,"sample_n":len(p),
            "entry":"next session open","exit":"same session close","position":"long or cash",
            "round_trip_cost_bps_assumed":cfg.round_trip_cost_bps,
            "sharpe":float(np.sqrt(252)*np.mean(pnl)/std) if std>0 else None,
            "sortino":float(np.sqrt(252)*np.mean(pnl)/downside) if downside>0 else None,
            "max_drawdown":float(np.min(equity/peaks-1)),
            "cumulative_return":float(equity[-1]-1),
            "caveat":"Daily open/close idealized fills; overnight gaps make actual PnL differ from close-to-close forecast target. No market impact/taxes calibrated."}

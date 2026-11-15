"""
Feature engineering with strict point-in-time and leakage guards.
"""

from __future__ import annotations

import re
from typing import List, Optional

import numpy as np
import pandas as pd

from .calendar import XNYSCalendar
from .config import Config
from .exceptions import DataError
from .logging_utils import get_logger

log = get_logger(__name__)

# Minimal transparent lexical lexicon (research baseline, not production NLP)
POS = {
    "bullish", "long", "buy", "upside", "breakout", "strong", "beat", "growth",
    "upgrade", "positive", "moon", "rally", "support",
}
NEG = {
    "bearish", "short", "sell", "downside", "breakdown", "weak", "miss", "decline",
    "downgrade", "negative", "crash", "dump", "resistance",
}


def lexical_sentiment(text: str) -> float:
    """Return score in [-1, 1]. Transparent, weak, reproducible."""
    if not isinstance(text, str) or not text.strip():
        return 0.0
    tokens = set(re.findall(r"[a-z]+", text.lower()))
    pos = len(tokens & POS)
    neg = len(tokens & NEG)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


def _cap_author_posts(df: pd.DataFrame, max_per_session: int) -> pd.DataFrame:
    """Limit repeated posts from the same author within a session (spam control)."""
    if df.empty or max_per_session < 1:
        return df
    df = df.sort_values("created_at")
    df["_rank"] = df.groupby(["session_date", "author"]).cumcount()
    before = len(df)
    df = df[df["_rank"] < max_per_session].drop(columns=["_rank"])
    removed = before - len(df)
    if removed:
        log.info("Author-cap removed %d posts (max %d per author/session)", removed, max_per_session)
    return df


def build_post_features(
    posts: pd.DataFrame,
    prices: pd.DataFrame,
    cfg: Config,
    cal: XNYSCalendar,
) -> pd.DataFrame:
    """
    Map posts to sessions, compute conversation sentiment, apply influence
    weights only when engagement snapshot is valid (asof <= origin close).
    """
    if posts is None or posts.empty:
        log.warning("No posts supplied; returning empty post features")
        return pd.DataFrame()

    df = posts.copy()
    n_before = len(df)
    df = df.drop_duplicates(subset=["post_id"], keep="first")
    if len(df) < n_before:
        log.info("Deduplicated %d duplicate post_id rows", n_before - len(df))

    # Cashtag gate
    if "has_cashtag" not in df.columns:
        raise DataError("Posts missing required column 'has_cashtag'")
    df = df[df["has_cashtag"]].copy()
    if df.empty:
        log.warning("No cashtag posts remaining after filter")
        return pd.DataFrame()

    # Session assignment with error isolation
    def _safe_map(ts):
        try:
            return cal.map_timestamp_to_session(ts, cfg.assign_exact_close_to_next)
        except Exception as exc:
            log.debug("Could not map timestamp %s: %s", ts, exc)
            return None

    df["session_date"] = df["created_at"].apply(_safe_map)
    bad = df["session_date"].isna()
    if bad.any():
        log.warning("Dropped %d posts that could not be mapped to a session", int(bad.sum()))
        df = df[~bad].copy()

    if df.empty:
        return pd.DataFrame()

    # HARDENED: Never backfill later posts into a previous price session.
    # A Saturday observation must not change Friday's closed-session features.
    if prices is not None and not prices.empty and "session_date" in prices.columns:
        last_available = prices["session_date"].max()
        future_mask = df["session_date"] > last_available
        if future_mask.any():
            log.warning(
                "Excluded %d post(s) assigned after final price session %s",
                int(future_mask.sum()), last_available,
            )
            df = df.loc[~future_mask].copy()

    # Historical external records need a VERIFIED observation timestamp.
    # Synthetic data carries an explicit generator provenance instead.
    external = df["source"].fillna("external").ne("synthetic") if "source" in df.columns else pd.Series(False, index=df.index)
    needs_asof = "observed_at" in df.columns or bool(external.any())
    if not df.empty and needs_asof:
        if "observed_at" not in df.columns:
            log.warning("Excluded %d external posts missing observed_at", int(external.sum()))
            df = df.loc[~external].copy()
        else:
            observed = pd.to_datetime(df["observed_at"], errors="coerce", utc=True)
            cutoffs = pd.to_datetime([cal.session_close_dt(d) for d in df["session_date"]], utc=True)
            created = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
            known_asof = (observed.notna() & (observed <= cutoffs) & (observed >= created)) | (~external & observed.isna())
            if (~known_asof).any():
                log.warning("Excluded %d observations not proven available by session close", int((~known_asof).sum()))
                df = df.loc[known_asof].copy()

    if df.empty:
        return pd.DataFrame()

    # Author frequency cap
    df = _cap_author_posts(df, cfg.max_posts_per_author_per_session)

    # Sentiment priority:
    # 1. explicit pre-scored column (if allowed)
    # 2. StockTwits / CWT _label_score (Bullish/Bearish or scaled daily score)
    # 3. transparent lexical baseline
    if "sentiment_prescored" in df.columns and getattr(cfg, "allow_prescored_sentiment", False):
        # A current NLP re-score of historical posts cannot be substituted for
        # an archived point-in-time score without declared timing.
        if "sentiment_scored_at" not in df.columns:
            raise DataError("Pre-scored sentiment requires sentiment_scored_at provenance")
        scored_at = pd.to_datetime(df["sentiment_scored_at"], errors="coerce", utc=True)
        cutoffs = pd.to_datetime([cal.session_close_dt(d) for d in df["session_date"]], utc=True)
        verified = scored_at.notna() & (scored_at <= cutoffs)
        lexical = df["text"].map(lexical_sentiment)
        scores = pd.to_numeric(df["sentiment_prescored"], errors="coerce")
        df["s_post"] = scores.where(verified & scores.between(-1, 1), lexical).fillna(0.0)
        log.info("Using only time-valid pre-scored sentiment; otherwise lexical")
    elif "_label_score" in df.columns:
        label = pd.to_numeric(df["_label_score"], errors="coerce")
        lexical = df["text"].map(lexical_sentiment)
        # Prefer explicit label when non-zero; otherwise fall back to lexical
        df["s_post"] = label.where(label != 0.0, lexical).fillna(0.0)
        log.info("Using StockTwits/CWT label scores where available, lexical otherwise")
    else:
        df["s_post"] = df["text"].map(lexical_sentiment)

    # Conversation score with reply time validity
    def conv_score(row):
        s = float(row["s_post"])
        if pd.notna(row.get("reply_sentiment")) and pd.notna(row.get("reply_asof")):
            try:
                close_dt = cal.session_close_dt(row["session_date"])
                if row["reply_asof"] <= close_dt:
                    return cfg.post_weight * s + cfg.reply_weight * float(row["reply_sentiment"])
            except Exception:
                pass
        return s

    df["s_conversation"] = df.apply(conv_score, axis=1)

    # Independently verify follower and engagement snapshots. A current follower
    # count is not a historical fact merely because the post is old.
    def has_valid_influence(row):
        close_dt = cal.session_close_dt(row["session_date"])
        engagement_asof = row.get("engagement_asof")
        followers_asof = row.get("followers_asof")
        if pd.isna(engagement_asof) or pd.isna(followers_asof):
            return False
        if not (row["created_at"] <= engagement_asof <= close_dt and
                row["created_at"] <= followers_asof <= close_dt):
            return False
        vals = pd.to_numeric(pd.Series([row.get(k) for k in
                              ("followers", "likes", "reposts", "comments")]), errors="coerce")
        return bool(vals.notna().all() and np.isfinite(vals.to_numpy(dtype=float)).all()
                    and (vals >= 0).all())

    df["influence_valid"] = df.apply(has_valid_influence, axis=1)

    def influence_weight(row):
        if not row["influence_valid"]:
            return 1.0
        reach = min(1.0, np.log1p(float(row["followers"])) / np.log1p(cfg.reach_cap_followers))
        eng = min(1.0, np.log1p(float(row["likes"]) + 2 * float(row["reposts"]) +
                                float(row["comments"])) / np.log1p(cfg.engagement_cap))
        return min(cfg.weight_cap, 1.0 + cfg.reach_coef * reach + cfg.engagement_coef * eng)

    df["weight"] = df.apply(influence_weight, axis=1)

    n_valid = int(df["influence_valid"].sum())
    log.info(
        "Post features: %d posts, %d with valid influence snapshots",
        len(df),
        n_valid,
    )
    return df


def aggregate_daily_sentiment(
    post_feat: pd.DataFrame,
    cfg: Config,
) -> pd.DataFrame:
    """
    Daily mean and influence-weighted mean + pressure feature.
    Zero-post days are handled downstream with explicit flags.
    """
    empty_cols = [
        "session_date",
        "post_count",
        "daily_mean",
        "daily_influence",
        "influence_pressure",
        "influence_coverage",
        "no_post",
    ]
    if post_feat is None or post_feat.empty:
        return pd.DataFrame(columns=empty_cols)

    g = post_feat.groupby("session_date", sort=True)

    daily = g.agg(
        post_count=("post_id", "count"),
        daily_mean=("s_conversation", "mean"),
        sum_w_s=("s_conversation", lambda s: (post_feat.loc[s.index, "weight"] * s).sum()),
        sum_w=("weight", "sum"),
        n_valid_infl=("influence_valid", "sum"),
    ).reset_index()

    daily["daily_influence"] = np.where(
        daily["sum_w"] > 0, daily["sum_w_s"] / daily["sum_w"], daily["daily_mean"]
    )
    daily["influence_pressure"] = np.tanh(
        daily["sum_w_s"] / (3.0 * np.sqrt(daily["post_count"].clip(lower=1)))
    )
    daily["influence_coverage"] = daily["n_valid_infl"] / daily["post_count"].clip(lower=1)
    daily["no_post"] = 0
    daily = daily.drop(columns=["sum_w_s", "sum_w", "n_valid_infl"])
    return daily


def build_price_features(prices: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    """
    Causal price features + multi-horizon log-return targets.
    """
    if prices is None or prices.empty:
        raise DataError("Cannot build price features from empty DataFrame")
    df = prices.copy()
    df["ret_1"] = np.log(df["close"]).diff()
    df["ret_5"] = np.log(df["close"]).diff(5)
    df["vol_10"] = df["ret_1"].rolling(10, min_periods=5).std()
    df["mom_10"] = df["close"].pct_change(10)

    for h in horizons:
        df[f"y_{h}"] = np.log(df["close"].shift(-h) / df["close"])

    df["next_open"] = df["open"].shift(-1)
    return df


def assemble_panel(
    prices: pd.DataFrame,
    daily_sent: pd.DataFrame,
    cfg: Config,
) -> pd.DataFrame:
    """Merge on session_date; fill no-post days with zeros + flag."""
    price_feat = build_price_features(prices, cfg.forecast_horizons)
    price_feat = price_feat.reset_index()
    if "session_date" not in price_feat.columns:
        price_feat["session_date"] = price_feat["session_close"].dt.date

    if daily_sent is None or daily_sent.empty:
        panel = price_feat.copy()
        panel["post_count"] = 0
        panel["daily_mean"] = 0.0
        panel["daily_influence"] = 0.0
        panel["influence_pressure"] = 0.0
        panel["no_post"] = 1
    else:
        panel = price_feat.merge(daily_sent, on="session_date", how="left")
        panel["post_count"] = panel["post_count"].fillna(0).astype(int)
        panel["daily_mean"] = panel["daily_mean"].fillna(0.0)
        panel["daily_influence"] = panel["daily_influence"].fillna(0.0)
        panel["influence_pressure"] = panel["influence_pressure"].fillna(0.0)
        panel["no_post"] = (panel["post_count"] == 0).astype(int)

    panel = panel.set_index("session_close").sort_index()
    log.info(
        "Assembled panel: %d sessions, %d with posts",
        len(panel),
        int((panel["post_count"] > 0).sum()),
    )
    return panel

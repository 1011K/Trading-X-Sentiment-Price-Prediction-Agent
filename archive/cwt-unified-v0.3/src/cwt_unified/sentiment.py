"""Transparent post scoring and *optional* historically observable influence.

Weights never create a sentiment sign. Unknown historical engagement does not
silently become a point-in-time predictor.
"""
from __future__ import annotations
import re
import numpy as np
import pandas as pd
from .config import Config
from .data import assign_session, is_relevant

POS = {"bullish", "beat", "beats", "growth", "upgrade", "upside", "profit", "surge", "recover", "rally", "outperform"}
NEG = {"bearish", "miss", "misses", "loss", "downgrade", "downside", "crash", "decline", "risk", "slump"}
NEGATION = {"not", "never", "no", "without"}


def lexical_sentiment(text: str) -> float:
    """Unvalidated explainable baseline, not financial-domain NLP or stance detection."""
    words = re.findall(r"[a-z']+", str(text).lower())
    opinions = []
    for i, word in enumerate(words):
        v = int(word in POS) - int(word in NEG)
        if v:
            if any(x in NEGATION for x in words[max(0, i - 3):i]): v = -v
            opinions.append(v)
    return float(np.mean(opinions)) if opinions else 0.


def influence_weight(followers: float, likes: float, reposts: float, comments: float) -> float:
    """EXPERIMENTAL fixed, capped heuristic, not fitted or causal evidence.
    Reach and engagement are normalized by predeclared caps, not future sample ranks.
    """
    xs = [followers, likes, reposts, comments]
    if any(not np.isfinite(v) or v < 0 for v in xs):
        raise ValueError("Influence requires complete non-negative historical fields")
    reach = np.clip(np.log1p(followers) / np.log1p(1_000_000), 0, 1)
    engagement = np.clip(np.log1p(likes + 2*reposts + comments) / np.log1p(10_000), 0, 1)
    return float(min(1.5, 1 + .30*reach + .20*engagement))


def build_daily_sentiment(prices: pd.DataFrame, posts: pd.DataFrame, config: Config):
    mapped = assign_session(posts, prices)
    mapped = mapped.loc[mapped.text.map(lambda x: is_relevant(x, config.ticker))].copy()
    mapped = mapped.sort_values(["session_date", "timestamp_utc", "post_id"]).copy()
    if len(mapped):
        # Cap only author IDs that are known. Unknown authors are never treated as one author.
        known = mapped.author_id.ne("")
        seq = mapped.loc[known].groupby(["session_date", "author_id"]).cumcount()
        mapped = mapped.loc[~known | (known & mapped.index.to_series().map(seq).fillna(0).lt(config.max_author_posts_per_day))].copy()
    mapped["post_s"] = mapped["sentiment"].where(mapped["sentiment"].notna(), mapped.text.map(lexical_sentiment)).astype(float)
    post_time = pd.to_datetime(mapped.timestamp_utc, utc=True)
    close = pd.to_datetime(mapped.session_close_utc, utc=True)
    snap = pd.to_datetime(mapped.engagement_asof_utc, utc=True)
    fields_available = mapped[["followers", "likes", "reposts", "comments"]].notna().all(axis=1)
    snap_usable = snap.notna() & snap.ge(post_time) & snap.le(close) & fields_available
    # Replies must be independently asset-scored and observed no later than the origin close.
    reply_time = pd.to_datetime(mapped.reply_asof_utc, utc=True)
    valid_reply = mapped.reply_sentiment.notna() & reply_time.notna() & reply_time.ge(post_time) & reply_time.le(close)
    mapped["conversation_s"] = mapped.post_s
    mapped.loc[valid_reply, "conversation_s"] = .6*mapped.loc[valid_reply, "post_s"] + .4*mapped.loc[valid_reply, "reply_sentiment"]
    mapped["weight"] = 1.0
    if snap_usable.any():
        subset = mapped.loc[snap_usable]
        mapped.loc[snap_usable, "weight"] = [influence_weight(r.followers, r.likes, r.reposts, r.comments) for r in subset.itertuples()]
    mapped["weighted_s"] = mapped.conversation_s * mapped.weight
    if mapped.empty:
        grouped = pd.DataFrame(columns=["post_count", "sentiment_mean", "sentiment_influence", "disagreement", "influence_pressure"])
    else:
        grouped = mapped.groupby("session_date").agg(
            post_count=("post_s", "size"), sentiment_mean=("conversation_s", "mean"),
            weighted_sum=("weighted_s", "sum"), weight_sum=("weight", "sum"),
            disagreement=("conversation_s", "std"))
        grouped["sentiment_influence"] = grouped.weighted_sum / grouped.weight_sum
        grouped["influence_pressure"] = np.tanh(grouped.weighted_sum / (3*np.sqrt(grouped.post_count)))
        grouped = grouped.drop(columns=["weighted_sum", "weight_sum"])
    daily = pd.DataFrame({"date": prices.date}).merge(grouped, left_on="date", right_index=True, how="left")
    cols = ["post_count", "sentiment_mean", "sentiment_influence", "disagreement", "influence_pressure"]
    daily[cols] = daily[cols].fillna(0.)
    daily["no_posts"] = daily.post_count.eq(0).astype(int)
    count = int(len(mapped))
    audit = {
        "relevant_mapped_posts": count,
        "influence_snapshots_valid": int(snap_usable.sum()),
        "reply_snapshots_valid": int(valid_reply.sum()),
        "influence_snapshot_coverage": float(snap_usable.mean()) if count else 0.,
        "allow_influence_requested": bool(config.allow_influence),
        "influence_model_eligible": bool(config.allow_influence and count >= 50 and mapped.session_date.nunique() >= 20 and snap_usable.all()),
        "sentiment_provider": "User-provided numeric scores where present, otherwise lexical baseline; external scores not independently verified",
        "post_count_before_filter": int(len(posts)),
        "posts_without_author_id": int(mapped.author_id.eq("").sum()),
        "unknown_historical_text_edits": True,
    }
    return daily, audit

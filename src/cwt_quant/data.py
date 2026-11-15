"""
Data loading and synthetic fixture generation.

Real-data mode uses optional connectors; synthetic mode exercises red-team fixtures.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, time, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from .calendar import XNYSCalendar, ET
from .config import Config, PACKAGE_VERSION
from .exceptions import DataError, ProvenanceError
from .logging_utils import get_logger

log = get_logger(__name__)


def _hash_df(df: pd.DataFrame) -> str:
    """Stable content hash for provenance."""
    try:
        raw = pd.util.hash_pandas_object(df, index=True).values.tobytes()
        return hashlib.sha256(raw).hexdigest()[:16]
    except Exception as exc:
        log.warning("Could not compute DataFrame hash: %s", exc)
        return "hash_failed"


def generate_synthetic_prices(
    cfg: Config,
    cal: XNYSCalendar,
    start: Optional[date] = None,
    n_sessions: int = 130,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Realistic daily OHLCV with occasional gaps (halts) and early-close days.
    Returns DataFrame indexed by session_close (tz-aware).
    """
    rng = np.random.default_rng(seed)
    if start is None:
        end = date(2026, 11, 13)
        days = cal.trading_days_between(
            end - timedelta(days=cfg.history_calendar_days + 30), end
        )
        days = days[-n_sessions:]
    else:
        days = cal.trading_days_between(
            start, start + timedelta(days=cfg.history_calendar_days + 60)
        )
        days = days[:n_sessions]

    if len(days) < 30:
        raise DataError(f"Could not generate enough trading days: got {len(days)}")

    closes, opens, highs, lows, volumes, session_dates = [], [], [], [], [], []
    price = 180.0

    for i, d in enumerate(days):
        # Occasional missing session (halt / data outage) — red-team case
        if i in {25, 67} and rng.random() < 0.9:
            log.debug("Synthetic gap inserted at session index %d (%s)", i, d)
            continue

        ret = rng.normal(0.0004, 0.012)
        o = price * (1 + rng.normal(0, 0.003))
        c = o * (1 + ret)
        h = max(o, c) * (1 + abs(rng.normal(0, 0.004)))
        l = min(o, c) * (1 - abs(rng.normal(0, 0.004)))
        vol = int(rng.lognormal(15.5, 0.4))

        closes.append(c)
        opens.append(o)
        highs.append(h)
        lows.append(l)
        volumes.append(vol)
        session_dates.append(d)
        price = c

    idx = pd.DatetimeIndex(
        [cal.session_close_dt(d) for d in session_dates], name="session_close"
    )
    df = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "session_date": session_dates,
        },
        index=idx,
    )
    df["adj_close"] = df["close"]  # synthetic: no corp actions
    df.attrs["source_hash"] = _hash_df(df)
    df.attrs["provenance"] = "synthetic_prices_v1"
    df.attrs["adjustment_policy"] = "none (synthetic identity)"
    log.info(
        "Generated synthetic prices: %d sessions, hash=%s",
        len(df),
        df.attrs["source_hash"],
    )
    return df


def generate_synthetic_posts(
    cfg: Config,
    cal: XNYSCalendar,
    price_df: pd.DataFrame,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Synthetic X posts covering red-team cases:
    cashtag / non-cashtag, exact-close, early-close, post-close engagement,
    duplicate post_ids, celebrity neutral, missing replies, author spam.
    """
    rng = np.random.default_rng(seed + 1)
    sessions = price_df["session_date"].tolist()
    if not sessions:
        raise DataError("Cannot generate posts: price sessions empty")

    rows = []
    post_id = 10000
    authors = [
        ("user_alpha", 12_000),
        ("user_beta", 85_000),
        ("elon_musk_sim", 180_000_000),
        ("retail_gamma", 420),
        ("newsbot_delta", 2_300_000),
        ("user_epsilon", 9_500),
        ("spam_author", 3_000),
    ]

    for i, sess in enumerate(sessions):
        n_posts = int(rng.integers(0, 8))
        for j in range(n_posts):
            author, followers = authors[rng.integers(0, len(authors))]
            if rng.random() < 0.15:
                prev = cal.previous_trading_day(sess)
                close_t = cal.session_close_time(prev)
                ts = datetime(
                    prev.year, prev.month, prev.day, close_t.hour, close_t.minute, tzinfo=ET
                )
            elif rng.random() < 0.1:
                prev = cal.previous_trading_day(sess)
                ts = datetime(prev.year, prev.month, prev.day, 17, 30, tzinfo=ET)
            else:
                hour = int(rng.integers(8, 16))
                minute = int(rng.integers(0, 60))
                ts = datetime(sess.year, sess.month, sess.day, hour, minute, tzinfo=ET)

            if rng.random() < 0.75:
                text = f"${cfg.ticker} looking interesting today. " + rng.choice(
                    ["bullish setup", "watch the levels", "neutral for now", "bearish flow", ""]
                )
                has_cashtag = True
            else:
                text = rng.choice(
                    ["I like apple fruit", "Apple pie recipe", "unrelated tech news", "random"]
                )
                has_cashtag = False

            likes = int(rng.lognormal(3, 1.5))
            reposts = int(rng.lognormal(1.5, 1.2))
            comments = int(rng.lognormal(1.8, 1.1))
            engagement_asof = ts + timedelta(minutes=int(rng.integers(5, 400)))

            if i > 5 and rng.random() < 0.08:
                close_dt = cal.session_close_dt(sess)
                engagement_asof = close_dt + timedelta(minutes=3)

            rows.append(
                {
                    "post_id": post_id,
                    "created_at": ts,
                    "author": author,
                    "followers": followers,
                    "followers_asof": ts,
                    "text": text,
                    "has_cashtag": has_cashtag,
                    "likes": likes,
                    "reposts": reposts,
                    "comments": comments,
                    "engagement_asof": engagement_asof,
                    "reply_sentiment": (
                        float(rng.uniform(-0.6, 0.6)) if rng.random() < 0.4 else None
                    ),
                    "reply_asof": (
                        ts + timedelta(minutes=30) if rng.random() < 0.4 else None
                    ),
                }
            )
            post_id += 1

            if rng.random() < 0.02:
                rows.append(dict(rows[-1]))

    df = pd.DataFrame(rows)
    df.attrs["source_hash"] = _hash_df(df)
    df.attrs["provenance"] = "synthetic_posts_v1"
    log.info(
        "Generated synthetic posts: %d rows, hash=%s",
        len(df),
        df.attrs["source_hash"],
    )
    return df


def _empty_posts_schema() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "post_id",
            "created_at",
            "author",
            "followers",
            "followers_asof",
            "text",
            "has_cashtag",
            "likes",
            "reposts",
            "comments",
            "engagement_asof",
            "reply_sentiment",
            "reply_asof",
            "source",
        ]
    )


def _map_stocktwits_to_posts(st_df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Map StockTwits public stream rows into the internal post schema."""
    if st_df is None or st_df.empty:
        return _empty_posts_schema()
    from .connectors.stocktwits import label_to_score

    rows = []
    for i, r in st_df.iterrows():
        created = r["created_at"]
        if hasattr(created, "to_pydatetime"):
            created = created.to_pydatetime()
        # Prefer explicit Bullish/Bearish label; fall back to lexical later
        label_score = label_to_score(r.get("sentiment_label"))
        body = str(r.get("body") or "")
        # Preserve the verbatim body. A symbol-stream result is not proof
        # that the original author used the requested cashtag.
        has_cashtag = f"${ticker.upper()}" in body.upper()
        rows.append(
            {
                "post_id": f"st_{r['post_id']}",
                "created_at": created,
                "author": str(r.get("author") or "st_user"),
                "followers": float("nan"),  # unknown, do not invent it
                "followers_asof": pd.NaT,
                "text": body[:2000],
                "has_cashtag": has_cashtag,
                "likes": int(r.get("likes") or 0),
                "reposts": 0,
                "comments": int(r.get("replies") or 0),
                "engagement_asof": pd.NaT,  # current totals are NOT historical snapshots
                "observed_at": datetime.now(timezone.utc),
                "reply_sentiment": None,
                "reply_asof": None,
                "source": "stocktwits_public",
                "_label_score": label_score,
            }
        )
    return pd.DataFrame(rows)


def _map_news_to_posts(news: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if news is None or news.empty:
        return _empty_posts_schema()
    rows = []
    for i, r in news.iterrows():
        pub = r["published_at"]
        if hasattr(pub, "to_pydatetime"):
            pub = pub.to_pydatetime()
        rows.append(
            {
                "post_id": f"news_{1_000_000 + i}",
                "created_at": pub,
                "author": str(r.get("source") or "news"),
                "followers": float("nan"),  # news outlets are not social accounts
                "followers_asof": pd.NaT,
                "text": str(r.get("title") or ""),
                "has_cashtag": f"${ticker.upper()}" in str(r.get("title") or "").upper(),
                "likes": 0,
                "reposts": 0,
                "comments": 0,
                "engagement_asof": pd.NaT,
                "observed_at": datetime.now(timezone.utc),
                "reply_sentiment": None,
                "reply_asof": None,
                "source": "news",
            }
        )
    return pd.DataFrame(rows)


def load_or_generate(
    cfg: Config,
    force_synthetic: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Returns (prices, posts, meta).

    force_synthetic=True  → full red-team synthetic fixtures (default, tests).
    force_synthetic=False → real prices (yfinance) + free social/news proxies.
    """
    cal = XNYSCalendar()
    meta: Dict[str, Any] = {
        "mode": "synthetic",
        "real_data_present": False,
        "price_hash": None,
        "posts_hash": None,
        "warnings": [],
        "adjustment_policy": None,
    }

    if force_synthetic:
        try:
            prices = generate_synthetic_prices(cfg, cal, seed=cfg.seed)
            posts = generate_synthetic_posts(cfg, cal, prices, seed=cfg.seed)
        except Exception as exc:
            raise DataError(f"Synthetic data generation failed: {exc}") from exc

        meta["price_hash"] = prices.attrs.get("source_hash")
        meta["posts_hash"] = posts.attrs.get("source_hash")
        meta["adjustment_policy"] = prices.attrs.get("adjustment_policy")
        meta["n_sessions"] = len(prices)
        meta["n_posts"] = len(posts)
        return prices, posts, meta

    # ---- Real data path (free open sources only) ----
    from .connectors.prices import fetch_daily_ohlc
    from .connectors.news import fetch_news_headlines
    from .connectors.stocktwits import fetch_stocktwits_messages

    log.info("Real-data mode: yfinance prices + StockTwits public + optional news")
    prices = fetch_daily_ohlc(
        cfg.ticker,
        history_calendar_days=cfg.history_calendar_days,
    )

    post_frames = []
    source_notes = ["Prices: yfinance daily auto_adjust"]

    # 1. StockTwits public stream (recent only, free, keyless)
    try:
        st = fetch_stocktwits_messages(cfg.ticker, max_pages=3)
        st_mapped = _map_stocktwits_to_posts(st, cfg.ticker)
        if not st_mapped.empty:
            post_frames.append(st_mapped)
            source_notes.append(f"StockTwits public stream: {len(st_mapped)} msgs")
    except Exception as exc:
        log.warning("StockTwits connector failed (non-fatal): %s", exc)
        meta["warnings"].append(f"StockTwits unavailable: {exc}")

    # 2. News headlines (optional free/cheap key)
    try:
        news = fetch_news_headlines(cfg.ticker)
        news_mapped = _map_news_to_posts(news, cfg.ticker)
        if not news_mapped.empty:
            post_frames.append(news_mapped)
            source_notes.append(f"News headlines: {len(news_mapped)}")
    except Exception as exc:
        log.warning("News connector failed (non-fatal): %s", exc)

    if post_frames:
        posts = pd.concat(post_frames, ignore_index=True)
        posts = posts.drop_duplicates(subset=["post_id"], keep="first")
    else:
        posts = _empty_posts_schema()
        meta["warnings"].append(
            "No social/news posts available — sentiment features will be zero. "
            "Price-only models still run."
        )

    # HARDENED: CWT's current aggregate score is not an individual X post.
    # Retain it separately for observational reporting, NEVER insert a fictitious
    # post or pretend this value was available at a prior close.
    try:
        from .connectors.cwt_sentiment import fetch_daily_crowd_score
        info = fetch_daily_crowd_score(cfg.ticker)
        if info.get("score") is not None:
            meta["latest_external_crowd_score"] = {
                "score": info["score"],
                "traders": info.get("traders"),
                "provider_as_of": info.get("as_of"),
                "collected_at_utc": datetime.now(timezone.utc).isoformat(),
                "historical_backtest_eligible": False,
            }
            source_notes.append("CWT daily score: context only, excluded from historical features")
    except Exception as exc:
        log.warning("CrowdWisdom daily score unavailable: %s", exc)

    meta["mode"] = "real"
    meta["real_data_present"] = True
    meta["price_hash"] = prices.attrs.get("source_hash") or "yfinance"
    meta["posts_hash"] = _hash_df(posts) if not posts.empty else "empty"
    meta["adjustment_policy"] = prices.attrs.get("adjustment_policy")
    meta["n_sessions"] = len(prices)
    meta["n_posts"] = len(posts)
    meta["source_note"] = " | ".join(source_notes)
    meta["honesty"] = (
        "No historical X point-in-time snapshots are provided. Live-fetched social/news "
        "are not backfilled into prior sessions, and the CWT score is context-only. "
        "Price-only results may run; sentiment improvement is WITHHELD pending archive."
    )
    return prices, posts, meta


def write_manifest(meta: Dict[str, Any], cfg: Config, out_dir: Path) -> Path:
    """Write a reproducibility manifest."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "run_manifest.json"
    payload = {
        "meta": meta,
        "config": cfg.to_dict(),
        "package_version": PACKAGE_VERSION,
        "status": "EXPERIMENTAL / INDEPENDENT CANDIDATE",
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    log.info("Wrote run manifest: %s", path)
    return path

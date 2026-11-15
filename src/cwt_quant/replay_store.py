"""Local SQLite evidence for reproducible submission runs."""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

import pandas as pd

from .connectors.tavily import validate_news_context
from .exceptions import DataError

SCHEMA = """
CREATE TABLE IF NOT EXISTS source_manifests (
  run_id TEXT PRIMARY KEY, ticker TEXT NOT NULL, metadata TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS price_bars (
  run_id TEXT NOT NULL REFERENCES source_manifests(run_id), session_date TEXT NOT NULL,
  session_close TEXT NOT NULL, open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL,
  close REAL NOT NULL, adj_close REAL NOT NULL, volume INTEGER NOT NULL,
  dividends REAL NOT NULL, splits REAL NOT NULL, PRIMARY KEY (run_id, session_date)
);
CREATE TABLE IF NOT EXISTS x_posts (
  run_id TEXT NOT NULL REFERENCES source_manifests(run_id), post_id TEXT NOT NULL,
  created_at TEXT NOT NULL, observed_at TEXT, model_eligible INTEGER NOT NULL,
  payload TEXT NOT NULL, PRIMARY KEY (run_id, post_id)
);
CREATE INDEX IF NOT EXISTS x_posts_by_availability ON x_posts(run_id, observed_at);
CREATE TABLE IF NOT EXISTS x_post_sessions (
  run_id TEXT NOT NULL, post_id TEXT NOT NULL, session_date TEXT NOT NULL,
  PRIMARY KEY (run_id, post_id),
  FOREIGN KEY (run_id, post_id) REFERENCES x_posts(run_id, post_id),
  FOREIGN KEY (run_id, session_date) REFERENCES price_bars(run_id, session_date)
);
CREATE INDEX IF NOT EXISTS x_post_sessions_by_date ON x_post_sessions(run_id, session_date);
CREATE TABLE IF NOT EXISTS session_panel (
  run_id TEXT NOT NULL REFERENCES source_manifests(run_id), session_close TEXT NOT NULL,
  payload TEXT NOT NULL, PRIMARY KEY (run_id, session_close)
);
CREATE TABLE IF NOT EXISTS forecast_ledger (
  run_id TEXT NOT NULL REFERENCES source_manifests(run_id), phase TEXT NOT NULL,
  model TEXT NOT NULL, origin TEXT NOT NULL, horizon INTEGER NOT NULL, payload TEXT NOT NULL,
  PRIMARY KEY (run_id, phase, model, origin, horizon)
);
CREATE TABLE IF NOT EXISTS trade_ledger (
  run_id TEXT NOT NULL REFERENCES source_manifests(run_id), model TEXT NOT NULL,
  origin TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY (run_id, model, origin)
);
CREATE TABLE IF NOT EXISTS open_nowcast_ledger (
  run_id TEXT NOT NULL REFERENCES source_manifests(run_id), model TEXT NOT NULL,
  origin TEXT NOT NULL, horizon INTEGER NOT NULL CHECK (horizon = 0), payload TEXT NOT NULL,
  PRIMARY KEY (run_id, model, origin)
);
CREATE UNIQUE INDEX IF NOT EXISTS source_manifests_run_ticker ON source_manifests(run_id, ticker);
CREATE TABLE IF NOT EXISTS news_captures (
  run_id TEXT NOT NULL, capture_id TEXT NOT NULL, ticker TEXT NOT NULL, source TEXT NOT NULL,
  collected_at_utc TEXT NOT NULL, response_sha256 TEXT NOT NULL, metadata TEXT NOT NULL,
  PRIMARY KEY (run_id, capture_id),
  FOREIGN KEY (run_id, ticker) REFERENCES source_manifests(run_id, ticker)
);
CREATE INDEX IF NOT EXISTS news_captures_by_collection ON news_captures(run_id, collected_at_utc);
CREATE TABLE IF NOT EXISTS news_articles (
  run_id TEXT NOT NULL, capture_id TEXT NOT NULL, url TEXT NOT NULL, title TEXT NOT NULL,
  published_at_utc TEXT, published_date TEXT, publication_status TEXT NOT NULL,
  PRIMARY KEY (run_id, capture_id, url),
  FOREIGN KEY (run_id, capture_id) REFERENCES news_captures(run_id, capture_id)
);
"""


def _json_scalar(value: object) -> object:
    if value is pd.NaT or value is pd.NA or (isinstance(value, float) and not math.isfinite(value)):
        return None
    return value.isoformat() if isinstance(value, date) else value


def _records(frame: pd.DataFrame) -> list[dict]:
    return [
        {key: _json_scalar(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _store_news(db: sqlite3.Connection, run_id: str, capture: dict) -> None:
    metadata = json.dumps(capture, ensure_ascii=False, sort_keys=True, allow_nan=False)
    capture_id = hashlib.sha256(metadata.encode()).hexdigest()
    db.execute(
        "INSERT INTO news_captures VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(run_id, capture_id) DO NOTHING",
        (run_id, capture_id, capture["ticker"], capture["source"], capture["collected_at_utc"],
         capture["response_sha256"], metadata),
    )
    db.executemany(
        "INSERT INTO news_articles VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(run_id, capture_id, url) DO NOTHING",
        (
            (run_id, capture_id, row["url"], row["title"], row["published_at_utc"],
             row["published_date"], row["publication_status"])
            for row in capture["articles"]
        ),
    )


def store_run(path: Path, run_id: str, manifest: dict, prices: pd.DataFrame,
              posts: pd.DataFrame, result: dict, forecasts: pd.DataFrame,
              comparisons: dict[str, pd.DataFrame], trades: dict[str, pd.DataFrame],
              nowcasts: pd.DataFrame | None = None) -> None:
    price_dates = set(prices["session_date"].astype(str))
    features = result["post_features"]
    post_sessions = {
        row.post_id: str(row.session_date) for row in features.itertuples()
        if str(row.session_date) in price_dates
    }
    # Targets and next-session prices are intentionally excluded from the as-of panel.
    panel = result["panel"]
    asof_columns = [c for c in panel if not c.startswith("y_") and c not in {"next_open", "adj_close"}]
    ticker = manifest["ticker"]
    news = manifest.get("current_news")
    capture = validate_news_context(news, ticker) if isinstance(news, dict) and news.get("source") == "Tavily" else None
    historical = {
        key: value for key, value in manifest.items() if key not in {"current_news", "generated_at_utc"}
    }
    forecast_phases = {"walk_forward": comparisons, "forward": dict(tuple(forecasts.groupby("model")))}
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(SCHEMA)
        with db:
            saved = db.execute(
                "INSERT INTO source_manifests VALUES (?, ?, ?) "
                "ON CONFLICT(run_id) DO UPDATE SET metadata=excluded.metadata "
                "WHERE source_manifests.ticker=excluded.ticker",
                (run_id, ticker, json.dumps(historical, sort_keys=True, allow_nan=False)),
            )
            if saved.rowcount != 1:
                raise DataError("Replay run ID already belongs to another ticker")
            for table in ("x_post_sessions", "price_bars", "x_posts", "session_panel", "forecast_ledger", "trade_ledger",
                          "open_nowcast_ledger"):
                db.execute(f"DELETE FROM {table} WHERE run_id=?", (run_id,))
            db.executemany("INSERT INTO price_bars VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                (run_id, str(row.session_date), ts.isoformat(), row.open, row.high, row.low,
                 row.close, row.adj_close, int(row.volume), row.dividends, row.splits)
                for ts, row in prices.iterrows()
            ))
            db.executemany("INSERT INTO x_posts VALUES (?, ?, ?, ?, ?, ?)", (
                (run_id, row["post_id"], row["created_at"], row.get("observed_at"),
                 int(row["post_id"] in post_sessions), json.dumps(row, ensure_ascii=False))
                for row in _records(posts)
            ))
            db.executemany("INSERT INTO x_post_sessions VALUES (?, ?, ?)", (
                (run_id, post_id, session_date) for post_id, session_date in post_sessions.items()
            ))
            db.executemany("INSERT INTO session_panel VALUES (?, ?, ?)", (
                (run_id, row["session_close"], json.dumps(row))
                for row in _records(panel[asof_columns].reset_index())
            ))
            db.executemany("INSERT INTO forecast_ledger VALUES (?, ?, ?, ?, ?, ?)", (
                (run_id, phase, model, row["origin"], row["horizon"], json.dumps(row))
                for phase, frames in forecast_phases.items()
                for model, frame in frames.items()
                for row in _records(frame)
            ))
            if capture is not None:
                _store_news(db, run_id, capture)
            if nowcasts is not None:
                db.executemany("INSERT INTO open_nowcast_ledger VALUES (?, ?, ?, ?, ?)", (
                    (run_id, row["model"], row["origin"], row["horizon"], json.dumps(row))
                    for row in _records(nowcasts)
                ))
            db.executemany("INSERT INTO trade_ledger VALUES (?, ?, ?, ?)", (
                (run_id, model, row["origin"], json.dumps(row))
                for model, frame in trades.items()
                for row in _records(frame)
            ))

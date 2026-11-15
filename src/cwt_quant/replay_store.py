"""Local SQLite evidence for reproducible submission runs."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

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
"""


def _records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def store_run(path: Path, run_id: str, manifest: dict, prices: pd.DataFrame,
              posts: pd.DataFrame, result: dict, forecasts: pd.DataFrame,
              comparisons: dict[str, pd.DataFrame], trades: dict[str, pd.DataFrame]) -> None:
    eligible_ids = set(result["post_features"].get("post_id", []))
    # Targets and next-session prices are intentionally excluded from the as-of panel.
    panel = result["panel"]
    asof_columns = [c for c in panel if not c.startswith("y_") and c not in {"next_open", "adj_close"}]
    with closing(sqlite3.connect(path)) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(SCHEMA)
        with db:
            db.execute(
                "INSERT INTO source_manifests VALUES (?, ?, ?) "
                "ON CONFLICT(run_id) DO UPDATE SET metadata=excluded.metadata",
                (run_id, manifest["ticker"], json.dumps(manifest, allow_nan=False)),
            )
            for table in ("price_bars", "x_posts", "session_panel", "forecast_ledger", "trade_ledger"):
                db.execute(f"DELETE FROM {table} WHERE run_id=?", (run_id,))
            db.executemany("INSERT INTO price_bars VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                (run_id, str(row.session_date), ts.isoformat(), row.open, row.high, row.low,
                 row.close, row.adj_close, int(row.volume), row.dividends, row.splits)
                for ts, row in prices.iterrows()
            ))
            db.executemany("INSERT INTO x_posts VALUES (?, ?, ?, ?, ?, ?)", (
                (run_id, row["post_id"], row["created_at"], row.get("observed_at"),
                 int(row["post_id"] in eligible_ids), json.dumps(row, ensure_ascii=False))
                for row in _records(posts)
            ))
            db.executemany("INSERT INTO session_panel VALUES (?, ?, ?)", (
                (run_id, row["session_close"], json.dumps(row))
                for row in _records(panel[asof_columns].reset_index())
            ))
            db.executemany("INSERT INTO forecast_ledger VALUES (?, ?, ?, ?, ?, ?)", (
                (run_id, phase, model, row["origin"], row["horizon"], json.dumps(row))
                for phase, frames in (
                    ("walk_forward", comparisons),
                    ("forward", dict(tuple(forecasts.groupby("model", sort=True)))),
                )
                for model, frame in frames.items()
                for row in _records(frame)
            ))
            db.executemany("INSERT INTO trade_ledger VALUES (?, ?, ?, ?)", (
                (run_id, model, row["origin"], json.dumps(row))
                for model, frame in trades.items()
                for row in _records(frame)
            ))

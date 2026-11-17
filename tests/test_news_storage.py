"""Regression tests for current news evidence and replay storage."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from cwt_quant.connectors import tavily
from cwt_quant.exceptions import DataError
from cwt_quant.replay_store import store_run


def mock_response(monkeypatch, items):
    key = "dummy_news_token"
    raw = json.dumps({
        "request_id": "42e79f8f-a5e2-460a-94ba-6dcc517cdd04",
        "results": items,
    }, indent=2).encode()

    class Client:
        def __init__(self, host, timeout):
            pass

        def request(self, method, path, body, headers):
            assert headers["Authorization"] == f"Bearer {key}"
            assert key not in body

        def getresponse(self):
            return SimpleNamespace(status=200, read=lambda: raw)

        def close(self):
            pass

    monkeypatch.setenv("TAVILY_API_KEY", key)
    monkeypatch.setattr(tavily.http.client, "HTTPSConnection", Client)
    return hashlib.sha256(raw).hexdigest()


def test_tavily_preserves_precision_and_source_hash(monkeypatch):
    digest = mock_response(monkeypatch, [
        {"title": "Timed", "url": "https://example.com/timed",
         "published_date": "Sat, 14 Nov 2026 11:00:00 -0500"},
        {"title": "Date only", "url": "https://example.com/day",
         "published_date": "2026-11-14"},
        {"title": "Undated", "url": "https://example.com/undated"},
    ])
    batch = tavily.fetch_news_context("AAPL")
    assert batch["ticker"] == "AAPL"
    assert batch["response_sha256"] == digest
    assert batch["request_id"] == "42e79f8f-a5e2-460a-94ba-6dcc517cdd04"
    assert "AAPL" in batch["request"]["query"]
    timed, dated, unknown = batch["articles"]
    assert timed["published_at_utc"] == "2026-11-14T16:00:00+00:00"
    assert timed["publication_status"] == "provider_timestamp"
    assert dated["publication_status"] == "provider_date"
    assert dated["published_date"] == "2026-11-14"
    assert dated["published_at_utc"] is None
    assert unknown["publication_status"] == "missing"
    assert unknown["published_date"] is None
    assert unknown["published_at_utc"] is None


def test_tavily_rejects_embedded_auth_and_deduplicates_links(monkeypatch):
    mock_response(monkeypatch, [
        {"title": "First", "url": "https://example.com/article?tracking=1"},
        {"title": "Duplicate", "url": "https://EXAMPLE.COM/article?tracking=2"},
        {"title": "Unsafe", "url": "https://example.com\\@evil.example/path"},
        {"title": "Encoded credential", "url": "https://example.com/%64ummy_news_token"},
    ])
    assert tavily.fetch_news_context("AAPL")["headlines"] == [
        {"title": "First", "url": "https://example.com/article"},
    ]


def test_tavily_does_not_promote_future_or_naive_dates(monkeypatch):
    mock_response(monkeypatch, [
        {"title": "Future", "url": "https://example.com/future",
         "published_date": "2099-06-05T07:00:00Z"},
        {"title": "Naive", "url": "https://example.com/naive",
         "published_date": "2025-06-05T07:00:00"},
        {"title": "Invalid offset", "url": "https://example.com/offset",
         "published_date": "2025-06-05T07:00:00+05:99"},
    ])
    articles = tavily.fetch_news_context("AAPL")["articles"]
    assert [row["publication_status"] for row in articles] == ["future", "invalid", "invalid"]
    assert all(row["published_at_utc"] is None and row["published_date"] is None for row in articles)


def fake_run(tmp_path):
    db_path = tmp_path / "replay.sqlite3"
    dates = pd.DatetimeIndex(["2026-11-13T16:00:00-05:00"], name="session_close")
    prices = pd.DataFrame({
        "session_date": [date(2026, 11, 13)], "open": [100.0], "high": [101.0],
        "low": [99.0], "close": [100.5], "adj_close": [100.5], "volume": [1_000],
        "dividends": [0.0], "splits": [0.0],
    }, index=dates)
    posts = pd.DataFrame([{
        "post_id": "1", "created_at": dates[0],
        "observed_at": pd.Timestamp("2026-11-13T21:00:00.000000001Z"),
    }])
    result = {"panel": prices, "post_features": pd.DataFrame()}
    forecasts = pd.DataFrame([{"model": "no_change", "origin": dates[0], "horizon": 1}])

    def save(news=None, nowcasts=None, ticker="AAPL", post_features=None):
        manifest = {"ticker": ticker, "generated_at_utc": "2026-11-15T00:00:00+00:00",
                    "current_news": news}
        args = () if nowcasts is None else (nowcasts,)
        run_result = result if post_features is None else {**result, "post_features": post_features}
        store_run(db_path, "run1", manifest, prices, posts, run_result, forecasts, {}, {}, *args)

    return db_path, save


def test_sqlite_captures_are_separate_append_only_and_idempotent(tmp_path, monkeypatch):
    path, save = fake_run(tmp_path)
    save()
    with sqlite3.connect(path) as db:
        expected_manifest = db.execute("SELECT metadata FROM source_manifests").fetchone()
        expected_forecasts = db.execute("SELECT * FROM forecast_ledger").fetchall()
    for url in ("https://example.com/first", "https://example.com/second"):
        mock_response(monkeypatch, [{"title": "Article", "url": url}])
        capture = tavily.fetch_news_context("AAPL")
        save(capture)
        save(capture)
    save()

    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("SELECT metadata FROM source_manifests").fetchone() == expected_manifest
        assert db.execute("SELECT * FROM forecast_ledger").fetchall() == expected_forecasts
        assert "current_news" not in json.loads(expected_manifest[0])
        assert db.execute("SELECT count(*) FROM news_captures").fetchone() == (2,)
        assert db.execute("""
            SELECT c.ticker, a.url, a.published_at_utc, a.publication_status
            FROM news_articles a JOIN news_captures c USING (run_id, capture_id)
            JOIN source_manifests m ON m.run_id=c.run_id AND m.ticker=c.ticker
            JOIN x_posts x ON x.run_id=c.run_id
            JOIN price_bars p ON p.run_id=c.run_id
            ORDER BY a.url
        """).fetchall() == [
            ("AAPL", "https://example.com/first", None, "missing"),
            ("AAPL", "https://example.com/second", None, "missing"),
        ]


def test_sqlite_rejects_cross_ticker_captures_and_run_id_collisions(tmp_path, monkeypatch):
    path, save = fake_run(tmp_path)
    save()
    mock_response(monkeypatch, [])
    with pytest.raises(DataError, match="ticker"):
        save(tavily.fetch_news_context("MSFT"))
    with pytest.raises(DataError, match="ticker"):
        save(ticker="MSFT")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM news_captures").fetchone() == (0,)
        assert db.execute("SELECT ticker FROM source_manifests").fetchone() == ("AAPL",)


def test_sqlite_records_open_nowcast_in_separate_ledger(tmp_path):
    path, save = fake_run(tmp_path)
    nowcasts = pd.DataFrame([{
        "model": "no_change", "origin": pd.Timestamp("2026-11-13T09:30:00-05:00"),
        "horizon": 0, "forecast_close": 99.0, "actual_close": 100.5,
    }])
    save(nowcasts=nowcasts)
    save(nowcasts=nowcasts)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT phase, horizon FROM forecast_ledger").fetchall() == [("forward", 1)]
        rows = db.execute("SELECT horizon, payload FROM open_nowcast_ledger").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == 0
    assert json.loads(rows[0][1])["forecast_close"] == 99.0


def test_sqlite_retains_post_observation_precision(tmp_path):
    path, save = fake_run(tmp_path)
    save()
    with sqlite3.connect(path) as db:
        observed, payload = db.execute("SELECT observed_at, payload FROM x_posts").fetchone()
    assert pd.Timestamp(observed) == pd.Timestamp("2026-11-13T21:00:00.000000001Z")
    assert json.loads(payload)["observed_at"] == observed


def test_sqlite_binds_only_real_price_sessions_to_strict_post_features(tmp_path):
    path, save = fake_run(tmp_path)
    post = {"post_id": "1", "session_date": date(2026, 11, 13)}
    save(post_features=pd.DataFrame([post]))
    with sqlite3.connect(path) as db:
        links = db.execute("""
            SELECT x.model_eligible, p.session_date
            FROM x_post_sessions s JOIN x_posts x USING (run_id, post_id)
            JOIN price_bars p USING (run_id, session_date)
        """).fetchall()
        assert links == [(1, "2026-11-13")]
    save(post_features=pd.DataFrame([{**post, "session_date": date(2026, 11, 12)}]))
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM x_post_sessions").fetchone() == (0,)
        assert db.execute("SELECT model_eligible FROM x_posts").fetchone() == (0,)


def test_news_snapshot_validation_drops_untrusted_presentation_and_rejects_forgery(monkeypatch):
    mock_response(monkeypatch, [{"title": "First &amp;lt;", "url": "https://example.com/a"}])
    batch = tavily.fetch_news_context("AAPL")
    expected = batch["headlines"]
    batch["headlines"] = [{"title": "Untrusted headline", "url": "https://evil.example"}]
    normalized = tavily.validate_news_context(batch, "AAPL")
    assert normalized["headlines"] == expected
    assert tavily.validate_news_context(normalized, "AAPL") == normalized
    with pytest.raises(DataError, match="context"):
        tavily.validate_news_context({**batch, "historical_features_eligible": True}, "AAPL")
    with pytest.raises(DataError, match="context"):
        tavily.validate_news_context({**batch, "collected_at_utc": "2099-01-01T00:00:00Z"}, "AAPL")

from datetime import date

import pandas as pd
import pytest

from cwt_quant.calendar import XNYSCalendar
from cwt_quant.config import Config
from cwt_quant.nowcast import open_nowcasts
from cwt_quant.x_analysis import sentiment_series, summarize_sentiment

from test_submission import END, snapshot
from cwt_quant.submission import evaluate, load_prices


def test_open_nowcast_excludes_current_close_high_low_volume_and_later_bars(tmp_path):
    path = tmp_path / "prices.json"
    snapshot(path)
    prices, _ = load_prices(path, "AAPL", END)
    start = date(2026, 5, 18)
    source = open_nowcasts(prices, Config(ticker="AAPL"), start)
    changed = prices.copy()
    target = pd.Timestamp("2026-08-04T16:00:00-04:00")
    changed.loc[target:, ["close", "high", "low", "volume"]] *= 1.5
    replay = open_nowcasts(changed, Config(ticker="AAPL"), start)
    cut = source.target_session <= target.date()
    pd.testing.assert_series_equal(source[cut].forecast_close, replay[cut].forecast_close)
    assert replay.loc[replay.target_session == target.date(), "actual_close"].iloc[0] > source.loc[
        source.target_session == target.date(), "actual_close"
    ].iloc[0]
    assert source.origin.iloc[0].hour == 9 and source.origin.iloc[0].minute == 30
    assert set(source.model) == {"no_change", "price_only"}


def test_retrospective_series_and_pit_series_are_separate_and_keep_missingness():
    cal = XNYSCalendar()
    days = [date(2026, 11, 25), date(2026, 11, 27), date(2026, 11, 30)]
    panel = pd.DataFrame({"session_date": days}, index=pd.DatetimeIndex(
        [cal.session_close_dt(day) for day in days], name="session_close",
    ))
    posts = pd.DataFrame({
        "created_at": pd.to_datetime(["2026-11-27T17:30:00Z", "2026-11-27T18:30:00Z"]),
        "observed_at": pd.to_datetime(["2026-12-01T00:00:00Z", "2026-12-01T00:00:00Z"]),
        "text": ["$AAPL bullish", "$AAPL bearish"],
    })
    series = sentiment_series(panel, posts, pd.DataFrame(), days[0], days[-1])
    assert series["retrospective_posts"].tolist() == [0, 1, 1]
    assert series["retrospective_mean"].iloc[0] != series["retrospective_mean"].iloc[0]
    assert series["strict_mean"].isna().all()
    summary = summarize_sentiment(series, days[-1])
    assert summary["retrospective"]["posts"] == 2
    assert summary["strict"]["mean"] is None


def test_replay_exports_actual_separate_nowcast_and_visible_withheld_x(tmp_path):
    path = tmp_path / "prices.json"
    snapshot(path)
    out = tmp_path / "out"
    manifest = evaluate("AAPL", END, path, out)
    latest = pd.read_csv(out / "open-nowcast.csv")
    assert list(latest.horizon.unique()) == [0]
    assert latest.loc[latest.target_session.eq(str(END)), "actual_close"].iloc[0] == pytest.approx(
        manifest["observed_close"]
    )
    assert (latest.origin.str.contains("09:30:00")).all()
    assert not pd.read_csv(out / "post-close-forecasts.csv").horizon.eq(0).any()
    assert manifest["sentiment_outlook"]["strict"]["mean"] is None
    assert (out / "x-coverage.json").is_file()
    assert (out / "x-versus-price.png").is_file()
    assert "opening nowcast" in (out / "outlook.md").read_text().lower()


def test_retrospective_export_changes_chart_series_but_never_price_predictions(tmp_path):
    import hashlib
    import json

    path = tmp_path / "prices.json"
    snapshot(path)
    export = tmp_path / "x.json"
    attestation = tmp_path / "x-manifest.json"
    export.write_text(json.dumps([{
        "id": "100", "author": {"id": "200"}, "text": "$AAPL bullish",
        "created_at": "2026-11-13T15:00:00Z", "observed_at": "2026-11-13T15:01:00Z",
        "likeCount": 9999, "viewCount": 99999,
    }]))
    attestation.write_text(json.dumps({
        "platform": "X", "source_name": "Apify", "acquisition_method": "authorized_local_export",
        "intended_asset": "AAPL", "intended_purpose": "research", "access_authorized": True,
        "rights_basis": "Fixture research permission", "dataset_id": "testDataset1",
        "retrieved_at_utc": "2026-11-15T12:00:00Z", "row_count": 1,
        "export_sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
        "historical_text_point_in_time_verified": False,
    }))
    empty, retrospective = tmp_path / "empty", tmp_path / "retrospective"
    evaluate("AAPL", END, path, empty)
    recorded = evaluate("AAPL", END, path, retrospective, export, attestation)
    for name in ("post-close-forecasts.csv", "open-nowcast.csv", "model_comparison.csv", "trade_ledger.csv"):
        assert (empty / name).read_bytes() == (retrospective / name).read_bytes()
    assert recorded["historical_x_status"] == "WITHHELD"
    assert recorded["sentiment_outlook"]["retrospective"]["posts"] == 1
    assert recorded["sentiment_outlook"]["strict"]["posts"] == 0
    rows = pd.read_csv(retrospective / "x-sentiment-series.csv")
    assert rows["retrospective_posts"].sum() == 1
    assert rows["strict_mean"].isna().all()


def test_validated_news_snapshot_roundtrip_cannot_change_forecasts(tmp_path, monkeypatch):
    import json
    import sqlite3

    from cwt_quant.connectors.tavily import fetch_news_context
    from cwt_quant.submission import main
    from test_news_storage import mock_response

    source = tmp_path / "prices"
    source.mkdir()
    snapshot(source / "AAPL.json")
    mock_response(monkeypatch, [{
        "title": "Company publishes results", "url": "https://example.com/results",
        "published_date": "2026-11-14",
    }])
    capture = tmp_path / "capture.json"
    capture.write_text(json.dumps(fetch_news_context("AAPL")))
    outputs = tmp_path / "runs"
    args = ["--ticker", "AAPL", "--end", str(END), "--prices-dir", str(source), "--out"]
    assert main([*args, str(outputs / "plain")]) == 0
    assert main([*args, str(outputs / "with-news"), "--news-snapshot", str(capture)]) == 0
    plain, news = outputs / "plain" / "AAPL", outputs / "with-news" / "AAPL"
    for name in ("post-close-forecasts.csv", "open-nowcast.csv", "x-sentiment-series.csv", "trade_ledger.csv"):
        assert (plain / name).read_bytes() == (news / name).read_bytes()
    assert "Company publishes results" in (news / "outlook.md").read_text()
    assert "Company publishes results" not in (plain / "outlook.md").read_text()
    with sqlite3.connect(news / "replay.sqlite3") as db:
        assert db.execute("select count(*) from open_nowcast_ledger").fetchone()[0] == 252
        assert db.execute("select count(*) from forecast_ledger").fetchone()[0] == 1221
        assert db.execute("select count(*) from news_captures").fetchone()[0] == 1
        assert db.execute("select count(*) from news_articles").fetchone()[0] == 1
        assert not db.execute("pragma foreign_key_check").fetchall()

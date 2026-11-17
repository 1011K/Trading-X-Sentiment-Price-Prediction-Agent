import json
import sqlite3
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from cwt_quant.calendar import XNYSCalendar
from cwt_quant.exceptions import DataError
from cwt_quant.submission import evaluate, evaluation_bounds, load_prices, main


END = date(2026, 11, 13)


def snapshot(path, ticker="AAPL"):
    start, _ = evaluation_bounds(END)
    rows = []
    for i, day in enumerate(XNYSCalendar().trading_days_between(start, END)):
        close = 100 + i * 0.15 + np.sin(i)
        rows.append({
            "date": str(day), "open": close - 0.1, "high": close + 1,
            "low": close - 1, "close": close, "adj_close": close,
            "volume": 1000, "dividends": 0, "splits": 0,
        })
    path.write_text(json.dumps({
        "provider": "Yahoo Finance via yfinance", "ticker": ticker, "currency": "USD",
        "instrument_type": "EQUITY", "exchange": "NMS",
        "retrieved_at_utc": "2026-11-15T12:00:00+00:00", "rows": rows,
    }))
    return rows


def test_exact_window_and_bad_price_rejected(tmp_path):
    path = tmp_path / "bars.json"
    snapshot(path)
    start, evaluation_start = evaluation_bounds(END)
    assert evaluation_start == date(2026, 5, 18)
    assert END - evaluation_start == timedelta(days=179)
    assert start < evaluation_start
    assert load_prices(path, "AAPL", END)[0].index[-1].date() == END
    dirty = json.loads(path.read_text())
    dirty["rows"].pop(15)
    path.write_text(json.dumps(dirty))
    with pytest.raises(DataError, match="session"):
        load_prices(path, "AAPL", END)


def test_replay_matches_origins_and_stores_observed_n0(tmp_path):
    path = tmp_path / "bars.json"
    rows = snapshot(path)
    out = tmp_path / "out"
    for _ in range(2):
        manifest = evaluate("AAPL", END, path, out)
        assert manifest["historical_x_status"] == "WITHHELD"
        assert manifest["evaluation_sessions"] == 126
    forecasts = pd.read_csv(out / "forecasts.csv")
    assert set(forecasts.horizon) == set(range(6))
    n0 = forecasts.loc[forecasts.horizon == 0].iloc[0]
    assert n0.model == "observed"
    assert n0.forecast_close == pytest.approx(rows[-1]["close"])
    assert n0.target_session == str(END)
    scores = pd.read_csv(out / "model_comparison.csv")
    assert set(scores.model) == {"no_change", "price_only"}
    assert scores.groupby("horizon").n.nunique().eq(1).all()
    assert scores.groupby("horizon").n.first().eq(121).all()
    with sqlite3.connect(out / "replay.sqlite3") as db:
        assert db.execute("select count(*) from price_bars").fetchone()[0] == len(rows)
        assert db.execute("select count(*) from forecast_ledger").fetchone()[0] == 1221
        assert db.execute("select count(*) from x_posts").fetchone()[0] == 0
    assert (out / "evaluation.md").exists()
    assert (out / "outlook.md").exists()
    assert (out / "price-and-models.png").exists()


def test_multi_ticker_cli_keeps_selected_symbols_isolated(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    snapshot(source / "AAPL.json", "AAPL")
    snapshot(source / "MSFT.json", "MSFT")
    out = tmp_path / "results"
    assert main(["--tickers", "AAPL", "MSFT", "--end", str(END),
                 "--prices-dir", str(source), "--out", str(out)]) == 0
    assert sorted(path.name for path in out.iterdir()) == ["AAPL", "MSFT"]
    assert json.loads((out / "MSFT" / "manifest.json").read_text())["ticker"] == "MSFT"


def test_apify_observation_gate_is_executable_end_to_end(tmp_path):
    import hashlib

    path = tmp_path / "bars.json"
    rows = snapshot(path)
    post_file = tmp_path / "x.json"
    meta_file = tmp_path / "x-manifest.json"
    records = [{
        "id": str(i + 1), "author": {"id": str(i + 1)},
        "text": "$AAPL bullish", "created_at": f"{row['date']}T15:00:00Z",
        "observed_at": f"{row['date']}T15:01:00Z", "viewCount": 5,
    } for i, row in enumerate(rows[75:120])]
    post_file.write_text(json.dumps(records))
    meta = {
        "platform": "X", "source_name": "Apify", "acquisition_method": "authorized_local_export",
        "intended_asset": "AAPL", "intended_purpose": "research", "access_authorized": True,
        "rights_basis": "Fixture research permission", "dataset_id": "testDataset1",
        "retrieved_at_utc": "2026-11-15T12:00:00Z", "row_count": len(records),
        "export_sha256": hashlib.sha256(post_file.read_bytes()).hexdigest(),
    }
    for attested, expected in [(False, "WITHHELD"), (True, "AVAILABLE")]:
        meta["historical_text_point_in_time_verified"] = attested
        meta_file.write_text(json.dumps(meta))
        out = tmp_path / expected
        manifest = evaluate("AAPL", END, path, out, post_file, meta_file)
        assert manifest["historical_x_status"] == expected
        comparison = pd.read_csv(out / "model_comparison.csv")
        assert ("price_sentiment" in set(comparison.model)) == attested
        assert comparison.groupby("horizon").n.nunique().eq(1).all()
        assert "price_influence" not in set(comparison.model)
        with sqlite3.connect(out / "replay.sqlite3") as db:
            assert db.execute("select count(*) from x_posts").fetchone()[0] == len(records)
            assert db.execute("select sum(model_eligible) from x_posts").fetchone()[0] == (
                len(records) if attested else 0
            )


def test_tavily_context_uses_fixed_endpoint_and_filters_credentials(monkeypatch):
    from cwt_quant.connectors import tavily

    request = {}
    dummy = "test-key-for-a-mock"

    class Client:
        def __init__(self, host, timeout):
            request["host"] = host

        def request(self, method, path, body, headers):
            request.update(headers=headers, path=path, body=body)

        def getresponse(self):
            from types import SimpleNamespace
            payload = {"results": [
                {"title": "Company publishes results", "url": "https://example.com/results?q=track"},
                {"title": dummy, "url": "https://example.com/redacted"},
            ]}
            return SimpleNamespace(status=200, read=lambda: json.dumps(payload).encode())

        def close(self):
            pass

    monkeypatch.setenv("TAVILY_API_KEY", dummy)
    monkeypatch.setattr(tavily.http.client, "HTTPSConnection", Client)
    context = tavily.fetch_news_context("AAPL")
    assert context["historical_features_eligible"] is False
    assert context["headlines"] == [
        {"title": "Company publishes results", "url": "https://example.com/results"},
    ]
    assert dummy not in json.dumps(context)
    assert request["host"] == "api.tavily.com"
    assert request["path"] == "/search"
    assert request["headers"]["Authorization"] == f"Bearer {dummy}"
    assert dummy not in request["body"]

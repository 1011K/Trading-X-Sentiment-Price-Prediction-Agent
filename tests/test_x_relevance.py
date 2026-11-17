import pandas as pd
import pytest

from cwt_quant.calendar import XNYSCalendar
from cwt_quant.config import Config
from cwt_quant.features import build_post_features
from test_x_export import _load, _row


def test_company_terms_keep_normalized_relevance_without_faking_cashtags(tmp_path):
    text = [
        "$AAPL bullish", "Apple Inc reported quarterly growth", "AAPL shares rose",
        "Apple earnings beat expectations", "apple pie is bullish",
        "AAPL $AAPLONG $AAPL.X", "Appleton earnings rise", "https://example.com/Apple-stock",
    ]
    rows = [_row(id=str(i), text=body) for i, body in enumerate(text, start=1)]
    posts, meta = _load(tmp_path, rows, overrides={"historical_text_point_in_time_verified": True})
    assert posts.post_id.tolist() == ["1", "2", "3", "4"]
    assert posts.has_cashtag.tolist() == [True, False, False, False]
    assert meta["relevance_counts"] == {"cashtag": 1, "issuer_keyword": 2, "ticker_context": 1}
    features = build_post_features(posts, pd.DataFrame(), Config(), XNYSCalendar())
    assert features.post_id.tolist() == ["1", "2", "3"]
    assert not features.influence_valid.any()


def test_keyword_text_can_be_described_but_late_observation_cannot_be_backdated(tmp_path):
    posts, _ = _load(
        tmp_path, [_row(text="Apple earnings rally", observed_at="2026-11-13T21:15:00Z")],
        overrides={"historical_text_point_in_time_verified": True},
    )
    assert posts.relevance_basis.tolist() == ["issuer_keyword"]
    assert build_post_features(posts, pd.DataFrame(), Config(), XNYSCalendar()).empty


def test_authorized_public_archive_preserves_unknowns_and_cannot_assert_cutoff(tmp_path):
    from cwt_quant.exceptions import ProvenanceError

    archive = {
        "source_name": "Community Archive",
        "source_url": "https://example.com/public-export",
        "acquisition_method": "authorized_archive_export",
    }
    rows = [_row(text="Apple Inc increases dividend", viewCount=None)]
    posts, meta = _load(tmp_path, rows, overrides=archive)
    assert meta["provenance"] == "authorized_x_archive"
    assert meta["source_url"] == archive["source_url"]
    assert pd.isna(posts.loc[0, "observed_at"]) and pd.isna(posts.loc[0, "views"])
    assert build_post_features(posts, pd.DataFrame(), Config(), XNYSCalendar()).empty
    with pytest.raises(ProvenanceError, match="retrospective"):
        _load(tmp_path, rows, overrides={**archive, "historical_text_point_in_time_verified": True})
    with pytest.raises(ProvenanceError, match="public source URL"):
        _load(tmp_path, rows, overrides={**archive, "source_url": "https://a:b@example.com"})


def test_submission_persists_and_logs_missing_fill_warning(tmp_path, monkeypatch, caplog):
    from datetime import date

    from cwt_quant import backtest
    from cwt_quant.submission import evaluate
    from test_submission import END, snapshot

    source = tmp_path / "prices.json"
    snapshot(source)
    out = tmp_path / "out"

    def missing_fill(*_args, **_kwargs):
        raise backtest.TradingFillError(date(2026, 5, 19), "missing_fill_bar", "No price bar on fill date")

    monkeypatch.setattr(backtest, "trading_diagnostic", missing_fill)
    result = evaluate("AAPL", END, source, out)
    assert result["risk"]["price_only"]["fill_issues"] == [{
        "session_date": "2026-05-19", "reason": "missing_fill_bar", "detail": "No price bar on fill date",
    }]
    assert "2026-05-19: missing_fill_bar" in (out / "evaluation.md").read_text()
    assert "price_only trading risk withheld" in caplog.text

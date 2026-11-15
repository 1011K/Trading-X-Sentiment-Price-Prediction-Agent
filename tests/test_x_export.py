import csv
import hashlib
import json

import pandas as pd
import pytest

from cwt_quant.calendar import XNYSCalendar
from cwt_quant.config import Config
from cwt_quant.exceptions import DataError, ProvenanceError
from cwt_quant.features import build_post_features
from cwt_quant.validation import validate_posts


def _load(tmp_path, rows, *, suffix="json", overrides=None):
    from cwt_quant.x_export import load_x_export

    path = tmp_path / f"export.{suffix}"
    if suffix == "json":
        path.write_text(json.dumps(rows), encoding="utf-8")
    elif suffix == "jsonl":
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    else:
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    manifest = {
        "platform": "X",
        "source_name": "Apify",
        "acquisition_method": "authorized_local_export",
        "rights_basis": "Provider license permits this local research import",
        "access_authorized": True,
        "intended_asset": "AAPL",
        "intended_purpose": "research",
        "dataset_id": "exampleDataset",
        "retrieved_at_utc": "2026-11-13T21:30:00Z",
        "historical_text_point_in_time_verified": False,
        "row_count": len(rows),
        "export_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    manifest.update(overrides or {})
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return load_x_export(path, manifest_path, "AAPL")


def _row(**overrides):
    return {
        "id": "123",
        "createdAt": "Fri Nov 13 15:00:00 +0000 2026",
        "observed_at": "2026-11-13T15:15:00Z",
        "authorId": "456",
        "text": "$aapl bullish",
        "likeCount": 7,
        **overrides,
    }


@pytest.mark.parametrize("suffix", ["json", "jsonl", "csv"])
def test_retrospective_export_has_provenance_and_cannot_enter_features(tmp_path, suffix):
    rows = [_row(), _row(), _row(id="124", text="AAPL $AAPLONG $AAPL.X")]
    posts, meta = _load(tmp_path, rows, suffix=suffix)

    assert posts["post_id"].tolist() == ["123"]
    assert posts.attrs["source_hash"] == meta["export_sha256"]
    assert meta["historical_eligible"] is False
    assert meta["raw_rows"] == 3
    assert pd.isna(posts.loc[0, "observed_at"])
    assert posts.loc[0, "acquired_at"] == pd.Timestamp("2026-11-13T21:30:00Z")
    assert posts.loc[0, "likes"] == 7
    assert pd.isna(posts.loc[0, "reposts"])
    assert validate_posts(posts, Config()) == []
    assert build_post_features(posts, pd.DataFrame(), Config(), XNYSCalendar()).empty


def test_attested_text_respects_close_and_never_uses_retrieved_engagement(tmp_path):
    posts, meta = _load(
        tmp_path,
        [_row(), _row(id="124", observed_at="2026-11-13T21:15:00Z")],
        overrides={"historical_text_point_in_time_verified": True},
    )

    assert meta["historical_eligible"] is True
    features = build_post_features(posts, pd.DataFrame(), Config(), XNYSCalendar())
    assert features["post_id"].tolist() == ["123"]
    assert not features["influence_valid"].any()


@pytest.mark.parametrize(
    "overrides",
    [
        {"access_authorized": "true"},
        {"dataset_id": ""},
        {"rights_basis": "REPLACE_WITH_RIGHTS"},
        {"intended_asset": "AA"},
        {"intended_purpose": ""},
        {"retrieved_at_utc": "2026-11-13 21:30:00"},
        {"historical_text_point_in_time_verified": 1},
        {"row_count": 2},
        {"export_sha256": "0" * 64},
    ],
)
def test_bad_manifest_fails_closed(tmp_path, overrides):
    with pytest.raises(ProvenanceError):
        _load(tmp_path, [_row()], overrides=overrides)


@pytest.mark.parametrize(
    "row",
    [
        _row(createdAt="2026-11-13 15:00:00"),
        _row(createdAt="2026-11-13T15:00:00+00:60"),
        _row(createdAt="2026-11-14T15:00:00Z"),
        _row(id=123.0),
        _row(likeCount=1.2),
        _row(likeCount=-1),
    ],
)
def test_bad_rows_fail_closed(tmp_path, row):
    with pytest.raises(DataError):
        _load(tmp_path, [row])


@pytest.mark.parametrize("observed", ["", "2026-11-13T14:59:00Z", "2026-11-13T21:31:00Z"])
def test_attested_observation_requires_row_evidence(tmp_path, observed):
    with pytest.raises(ProvenanceError):
        _load(
            tmp_path,
            [_row(observed_at=observed)],
            overrides={"historical_text_point_in_time_verified": True},
        )


def test_conflicting_duplicate_cannot_hide_behind_ticker_filter(tmp_path):
    with pytest.raises(DataError, match="Conflicting"):
        _load(tmp_path, [_row(), _row(text="$MSFT bullish")])


def test_download_authorized_dataset_uses_header_and_pagination(tmp_path, monkeypatch):
    import io
    from cwt_quant import x_export

    calls = []

    class Connection:
        def __init__(self, host, *, timeout):
            assert host == "api.apify.com"
            assert timeout > 0

        def request(self, method, path, *, headers):
            calls.append((method, path, headers))

        def getresponse(self):
            offset = len(calls) - 1
            response = io.BytesIO(json.dumps([_row(id=str(offset + 1))]).encode())
            response.status = 200
            response.getheader = {
                "X-Apify-Pagination-Total": "2",
                "X-Apify-Pagination-Count": "1",
                "X-Apify-Pagination-Offset": str(offset),
            }.get
            return response

        def close(self):
            pass

    monkeypatch.setenv("APIFY_TOKEN", "test-token")
    monkeypatch.setattr(x_export.http.client, "HTTPSConnection", Connection)
    path = tmp_path / "download.json"
    provenance = x_export.download_authorized_apify_dataset(
        "dataset", path, ticker="AAPL", rights_basis="Permission for local research",
    )

    assert len(calls) == 2
    for offset, (method, request_path, headers) in enumerate(calls):
        assert method == "GET"
        assert request_path.startswith("/v2/datasets/dataset/items?")
        assert f"offset={offset}" in request_path
        assert "test-token" not in request_path
        assert headers["Authorization"] == "Bearer test-token"
    assert [row["id"] for row in json.loads(path.read_text())] == ["1", "2"]
    assert provenance["row_count"] == 2
    assert provenance["export_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert provenance["historical_text_point_in_time_verified"] is False
    assert "test-token" not in repr(provenance)

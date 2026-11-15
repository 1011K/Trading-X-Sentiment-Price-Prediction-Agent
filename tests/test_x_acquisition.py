import io
import json
from datetime import date

import pandas as pd
import pytest

from cwt_quant import apify_runs, x_export
from cwt_quant.exceptions import DataError, ProvenanceError
from test_x_export import _load, _row


END = date(2026, 11, 13)


def test_plan_covers_180_new_york_dates_with_utc_padding_in_provider_sized_batch():
    plan = apify_runs.query_plan("AAPL", END, max_items=2000, keyword="Apple Inc")
    assert plan["window"] == {
        "start_date": "2026-05-18", "end_date": "2026-11-13", "timezone": "America/New_York",
    }
    with pytest.raises(DataError, match="must have ended"):
        apify_runs.query_plan("AAPL", date.max)
    with pytest.raises(DataError, match="outside supported dates"):
        apify_runs.query_plan("AAPL", date.min)
    assert plan["query_end_utc_exclusive"] == "2026-11-15"
    assert plan["actor_input"] == {
        "searchTerms": [
            '($AAPL OR AAPL OR "Apple Inc") since:2026-05-18 until:2026-07-02 -filter:retweets',
            '($AAPL OR AAPL OR "Apple Inc") since:2026-07-02 until:2026-08-16 -filter:retweets',
            '($AAPL OR AAPL OR "Apple Inc") since:2026-08-16 until:2026-09-30 -filter:retweets',
            '($AAPL OR AAPL OR "Apple Inc") since:2026-09-30 until:2026-11-15 -filter:retweets',
        ], "sort": "Latest", "maxItems": 2000,
    }


def test_coverage_distinguishes_utc_and_new_york_at_window_boundaries(tmp_path):
    posts, meta = _load(tmp_path, [
        _row(createdAt="2026-05-18T00:15:00Z"),
        _row(id="124", createdAt="2026-11-13T15:00:00Z"),
        _row(id="125", createdAt="2026-11-14T01:00:00Z"),
    ], overrides={"retrieved_at_utc": "2026-11-14T03:00:00Z"})
    audit = x_export.coverage_audit(posts, date(2026, 5, 18), END, meta)
    assert audit["matched_posts"] == 3
    assert audit["in_window_posts"] == 2
    assert audit["outside_window_posts"] == 1
    assert audit["pit_timestamped_posts"] == 0
    assert len(audit["daily"]) == 180
    assert audit["daily"][0]["posts"] == 0
    assert audit["daily"][-1]["posts"] == 2
    assert audit["daily"][0]["utc_posts"] == 1
    assert audit["daily"][-1]["utc_posts"] == 1
    assert audit["days_with_posts"] == 1
    assert audit["coverage_independently_verified"] is False


def test_future_retrieval_and_overlapping_aliases_fail_closed(tmp_path):
    with pytest.raises(ProvenanceError, match="future"):
        _load(tmp_path, [_row()], overrides={"retrieved_at_utc": "2126-11-13T21:30:00Z"})
    with pytest.raises(DataError, match="aliases"):
        _load(tmp_path, [_row(post_id="999")])


def test_actor_output_requires_retrospective_classification_and_valid_run_timing(tmp_path):
    run = {
        "actor_name": x_export.ACTOR_NAME, "actor_id": "actorID",
        "dataset_id": "exampleDataset", "run_id": "completedRun", "build_id": "buildID",
        "started_at_utc": "2026-11-14T09:00:00Z", "finished_at_utc": "2026-11-14T09:01:00Z",
        "query_start_date": "2026-05-18", "query_end_date": "2026-11-13",
        "search_terms": apify_runs.query_plan("AAPL", END)["actor_input"]["searchTerms"],
        "sort": "Latest", "max_items": 2000,
    }
    base = {"actor_run": run, "retrieved_at_utc": "2026-11-15T12:00:00Z"}
    with pytest.raises(ProvenanceError, match="retrospective"):
        _load(tmp_path, [_row()], overrides={**base, "historical_text_point_in_time_verified": True})
    with pytest.raises(ProvenanceError, match="ended"):
        _load(tmp_path, [_row()], overrides={**base, "actor_run": {
            **run, "started_at_utc": "2026-11-13T09:00:00Z",
        }})
    with pytest.raises(DataError, match="after the actor run"):
        _load(tmp_path, [_row(createdAt="2026-11-14T15:00:00Z")], overrides=base)


def test_existing_run_import_binds_actor_build_dataset_and_input(monkeypatch, tmp_path):
    calls = []
    actor_input = apify_runs.query_plan("AAPL", END, keyword="Apple Inc")["actor_input"]

    class Connection:
        def __init__(self, host, *, timeout):
            assert host == "api.apify.com"

        def request(self, method, path, *, headers):
            assert method == "GET"
            assert headers["Authorization"] == "Bearer test-token"
            assert "test-token" not in path
            self.path = path
            calls.append(path)

        def getresponse(self):
            if self.path == "/v2/actors/apidojo~tweet-scraper":
                body = {"data": {"id": "actorId", "username": "apidojo", "name": "tweet-scraper"}}
            elif self.path == "/v2/actor-runs/completedRun":
                body = {"data": {
                    "id": "completedRun", "actId": "actorId", "status": "SUCCEEDED",
                    "privateAPIKey": "do-not-record", "buildId": "buildID", "defaultDatasetId": "datasetID", "defaultKeyValueStoreId": "kvStore",
                    "startedAt": "2026-11-14T09:00:00Z", "finishedAt": "2026-11-14T09:01:00Z",
                }}
            elif self.path == "/v2/key-value-stores/kvStore/records/INPUT":
                body = actor_input
            elif self.path.startswith("/v2/datasets/datasetID/items?"):
                body = [_row()]
            else:
                pytest.fail(f"unexpected Apify path {self.path}")
            result = io.BytesIO(json.dumps(body).encode())
            result.status = 200
            result.getheader = {
                "X-Apify-Pagination-Total": "1", "X-Apify-Pagination-Count": "1",
                "X-Apify-Pagination-Offset": "0", "X-Apify-Pagination-Desc": "false",
            }.get
            return result

        def close(self):
            pass

    monkeypatch.setenv("APIFY_TOKEN", "test-token")
    monkeypatch.setattr(x_export.http.client, "HTTPSConnection", Connection)
    path, manifest_path = tmp_path / "dataset.json", tmp_path / "manifest.json"
    apify_runs.import_authorized_run("completedRun", path, manifest_path,
                                     ticker="AAPL", end=END, rights_basis="Authorized research licence",
                                     keyword="Apple Inc")
    assert len(calls) == 4
    posts, source = x_export.load_x_export(path, manifest_path, "AAPL")
    assert len(posts) == 1
    assert pd.isna(posts.loc[0, "observed_at"])
    assert source["actor_run"]["run_id"] == "completedRun"
    assert source["actor_run"]["build_id"] == "buildID"
    assert source["actor_run"]["search_terms"] == actor_input["searchTerms"]
    assert source["actor_run"]["dataset_id"] == "datasetID"
    assert x_export.coverage_audit(posts, date(2026, 5, 18), END, source)["actor_query_window_matches"]
    assert "do-not-record" not in manifest_path.read_text()
    assert "test-token" not in manifest_path.read_text()

    actor_input["searchTerms"] = ["$AAPL since:2026-10-01 until:2026-11-14"]
    bad = tmp_path / "bad.json"
    with pytest.raises(ProvenanceError, match="query plan"):
        apify_runs.import_authorized_run("completedRun", bad, tmp_path / "bad-manifest.json",
                                         ticker="AAPL", end=END, rights_basis="Authorized research licence",
                                         keyword="Apple Inc")
    assert not bad.exists()

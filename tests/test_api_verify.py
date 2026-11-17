import hashlib
import http.client
import json

import pytest

from cwt_quant.api_verify import main


APIFY_KEY = "apify_api_test_secret_only"
TAVILY_KEY = "tvly-test-secret-only-value"


@pytest.fixture
def requests(monkeypatch):
    class Connection:
        pending = []
        seen = []

        def __init__(self, host, timeout):
            self.host = host

        def request(self, method, path, body=None, headers=None):
            self.seen.append((self.host, method, path, headers["Authorization"]))

        def getresponse(self):
            response = Response(*self.pending.pop(0))
            return response

        def close(self):
            pass

    class Response:
        def __init__(self, status, raw, headers=None):
            self.status = status
            self.raw = raw if isinstance(raw, bytes) else json.dumps(raw).encode()
            self.headers = headers or {}

        def read(self, limit=None):
            return self.raw[:limit]

        def getheader(self, name):
            return self.headers.get(name)

    monkeypatch.setattr(http.client, "HTTPSConnection", Connection)
    monkeypatch.setenv("APIFY_TOKEN", APIFY_KEY)
    monkeypatch.setenv("TAVILY_API_KEY", TAVILY_KEY)
    return Connection


def record(tmp_path, args):
    out = tmp_path / "receipt.json"
    status = main([*args, "--out", str(out)])
    raw = out.read_text()
    assert APIFY_KEY not in raw and TAVILY_KEY not in raw
    receipt = json.loads(raw)
    assert receipt["historical_x_status"] == "WITHHELD"
    assert receipt["actor_started"] is False
    return status, receipt["checks"]


def usage(*, remaining=True, paid=False):
    return {
        "account": {"current_plan": "Researcher", "plan_usage": 3 if remaining else 1000,
                    "plan_limit": 1000, "paygo_usage": 0, "paygo_limit": 100 if paid else None},
        "key": {"usage": 3, "limit": None},
    }


@pytest.mark.parametrize("operation, variable", [("apify-auth", "APIFY_TOKEN"), ("tavily-search", "TAVILY_API_KEY")])
def test_missing_credentials_do_not_send_requests(tmp_path, monkeypatch, requests, operation, variable):
    monkeypatch.delenv(variable)
    status, checks = record(tmp_path, [operation])
    assert status == 1 and not requests.seen
    assert checks[0]["outcome"] == "MISSING_CREDENTIAL"
    assert checks[0]["http_status"] is None and checks[0]["executed_at_utc"] is None


def test_apify_auth_rejects_http_failure_without_error_body(tmp_path, requests, capsys):
    requests.pending = [(401, {"message": APIFY_KEY, "other": "private-error-body"})]
    status, checks = record(tmp_path, ["apify-auth"])
    assert status == 1 and checks[0]["http_status"] == 401
    assert checks[0]["outcome"] == "HTTP_ERROR"
    assert "private-error-body" not in capsys.readouterr().err


def test_apify_inventory_uses_safe_counts_and_never_starts_actor(tmp_path, requests):
    requests.pending = [
        (200, {"data": {"id": "Account01", "email": "private@example.com", "token": APIFY_KEY}}),
        (200, {"data": {"total": 0, "count": 0, "items": []}}),
        (200, {"data": {"total": 1, "count": 1, "items": [{"id": APIFY_KEY}]}}),
    ]
    status, checks = record(tmp_path, ["apify-auth", "--inventory"])
    assert status == 0 and len(checks) == 3
    assert all(request[1] == "GET" for request in requests.seen)
    assert checks[0]["outcome"] == "VERIFIED"
    assert checks[1]["result_count"] == 0 and checks[2]["result_count"] == 1
    assert "private@example.com" not in json.dumps(checks)


def test_apify_malformed_success_is_a_failure(tmp_path, requests):
    raw = b"{broken"
    requests.pending = [(200, raw)]
    status, checks = record(tmp_path, ["apify-auth"])
    assert status == 1 and checks[0]["outcome"] == "MALFORMED_RESPONSE"
    assert checks[0]["http_status"] == 200 and checks[0]["response_sha256"] == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("response", [usage(remaining=False), usage(paid=True), {"account": {}}])
def test_tavily_search_fails_closed_without_free_allowance(tmp_path, requests, response):
    requests.pending = [(200, response)]
    status, checks = record(tmp_path, ["tavily-search"])
    assert status == 1 and len(requests.seen) == 1
    assert checks[-1]["outcome"] == "FREE_USAGE_NOT_VERIFIED"
    assert checks[-1]["executed_at_utc"] is None


def test_tavily_search_records_real_http_shape_without_publishing_headlines(tmp_path, requests):
    requests.pending = [(200, usage()), (200, {"results": [
        {"title": "Private headline for the test", "url": "https://example.com/article"},
        {"title": TAVILY_KEY, "url": "https://example.com/echo"},
    ]})]
    status, checks = record(tmp_path, ["tavily-search"])
    assert status == 0
    assert [r[1] for r in requests.seen] == ["GET", "POST"]
    assert checks[-1]["http_status"] == 200 and checks[-1]["result_count"] == 2
    assert checks[-1]["usable_article_count"] == 1 and len(checks[-1]["response_sha256"]) == 64
    assert "Private headline" not in json.dumps(checks)
    assert "example.com/echo" not in json.dumps(checks)


def test_tavily_malformed_search_does_not_pass(tmp_path, requests):
    requests.pending = [(200, usage()), (200, {"results": {"token": TAVILY_KEY}})]
    status, checks = record(tmp_path, ["tavily-search"])
    assert status == 1 and checks[-1]["outcome"] == "REQUEST_FAILED"
    assert checks[-1]["http_status"] == 200 and len(checks[-1]["response_sha256"]) == 64


def test_verified_apify_dataset_read_preserves_historical_withholding(tmp_path, requests):
    requests.pending = [(200, [{
        "id": "100", "author": {"id": "200"},
        "text": "$AAPL authored test specimen", "created_at": "2026-11-11T15:00:00Z",
    }], {"X-Apify-Pagination-Total": "1", "X-Apify-Pagination-Count": "1", "X-Apify-Pagination-Offset": "0"})]
    status, checks = record(tmp_path, [
        "apify-dataset", "--dataset-id", "Dataset01", "--rights-basis", "Test fixture author",
        "--confirm-included-storage",
    ])
    assert status == 0 and checks[0]["dataset_id"] == "Dataset01"
    assert checks[0]["result_count"] == 1 and checks[0]["ticker_matched_count"] == 1
    assert checks[0]["http_status"] == 200 and len(checks[0]["export_sha256"]) == 64
    assert "authored test specimen" not in json.dumps(checks)


def apify_free_plan(*, cap=5):
    return {"data": {"id": "Account01", "plan": {
        "id": "FREE", "isEnabled": True, "monthlyBasePriceUsd": 0,
        "monthlyUsageCreditsUsd": 5, "maxMonthlyUsageUsd": cap,
    }}}


def test_apify_demo_requires_proven_no_overage(tmp_path, requests):
    requests.pending = [(200, apify_free_plan(cap=6))]
    out = tmp_path / "demo.json"
    assert main(["apify-demo", "--out", str(out)]) == 1
    assert len(requests.seen) == 1
    assert json.loads(out.read_text())["actor_started"] is False


def test_apify_demo_runs_only_official_hello_world_and_checks_output(tmp_path, requests):
    requests.pending = [
        (200, apify_free_plan()),
        (200, {"data": {"totalUsageCreditsUsdAfterVolumeDiscount": 0.01}}),
        (201, {"data": {"id": "DemoRun01", "buildId": "DemoBuild01", "status": "SUCCEEDED",
                        "defaultKeyValueStoreId": "DemoStore01", "defaultDatasetId": "DemoDataset01"}}),
        (200, {"message": "Hello world!"}),
    ]
    out = tmp_path / "demo.json"
    assert main(["apify-demo", "--out", str(out)]) == 0
    raw = out.read_text()
    assert APIFY_KEY not in raw and "Account01" not in raw
    receipt = json.loads(raw)
    assert receipt["actor_started"] is True and receipt["historical_x_status"] == "WITHHELD"
    assert receipt["checks"][-1]["run_id"] == "DemoRun01"
    assert [r[1] for r in requests.seen] == ["GET", "GET", "POST", "GET"]
    assert requests.seen[2][2].startswith("/v2/acts/apify~hello-world/runs?")


def test_demo_dataset_validates_generic_rows_without_claiming_x_ingestion(tmp_path, requests):
    requests.pending = [(200, [{"message": "demo content"}], {
        "X-Apify-Pagination-Total": "1", "X-Apify-Pagination-Count": "1", "X-Apify-Pagination-Offset": "0",
    })]
    status, checks = record(tmp_path, [
        "apify-dataset", "--demo-records", "--dataset-id", "Dataset01",
        "--rights-basis", "Owned demo storage", "--confirm-included-storage",
    ])
    assert status == 0 and checks[0]["result_count"] == 1
    assert checks[0]["phase"] == "authorized_demo_dataset_read"
    assert "ticker_matched_count" not in checks[0]
    assert "demo content" not in json.dumps(checks)


def test_transport_failure_does_not_echo_exception(tmp_path, requests, monkeypatch, capsys):
    def failed_response(self):
        raise OSError("private transport details " + APIFY_KEY)

    monkeypatch.setattr(requests, "getresponse", failed_response)
    status, checks = record(tmp_path, ["apify-auth"])
    assert status == 1 and checks[0]["outcome"] == "REQUEST_FAILED"
    assert checks[0]["http_status"] is None and checks[0]["executed_at_utc"]
    messages = capsys.readouterr()
    assert APIFY_KEY not in messages.out + messages.err


def test_dataset_with_echoed_credential_fails_ingestion(tmp_path, requests):
    requests.pending = [(200, [{"message": APIFY_KEY}], {
        "X-Apify-Pagination-Total": "1", "X-Apify-Pagination-Count": "1", "X-Apify-Pagination-Offset": "0",
    })]
    status, checks = record(tmp_path, [
        "apify-dataset", "--demo-records", "--dataset-id", "Dataset01",
        "--rights-basis", "Owned demo storage", "--confirm-included-storage",
    ])
    assert status == 1 and checks[0]["outcome"] == "INGESTION_FAILED"
    assert "export_sha256" not in checks[0]

"""Verify providers and write sanitized, credential-free receipts."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import http.client
import json
from math import isfinite
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from .connectors.tavily import fetch_news_context, validate_news_context
from .exceptions import CWTQuantError

APIFY = "api.apify.com"
TAVILY = "api.tavily.com"
MAX_RECEIPT_RESPONSE = 1_000_000


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _receipt(provider: str, host: str, path: str, phase: str, method: str = "GET") -> dict:
    return {
        "provider": provider, "phase": phase, "method": method, "endpoint": f"https://{host}{path}",
        "executed_at_utc": None, "http_status": None, "result_count": None,
        "response_sha256": None, "outcome": "NOT_RUN",
    }


def _request(host: str, path: str, key: str, receipt: dict) -> dict | None:
    if not key:
        receipt["outcome"] = "MISSING_CREDENTIAL"
        return None
    try:
        method = receipt["method"]
        headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
        body = None
        if method == "POST":
            body = "{}"
            headers["Content-Type"] = "application/json"
        with closing(http.client.HTTPSConnection(host, timeout=45 if body else 20)) as client:
            receipt["executed_at_utc"] = _utc()
            client.request(method, path, body=body, headers=headers)
            response = client.getresponse()
            receipt["http_status"] = response.status
            if response.status != (201 if method == "POST" else 200):
                receipt["outcome"] = "HTTP_ERROR"
                return None
            raw = response.read(MAX_RECEIPT_RESPONSE + 1)
    except (OSError, ValueError, http.client.HTTPException):
        receipt["outcome"] = "REQUEST_FAILED"
        return None
    if len(raw) <= MAX_RECEIPT_RESPONSE:
        receipt["response_sha256"] = sha256(raw).hexdigest()
        try:
            payload = json.loads(raw)
        except (ValueError, RecursionError):
            payload = None
        if isinstance(payload, dict):
            return payload
    receipt["outcome"] = "MALFORMED_RESPONSE"
    return None


def _apify_checks(key: str, inventory: bool) -> list[dict]:
    path = "/v2/users/me"
    auth = _receipt("Apify", APIFY, path, "authentication")
    checks = [auth]
    payload = _request(APIFY, path, key, auth)
    if payload is None:
        return checks
    account = payload.get("data")
    if not isinstance(account, dict) or not isinstance(account.get("id"), str) or not account["id"]:
        auth["outcome"] = "MALFORMED_RESPONSE"
        return checks
    auth.update(outcome="VERIFIED", result_count=1)
    if inventory:
        for name, path in (
            ("run_inventory", "/v2/actor-runs?limit=10&desc=1"),
            ("dataset_inventory", "/v2/datasets?limit=10&desc=1&unnamed=1"),
        ):
            receipt = _receipt("Apify", APIFY, path, name)
            checks.append(receipt)
            payload = _request(APIFY, path, key, receipt)
            if payload is None:
                continue
            page = payload.get("data")
            items = page.get("items") if isinstance(page, dict) else None
            if (not isinstance(items, list) or not all(isinstance(item, dict) for item in items)
                    or type(page.get("count")) is not int or type(page.get("total")) is not int
                    or page["count"] != len(items) or not len(items) <= min(10, page["total"])):
                receipt["outcome"] = "MALFORMED_RESPONSE"
                continue
            receipt.update(outcome="VERIFIED", result_count=len(items), inventory_total=page["total"])
    return checks


def _safe_id(value: object) -> bool:
    keys = (os.environ.get(name, "").strip() for name in ("APIFY_TOKEN", "TAVILY_API_KEY"))
    return (isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) is not None
            and not any(key and key in value for key in keys))


def _apify_demo(key: str) -> list[dict]:
    auth = _receipt("Apify", APIFY, "/v2/users/me", "authentication")
    payload = _request(APIFY, "/v2/users/me", key, auth)
    if payload is None:
        return [auth]
    account = payload.get("data")
    if not isinstance(account, dict) or not _safe_id(account.get("id")):
        auth["outcome"] = "MALFORMED_RESPONSE"
        return [auth]
    plan = account.get("plan")
    free = isinstance(plan, dict) and plan.get("id") == "FREE" and plan.get("isEnabled") is True
    included = plan.get("monthlyUsageCreditsUsd") if free else None
    maximum = plan.get("maxMonthlyUsageUsd") if free else None
    no_overage = (type(included) in (int, float) and type(maximum) in (int, float)
                  and isfinite(included) and isfinite(maximum)
                  and 0 < maximum <= included and plan.get("monthlyBasePriceUsd") == 0)
    auth.update(outcome="VERIFIED", result_count=1, free_plan=free, usage_cap_within_included=no_overage)
    run_path = "/v2/acts/apify~hello-world/runs?memory=128&timeout=30&waitForFinish=30"
    run = _receipt("Apify", APIFY, run_path, "hello_world_actor", method="POST")
    run["actor_name"] = "apify/hello-world"
    if not no_overage:
        run["outcome"] = "FREE_USAGE_NOT_VERIFIED"
        return [auth, run]
    usage = _receipt("Apify", APIFY, "/v2/users/{authenticated-user}/usage/monthly", "included_usage")
    payload = _request(APIFY, f"/v2/users/{account['id']}/usage/monthly", key, usage)
    data = payload.get("data") if payload else None
    spent = data.get("totalUsageCreditsUsdAfterVolumeDiscount") if isinstance(data, dict) else None
    if type(spent) not in (int, float) or not 0 <= spent <= maximum:
        if payload is not None:
            usage["outcome"] = "MALFORMED_RESPONSE"
        run["outcome"] = "FREE_USAGE_NOT_VERIFIED"
        return [auth, usage, run]
    usage.update(outcome="VERIFIED", result_count=1, remaining_at_least_10_cents=maximum - spent >= 0.10)
    if not usage["remaining_at_least_10_cents"]:
        run["outcome"] = "FREE_USAGE_NOT_VERIFIED"
        return [auth, usage, run]

    checks = [auth, usage, run]
    payload = _request(APIFY, run_path, key, run)
    data = payload.get("data") if payload else None
    if not isinstance(data, dict) or not _safe_id(data.get("id")):
        if payload is not None:
            run["outcome"] = "MALFORMED_RESPONSE"
        return checks
    run_id = data["id"]
    run.update(outcome="VERIFIED", result_count=1, run_id=run_id)
    settled = run
    if data.get("status") in ("READY", "RUNNING", "TIMING-OUT", "ABORTING"):
        status_path = f"/v2/actor-runs/{run_id}?waitForFinish=10"
        settled = _receipt("Apify", APIFY, status_path, "actor_status")
        checks.append(settled)
        payload = _request(APIFY, status_path, key, settled)
        if payload is None:
            return checks
        data = payload.get("data")
    if not isinstance(data, dict) or data.get("id") != run_id or data.get("status") != "SUCCEEDED":
        settled["outcome"] = "ACTOR_NOT_SUCCEEDED"
        return checks
    store_id = data.get("defaultKeyValueStoreId")
    if not _safe_id(store_id):
        settled["outcome"] = "MALFORMED_RESPONSE"
        return checks
    settled.update(outcome="VERIFIED", result_count=1, run_id=run_id, run_status="SUCCEEDED")
    for field, name in (("buildId", "build_id"), ("defaultDatasetId", "default_dataset_id")):
        if _safe_id(data.get(field)):
            settled[name] = data[field]
    path = f"/v2/key-value-stores/{store_id}/records/OUTPUT"
    output = _receipt("Apify", APIFY, path, "hello_world_output")
    payload = _request(APIFY, path, key, output)
    if payload is not None:
        if payload == {"message": "Hello world!"}:
            output.update(outcome="VERIFIED", result_count=1, run_id=run_id)
        else:
            output["outcome"] = "UNEXPECTED_DEMO_OUTPUT"
    return checks + [output]


def _credits_available(used: object, limit: object) -> bool:
    return type(used) is int and type(limit) is int and 0 <= used < limit


def _tavily_checks(key: str, search: bool) -> list[dict]:
    auth = _receipt("Tavily", TAVILY, "/usage", "authentication_and_quota")
    payload = _request(TAVILY, "/usage", key, auth)
    free_capacity = False
    if payload is not None:
        account, api_key = payload.get("account"), payload.get("key")
        if isinstance(account, dict) and isinstance(api_key, dict):
            plan = account.get("current_plan")
            free = isinstance(plan, str) and plan.strip().lower() in {"researcher", "free", "free researcher"}
            included = _credits_available(account.get("plan_usage"), account.get("plan_limit"))
            paygo = all(name in account and (account[name] is None or
                         (type(account[name]) is int and account[name] == 0))
                        for name in ("paygo_usage", "paygo_limit"))
            key_limit = "limit" in api_key and (
                api_key["limit"] is None or _credits_available(api_key.get("usage"), api_key["limit"])
            )
            free_capacity = free and included and paygo and key_limit
            auth.update(outcome="VERIFIED", result_count=1, free_plan=free,
                        included_credit_available=included, no_paygo_quota_reported=paygo,
                        key_capacity_available=key_limit)
        else:
            auth["outcome"] = "MALFORMED_RESPONSE"
    if not search or not key:
        return [auth]

    receipt = _receipt("Tavily", TAVILY, "/search", "aapl_news", method="POST")
    if not free_capacity:
        receipt["outcome"] = "FREE_USAGE_NOT_VERIFIED"
        return [auth, receipt]
    try:
        capture = validate_news_context(fetch_news_context("AAPL", receipt=receipt), "AAPL")
    except CWTQuantError:
        status = receipt["http_status"]
        receipt["outcome"] = "HTTP_ERROR" if status is not None and status != 200 else "REQUEST_FAILED"
    else:
        receipt.update(outcome="VERIFIED", result_count=capture["response_result_count"],
                       usable_article_count=len(capture["articles"]), request_id=capture["request_id"],
                       historical_features_eligible=False, search_depth="basic")
    return [auth, receipt]


def _apify_dataset(key: str, dataset_id: str, rights: str, max_items: int, demo: bool) -> list[dict]:
    from .x_export import download_authorized_apify_dataset, load_x_export

    path = f"/v2/datasets/{dataset_id}/items"
    phase = "authorized_demo_dataset_read" if demo else "authorized_x_dataset_ingestion"
    receipt = _receipt("Apify", APIFY, path, phase)
    receipt["dataset_id"] = dataset_id
    if not key:
        receipt["outcome"] = "MISSING_CREDENTIAL"
        return [receipt]
    try:
        with TemporaryDirectory(prefix="cwt-apify-check-") as temporary:
            export = Path(temporary) / "export.json"
            meta = download_authorized_apify_dataset(
                dataset_id, export, ticker="AAPL", rights_basis=rights,
                max_items=max_items, receipt=receipt,
            )
            if not demo:
                manifest = Path(temporary) / "manifest.json"
                manifest.write_text(json.dumps(meta), encoding="utf-8")
                posts, _ = load_x_export(export, manifest, "AAPL")
                receipt["ticker_matched_count"] = len(posts)
    except (CWTQuantError, OSError, ValueError, http.client.HTTPException):
        status = receipt["http_status"]
        receipt["outcome"] = "HTTP_ERROR" if status is not None and status != 200 else "INGESTION_FAILED"
    else:
        receipt.update(outcome="VERIFIED", result_count=meta["row_count"],
                       page_count=meta["dataset_pages"], export_sha256=meta["export_sha256"],
                       historical_features_eligible=False)
    return [receipt]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=(
        "apify-auth", "apify-demo", "apify-dataset", "tavily-auth", "tavily-search",
    ))
    parser.add_argument("--out", type=Path, required=True, help="New JSON receipt path")
    parser.add_argument("--inventory", action="store_true", help="List Apify run/dataset totals after authentication")
    parser.add_argument("--dataset-id", help="Existing authorized Apify dataset")
    parser.add_argument("--demo-records", action="store_true", help="Verify non-X JSON demo records")
    parser.add_argument("--rights-basis", help="Documented rights for the supplied dataset")
    parser.add_argument("--confirm-included-storage", action="store_true",
                        help="Confirm this read fits the account's included storage allowance")
    parser.add_argument("--max-items", type=int, default=50, help="Maximum authorized dataset size")
    args = parser.parse_args(argv)

    apify_key = os.environ.get("APIFY_TOKEN", "").strip()
    tavily_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if args.inventory and args.operation != "apify-auth":
        parser.error("--inventory requires apify-auth")
    if args.demo_records and args.operation != "apify-dataset":
        parser.error("--demo-records requires apify-dataset")
    if args.operation == "apify-dataset":
        if (not _safe_id(args.dataset_id)
                or not args.rights_basis or not args.rights_basis.strip()
                or any(key and key in args.rights_basis for key in (apify_key, tavily_key))
                or not args.confirm_included_storage or not 1 <= args.max_items <= 1000):
            parser.error("Dataset check requires a valid ID, documented rights, included storage and max-items 1–1000")

    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as output:
            if args.operation == "apify-dataset":
                checks = _apify_dataset(
                    apify_key, args.dataset_id, args.rights_basis, args.max_items, args.demo_records,
                )
            elif args.operation == "apify-auth":
                checks = _apify_checks(apify_key, args.inventory)
            elif args.operation == "apify-demo":
                checks = _apify_demo(apify_key)
            else:
                checks = _tavily_checks(tavily_key, args.operation == "tavily-search")
            actor_started = False
            for check in checks:
                if check["phase"] == "hello_world_actor" and check["executed_at_utc"]:
                    status = check["http_status"]
                    actor_started = None if status is None or status >= 500 else status == 201
            output.write(json.dumps({
                "checks": checks, "actor_started": actor_started, "historical_x_status": "WITHHELD",
            }, indent=2) + "\n")
    except OSError:
        print("Could not write a new API receipt.")
        return 1
    for check in checks:
        print(f"{check['provider']} {check['phase']} {check['outcome']} (HTTP {check['http_status']})")
    return int(any(check["outcome"] != "VERIFIED" for check in checks))


if __name__ == "__main__":
    raise SystemExit(main())

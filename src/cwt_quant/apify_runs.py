"""Plan a 180-day X search and import an already-authorized completed Apify run."""

from __future__ import annotations

import argparse
import http.client
import json
import re
import tempfile
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .exceptions import DataError, ProvenanceError
from .x_export import (
    ACTOR_NAME,
    _SYMBOL,
    _authorization,
    _download_response,
    _evaluation_cutoff,
    _json,
    _publish_new,
    _query_keyword,
    _query_terms,
    _timestamp,
    coverage_audit,
    download_authorized_apify_dataset,
    load_x_export,
)


def query_plan(ticker: str, end: date, *, max_items: int = 2000, keyword: str | None = None) -> dict:
    ticker = ticker.strip().upper()
    if not _SYMBOL.fullmatch(ticker):
        raise DataError("A valid single ticker is required for the actor query plan")
    if type(max_items) is not int or not 50 <= max_items <= 10_000:
        raise DataError("Actor max_items must be an integer from 50 to 10000")
    now = datetime.now(timezone.utc)
    if end >= now.date() or _evaluation_cutoff(end) > now:
        raise DataError("The final New York query date must have ended")
    end_exclusive = end + timedelta(days=2)
    try:
        start = end - timedelta(days=179)
    except OverflowError:
        raise DataError("Actor query start falls outside supported dates") from None
    keyword = _query_keyword(keyword, DataError)
    return {
        "actor": ACTOR_NAME,
        "window": {"start_date": start.isoformat(), "end_date": end.isoformat(), "timezone": "America/New_York"},
        "query_timezone": "UTC", "query_end_utc_exclusive": end_exclusive.isoformat(),
        "keyword": keyword,
        "actor_input": {
            "searchTerms": _query_terms(ticker, start, keyword), "sort": "Latest", "maxItems": max_items,
        },
    }


def _apify_id(value: object, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ProvenanceError(f"A valid Apify {label} is required")
    return value


def _object(connection, path: str, headers: dict, *, wrapped: bool = False) -> dict:
    try:
        _, raw = _download_response(connection, path, headers)
        value = _json(raw.decode("utf-8"))
        if wrapped and isinstance(value, dict):
            value = value.get("data")
    except (ValueError, OSError, RecursionError, http.client.HTTPException):
        raise DataError("Unable to read Apify run metadata or input") from None
    if not isinstance(value, dict):
        raise DataError("Apify returned malformed actor metadata or input")
    return value


def import_authorized_run(
    run_id: str, path: Path, manifest_path: Path, *, ticker: str, end: date,
    rights_basis: str, max_items: int = 10_000, keyword: str | None = None,
) -> dict:
    """Read and bind a successful actor run, canonical query input, and dataset, then validate the export."""
    run_id = _apify_id(run_id, "run ID")
    ticker = ticker.strip().upper()
    plan = query_plan(ticker, end, keyword=keyword)
    if (
        not isinstance(rights_basis, str) or not rights_basis.strip()
        or rights_basis.strip().upper().startswith(("REPLACE_", "TODO", "UNKNOWN"))
    ):
        raise ProvenanceError("Import requires the documented research rights for this run")
    if (
        path.suffix.lower() != ".json" or manifest_path.suffix.lower() != ".json"
        or path.resolve() == manifest_path.resolve() or path.exists() or manifest_path.exists()
        or not path.parent.is_dir() or not manifest_path.parent.is_dir()
    ):
        raise DataError("Import requires two new local JSON paths in existing directories")
    if type(max_items) is not int or not 1 <= max_items <= 10_000:
        raise DataError("Import max_items must be an integer from 1 to 10000")

    headers = _authorization()
    with closing(http.client.HTTPSConnection("api.apify.com", timeout=30)) as connection:
        actor = _object(connection, f"/v2/actors/{ACTOR_NAME.replace('/', '~')}", headers, wrapped=True)
        if (actor.get("username"), actor.get("name")) != tuple(ACTOR_NAME.split("/")):
            raise ProvenanceError("Apify returned an unexpected actor identity")
        actor_id = _apify_id(actor.get("id"), "actor ID")
        run = _object(connection, f"/v2/actor-runs/{run_id}", headers, wrapped=True)
        if run.get("id") != run_id or run.get("actId") != actor_id or run.get("status") != "SUCCEEDED":
            raise ProvenanceError("The supplied Apify run did not complete under the planned actor")
        dataset_id = _apify_id(run.get("defaultDatasetId"), "dataset ID")
        store_id = _apify_id(run.get("defaultKeyValueStoreId"), "input store ID")
        build_id = _apify_id(run.get("buildId"), "build ID")
        started = _timestamp(run.get("startedAt"), "actor started_at", ProvenanceError)
        finished = _timestamp(run.get("finishedAt"), "actor finished_at", ProvenanceError)
        if not _evaluation_cutoff(end) <= started <= finished <= datetime.now(timezone.utc):
            raise ProvenanceError("The Apify run must have collected after the New York search window ended")
        actor_input = _object(connection, f"/v2/key-value-stores/{store_id}/records/INPUT", headers)

    planned = plan["actor_input"]
    cap = actor_input.get("maxItems")
    if (
        type(cap) is not int or not 50 <= cap <= max_items
        or actor_input.get("searchTerms") != planned["searchTerms"] or actor_input.get("sort") != planned["sort"]
        or any(value not in (None, False, "", [], {}) for key, value in actor_input.items() if key not in planned)
    ):
        raise ProvenanceError("Apify actor input does not match the approved query plan or local item limit")

    # Validate before publication. Neither destination is overwritten. If the second
    # publication fails, remove the newly linked export from this import.
    with tempfile.TemporaryDirectory(dir=path.parent) as temporary:
        export = Path(temporary) / "dataset.json"
        manifest = download_authorized_apify_dataset(
            dataset_id, export, ticker=ticker, rights_basis=rights_basis, max_items=cap,
        )
        manifest["actor_run"] = {
            "actor_name": ACTOR_NAME, "actor_id": actor_id, "run_id": run_id, "build_id": build_id,
            "dataset_id": dataset_id, "started_at_utc": started.isoformat(), "finished_at_utc": finished.isoformat(),
            "query_start_date": plan["window"]["start_date"], "query_end_date": end.isoformat(),
            "search_terms": planned["searchTerms"], "sort": planned["sort"], "max_items": cap,
            "keyword": plan["keyword"],
        }
        provenance = Path(temporary) / "manifest.json"
        payload = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
        provenance.write_bytes(payload)
        posts, source = load_x_export(export, provenance, ticker)
        audit = coverage_audit(posts, end - timedelta(days=179), end, source)
        _publish_new(path, export.read_bytes())
        try:
            _publish_new(manifest_path, payload)
        except DataError:
            path.unlink()
            raise
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    for name in ("plan", "import"):
        action = actions.add_parser(name)
        action.add_argument("--ticker", required=True)
        action.add_argument("--end", type=date.fromisoformat, required=True)
        action.add_argument("--max-items", type=int, default=2000 if name == "plan" else 10_000)
        action.add_argument("--keyword", help="Optional company name or search phrase")
    action.add_argument("--run-id", required=True)
    action.add_argument("--rights-basis", required=True)
    action.add_argument("--out", type=Path, required=True)
    action.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "plan":
            result = query_plan(args.ticker, args.end, max_items=args.max_items, keyword=args.keyword)
        else:
            result = import_authorized_run(
                args.run_id, args.out, args.manifest, ticker=args.ticker,
                end=args.end, rights_basis=args.rights_basis, max_items=args.max_items, keyword=args.keyword,
            )
    except (DataError, ProvenanceError) as exc:
        parser.exit(1, f"{exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

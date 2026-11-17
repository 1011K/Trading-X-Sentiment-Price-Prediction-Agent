"""Import local, permissioned X exports with explicit availability evidence."""

from __future__ import annotations

import csv
import hashlib
import http.client
import io
import json
import os
import re
import tempfile
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

from .calendar import ET
from .exceptions import DataError, ProvenanceError

_SOURCE = "apify_x_export"
_ARCHIVE_SOURCE = "authorized_x_archive"
ACTOR_NAME = "apidojo/tweet-scraper"
_MAX_API_RESPONSE_BYTES = 32 * 1024 * 1024
_MAX_EXPORT_RESPONSE_BYTES = 128 * 1024 * 1024
_COUNTS = {
    "followers": (
        "author.followers", "author.followersCount", "user.followers_count", "authorFollowers", "followers"
    ),
    "likes": ("likeCount", "favoriteCount", "likes", "favorite_count"),
    "reposts": ("retweetCount", "repostCount", "reposts", "retweet_count"),
    "comments": ("replyCount", "comments", "reply_count"),
    "views": ("viewCount", "views", "view_count"),
}
_COLUMNS = [
    "post_id", "author", "text", "has_cashtag", "relevance_basis", "source", "created_at", "observed_at",
    "acquired_at", "engagement_asof", "followers_asof", *_COUNTS,
]
_SYMBOL = re.compile(r"[A-Z][A-Z0-9]*(?:[.-][A-Z0-9]+)*", re.ASCII)
_ISO_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,9})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])",
    re.ASCII,
)
_X_TIMESTAMP = re.compile(
    r"[A-Z][a-z]{2} [A-Z][a-z]{2} {1,2}[0-9]{1,2} [0-9]{2}:[0-9]{2}:[0-9]{2} "
    r"[+-][0-9]{4} [0-9]{4}",
    re.ASCII,
)


def _timestamp(value: object, label: str, error: type[Exception], *, native_x: bool = False):
    try:
        if isinstance(value, str) and _ISO_TIMESTAMP.fullmatch(value):
            return pd.Timestamp(value).tz_convert("UTC").as_unit("ns")
        if native_x and isinstance(value, str) and _X_TIMESTAMP.fullmatch(value):
            parsed = datetime.strptime(value, "%a %b %d %H:%M:%S %z %Y")
            if parsed.strftime("%a") == value[:3]:
                return pd.Timestamp(parsed).tz_convert("UTC").as_unit("ns")
    except (ValueError, OverflowError):
        pass
    raise error(f"{label} requires a valid, timezone-aware timestamp")


def _read(path: Path, error: type[Exception]) -> tuple[str, str]:
    try:
        raw = path.read_bytes()
        return raw.decode("utf-8-sig"), hashlib.sha256(raw).hexdigest()
    except (OSError, UnicodeError):
        raise error("Could not read a UTF-8 X export or manifest") from None


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("Non-finite JSON number")


def _json(payload: str):
    return json.loads(payload, object_pairs_hook=_unique_keys, parse_constant=_reject_constant)


def _items(payload: str, suffix: str) -> list[dict]:
    try:
        if suffix == ".json":
            rows = _json(payload)
            if isinstance(rows, dict):
                rows = rows.get("items")
        elif suffix == ".jsonl":
            rows = [_json(line) for line in payload.split("\n") if line.strip()]
        elif suffix == ".csv":
            reader = csv.DictReader(io.StringIO(payload, newline=""), strict=True)
            names = reader.fieldnames
            if not names or len(names) != len(set(names)) or any(not name.strip() for name in names):
                raise ValueError("Missing or repeated CSV headers")
            rows = list(reader)
            if any(None in row or None in row.values() for row in rows):
                raise ValueError("Inconsistent CSV row width")
        else:
            raise DataError("X export must have a .json, .jsonl, or .csv extension")
    except (ValueError, csv.Error, RecursionError):
        raise DataError("Malformed X export") from None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise DataError("X export must contain a list of post records")
    return rows


def _manifest(payload: str, ticker: str, digest: str) -> tuple[dict, pd.Timestamp]:
    try:
        manifest = _json(payload)
    except (ValueError, RecursionError):
        raise ProvenanceError("Malformed X export manifest") from None
    if not isinstance(manifest, dict):
        raise ProvenanceError("X export manifest must be a JSON object")
    required = {
        "platform": "X",
        "intended_asset": ticker,
        "intended_purpose": "research",
        "export_sha256": digest,
    }
    for key, expected in required.items():
        if manifest.get(key) != expected:
            raise ProvenanceError(f"X export manifest has missing or invalid {key}")
    method = manifest.get("acquisition_method")
    if method == "authorized_local_export" and manifest.get("source_name") == "Apify":
        pass
    elif method == "authorized_archive_export":
        name = manifest.get("source_name")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9 ._-]{1,100}", name):
            raise ProvenanceError("Archive manifest requires a publisher name")
        try:
            reference = urlsplit(manifest.get("source_url") or "")
        except (AttributeError, ValueError):
            raise ProvenanceError("Archive manifest requires a public source URL") from None
        if (reference.scheme != "https" or not reference.hostname or reference.username
                or reference.password or reference.query or reference.fragment):
            raise ProvenanceError("Archive manifest requires a public source URL")
        if "actor_run" in manifest or manifest.get("historical_text_point_in_time_verified") is not False:
            raise ProvenanceError("A retrospective archive cannot attest historical observation or an Apify run")
    else:
        raise ProvenanceError("X export manifest has unsupported source provenance")
    if manifest.get("access_authorized") is not True:
        raise ProvenanceError("X export manifest must attest access_authorized as true")
    for key in ("rights_basis", "dataset_id"):
        value = manifest.get(key)
        if (
            not isinstance(value, str)
            or not value.strip()
            or value.strip().upper().startswith(("REPLACE_", "TODO", "UNKNOWN"))
        ):
            raise ProvenanceError(f"X export manifest requires a documented {key}")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", manifest["dataset_id"], re.ASCII):
        raise ProvenanceError("X export manifest requires a stable dataset ID")
    if type(manifest.get("historical_text_point_in_time_verified")) is not bool:
        raise ProvenanceError("X export manifest requires a boolean historical text attestation")
    if type(manifest.get("row_count")) is not int or manifest["row_count"] < 0:
        raise ProvenanceError("X export manifest requires a nonnegative integer raw row_count")
    acquired = _timestamp(manifest.get("retrieved_at_utc"), "retrieved_at_utc", ProvenanceError)
    if acquired > pd.Timestamp.now(tz="UTC"):
        raise ProvenanceError("X export retrieval time is in the future")
    return manifest, acquired


def _values(row: dict, *aliases: str):
    for alias in aliases:
        if alias in row and row[alias] not in (None, ""):
            yield row[alias]
            continue
        value = row
        for part in alias.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if value not in (None, ""):
            yield value


def _field(row: dict, *aliases: str):
    return next(_values(row, *aliases), None)


def _identity(value: object, field: str) -> str:
    if type(value) is int and value > 0:
        return str(value)
    if isinstance(value, str) and value and value == value.strip() and not any(c.isspace() for c in value):
        return value
    raise DataError(f"X export row requires a valid {field}")


def _count(value: object, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,20}", value):
        value = int(value)
    if type(value) is not int or not 0 <= value < 2**64:
        raise DataError(f"X export {field} requires a nonnegative integer")
    return value


def _relevance(text: str, ticker: str, cashtag: re.Pattern) -> str | None:
    text = re.sub(r"https?://\S+", "", text, flags=re.IGNORECASE)
    if cashtag.search(text):
        return "cashtag"
    if ticker != "AAPL":
        return None
    if re.search(r"\bApple\s+(?:Inc\b|earnings\b|shares\b|dividend\b|buyback\b|guidance\b|stock\b)",
                 text, re.IGNORECASE):
        return "issuer_keyword"
    symbol = r"(?<![\w$])AAPL(?![\w$]|[.-]\w)"
    financial = r"\b(?:shares|stock|earnings|dividend|buyback|guidance|revenue|EPS|investors|price\s+target)\b"
    for sentence in re.split(r"[!?\n]|\.\s", text):
        if re.search(symbol, sentence) and re.search(financial, sentence, re.IGNORECASE):
            return "ticker_context"
    return None


def load_x_export(path: Path, manifest_path: Path, ticker: str) -> tuple[pd.DataFrame, dict]:
    """Return symbol-relevant posts and source metadata for a permissioned local export."""
    ticker = ticker.upper()
    if not _SYMBOL.fullmatch(ticker):
        raise DataError("X export requires a valid ticker")
    payload, export_hash = _read(path, DataError)
    manifest_payload, manifest_hash = _read(manifest_path, ProvenanceError)
    manifest, acquired = _manifest(manifest_payload, ticker, export_hash)
    items = _items(payload, path.suffix.lower())
    if manifest["row_count"] != len(items):
        raise ProvenanceError("X export does not match the manifest row_count")

    attested = manifest["historical_text_point_in_time_verified"]
    provenance = _ARCHIVE_SOURCE if manifest["acquisition_method"] == "authorized_archive_export" else _SOURCE
    run = _actor_run_provenance(manifest, acquired) if "actor_run" in manifest else None
    if run and attested:
        raise ProvenanceError("Apify actor output is retrospective and cannot attest historical observation")
    run_finished = pd.Timestamp(run["finished_at_utc"]) if run else None
    cashtag = re.compile(rf"(?<![\w$])\${re.escape(ticker)}(?![\w$]|[.-][\w])", re.IGNORECASE)
    seen: dict[str, dict] = {}
    posts: list[dict] = []
    for row in items:
        ids = {
            _identity(value, "post ID")
            for value in _values(row, "id", "tweetId", "tweet_id", "post_id", "id_str")
        }
        if not ids:
            raise DataError("X export row requires a valid post ID")
        if len(ids) != 1:
            raise DataError("X export row has conflicting post ID aliases")
        post_id = ids.pop()
        author = _identity(_field(
            row, "author.id", "author.id_str", "user.id", "authorId", "author_id",
            "author.userName", "user.screen_name", "author", "account_id",
        ), "author ID or handle")
        body = _field(row, "fullText", "text", "full_text", "content")
        if not isinstance(body, str) or not body.strip():
            raise DataError("X export row requires post text")
        created = _timestamp(
            _field(row, "createdAt", "created_at", "timestamp_utc", "date", "timestamp"),
            "created_at", DataError, native_x=True,
        )
        if created > acquired:
            raise DataError("X export post was created after retrieval")
        if run_finished is not None and created > run_finished:
            raise DataError("X export post was created after the actor run finished")
        counts = {name: _count(_field(row, *aliases), name) for name, aliases in _COUNTS.items()}
        relevance = _relevance(body, ticker, cashtag)
        observed = pd.NaT
        if relevance and attested:
            observed = _timestamp(
                _field(row, "observed_at", "observed_at_utc"), "observed_at", ProvenanceError,
            )
            if not created <= observed <= acquired:
                raise ProvenanceError("X export observed_at must fall between creation and retrieval")
        if post_id in seen:
            if row != seen[post_id]:
                raise DataError("Conflicting records share an X post ID")
            continue
        seen[post_id] = row
        if relevance:
            posts.append({
                "post_id": post_id, "author": author, "text": body,
                "has_cashtag": relevance == "cashtag", "relevance_basis": relevance,
                "source": provenance, "created_at": created, "observed_at": observed,
                "acquired_at": acquired, "engagement_asof": pd.NaT,
                "followers_asof": pd.NaT, **counts,
            })
    frame = pd.DataFrame(posts, columns=_COLUMNS)
    for col in ("created_at", "observed_at", "acquired_at", "engagement_asof", "followers_asof"):
        frame[col] = pd.to_datetime(frame[col], utc=True)
    for col in _COUNTS:
        frame[col] = pd.array([row[col] for row in posts], dtype="UInt64")
    frame = frame.sort_values(["created_at", "post_id"]).reset_index(drop=True)
    meta = {
        "provenance": provenance,
        "source_hash": export_hash,
        "export_sha256": export_hash,
        "manifest_sha256": manifest_hash,
        "dataset_id": manifest["dataset_id"],
        "retrieved_at_utc": acquired.isoformat(),
        "ticker": ticker,
        "raw_rows": len(items),
        "deduplicated_rows": len(seen),
        "matched_rows": len(frame),
        "relevance_counts": {str(key): int(n) for key, n in frame["relevance_basis"].value_counts().items()},
        "historical_eligible": attested and not frame.empty,
        "historical_engagement_verified": False,
        "coverage_independently_verified": False,
    }
    if provenance == _ARCHIVE_SOURCE:
        meta["source_name"] = manifest["source_name"]
        meta["source_url"] = manifest["source_url"]
    if run:
        meta["actor_run"] = run
    pages = manifest.get("dataset_pages")
    if pages is not None:
        if type(pages) is not int or not 1 <= pages <= max(1, len(items)):
            raise ProvenanceError("X export has invalid dataset page count")
        meta["dataset_pages"] = pages
    frame.attrs.update(meta)
    return frame, meta


def _actor_run_provenance(manifest: dict, acquired: pd.Timestamp) -> dict:
    run = manifest["actor_run"]
    if not isinstance(run, dict) or run.get("actor_name") != ACTOR_NAME:
        raise ProvenanceError("X export has unsupported actor run provenance")
    keys = ("actor_id", "run_id", "build_id", "dataset_id")
    if any(not isinstance(run.get(key), str) or not re.fullmatch(r"[A-Za-z0-9_-]+", run[key])
           for key in keys):
        raise ProvenanceError("X export has invalid actor run identifiers")
    if run["dataset_id"] != manifest["dataset_id"]:
        raise ProvenanceError("Actor run dataset does not match the X export")
    started = _timestamp(run.get("started_at_utc"), "actor started_at", ProvenanceError)
    finished = _timestamp(run.get("finished_at_utc"), "actor finished_at", ProvenanceError)
    if not started <= finished <= acquired:
        raise ProvenanceError("X export has inconsistent actor run timing")
    date_keys = ("query_start_date", "query_end_date")
    try:
        start, end = (date.fromisoformat(run.get(key)) for key in date_keys)
    except (ValueError, TypeError):
        raise ProvenanceError("X export has invalid actor query dates") from None
    if [start.isoformat(), end.isoformat()] != [run[key] for key in date_keys]:
        raise ProvenanceError("X export actor query dates must use YYYY-MM-DD")
    if end >= started.date() or started < _evaluation_cutoff(end):
        raise ProvenanceError("The Apify actor run must begin after the search window ended")
    end_exclusive = (end + timedelta(days=2)).isoformat()
    if (end - start).days != 179:
        raise ProvenanceError("X export actor query plan does not match the declared 180-day window")
    terms = run.get("search_terms")
    keyword = _query_keyword(run.get("keyword"), ProvenanceError)
    planned = _query_terms(manifest["intended_asset"], start, keyword)
    if terms != planned or run.get("sort") != "Latest":
        raise ProvenanceError("X export actor query plan does not match the declared 180-day window")
    if type(run.get("max_items")) is not int or run["max_items"] < 50:
        raise ProvenanceError("X export has invalid actor item limit")
    return {
        "actor_name": ACTOR_NAME, **{key: run[key] for key in (*keys, *date_keys)},
        "started_at_utc": started.isoformat(), "finished_at_utc": finished.isoformat(),
        "search_terms": planned, "query_timezone": "UTC", "query_end_utc_exclusive": end_exclusive,
        "sort": "Latest", "keyword": keyword,
        "max_items": run["max_items"], "item_cap_reached": manifest["row_count"] >= run["max_items"],
        "api_readback_claim_is_manifest_declared": True,
    }


def _evaluation_cutoff(end: date) -> datetime:
    return datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=ET)


def _query_keyword(keyword: object, error: type[Exception]) -> str | None:
    if keyword is None:
        return None
    if not isinstance(keyword, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .,&'-]{0,59}", keyword):
        raise error("Actor keyword must be a plain company name or search phrase")
    return keyword.strip()


def _query_terms(ticker: str, start: date, keyword: str | None = None) -> list[str]:
    alternatives = [f"${ticker}", ticker]
    if keyword is not None:
        alternatives.append(f'"{keyword}"')
    subject = " OR ".join(alternatives)
    bounds = [start + timedelta(days=45 * index) for index in range(5)]
    # The last New York day extends into the next UTC day.
    bounds[-1] += timedelta(days=1)
    return [
        f"({subject}) since:{left} until:{right} -filter:retweets"
        for left, right in zip(bounds, bounds[1:])
    ]


def coverage_audit(posts: pd.DataFrame, start: date, end: date, source: dict | None = None) -> dict:
    """Count matching posts across UTC and New York dates without asserting corpus completeness."""
    if end < start:
        raise DataError("X coverage dates must be in chronological order")
    source = source or {}
    run = source.get("actor_run") or {}
    if posts.empty:
        ny_days = utc_days = timestamped_days = pd.Series(dtype="int64")
    else:
        created = posts["created_at"]
        ny = created.dt.tz_convert(ET).dt.date
        ny_days = ny.value_counts()
        utc_days = created.dt.tz_convert("UTC").dt.date.value_counts()
        timestamped_days = ny[posts["observed_at"].notna()].value_counts()
    daily = [
        {
            "date": day.isoformat(),
            "posts": int(ny_days.get(day, 0)),
            "utc_posts": int(utc_days.get(day, 0)),
            "pit_timestamped_posts": int(timestamped_days.get(day, 0)),
        }
        for day in pd.date_range(start, end).date
    ]
    in_window = sum(row["posts"] for row in daily)
    in_window_utc = sum(row["utc_posts"] for row in daily)
    covered_days = sum(row["posts"] > 0 for row in daily)
    return {
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "calendar_days": len(daily), "primary_timezone": str(ET),
        "raw_rows": source.get("raw_rows", len(posts)),
        "deduplicated_rows": source.get("deduplicated_rows", len(posts)),
        "unmatched_rows": source.get("deduplicated_rows", len(posts)) - len(posts),
        "matched_posts": len(posts), "in_window_posts": in_window,
        "outside_window_posts": len(posts) - in_window,
        "utc_in_window_posts": in_window_utc,
        "utc_outside_window_posts": len(posts) - in_window_utc,
        "pit_timestamped_posts": sum(row["pit_timestamped_posts"] for row in daily),
        "days_with_posts": covered_days, "days_without_returned_posts": len(daily) - covered_days,
        "actor_query_window_matches": (
            run.get("query_start_date") == start.isoformat() and run.get("query_end_date") == end.isoformat()
        ),
        "actor_run": run or None, "coverage_independently_verified": False,
        "note": (
            "Counts use creation dates. A zero count means no matching row returned by the export. "
            "Search visibility, query caps, time-zone edges and retrieval timing can affect coverage. "
            "An observation timestamp still requires a separate forecast-cutoff check."
        ),
        "daily": daily,
    }


def _authorization() -> dict:
    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        raise ProvenanceError("Set APIFY_TOKEN locally before downloading an authorized dataset")
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _download_response(connection, path: str, headers: dict, *, receipt: dict | None = None):
    if receipt is not None and receipt["executed_at_utc"] is None:
        receipt["executed_at_utc"] = datetime.now(timezone.utc).isoformat()
    connection.request("GET", path, headers=headers)
    response = connection.getresponse()
    if receipt is not None:
        receipt["http_status"] = response.status
        receipt["response_sha256"] = None
    if response.status != 200:
        raise DataError(f"Apify request returned HTTP {response.status}")
    payload = response.read(_MAX_API_RESPONSE_BYTES + 1)
    if len(payload) > _MAX_API_RESPONSE_BYTES:
        raise DataError("Apify response exceeds the local byte limit")
    if receipt is not None:
        receipt["response_sha256"] = hashlib.sha256(payload).hexdigest()
    return response, payload


def _publish_new(path: Path, payload: bytes) -> None:
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent) as temporary:
            temporary.write(payload)
            temporary.flush()
            os.link(temporary.name, path)
    except OSError:
        raise DataError("Unable to write the new local Apify export or manifest") from None


def download_authorized_apify_dataset(
    dataset_id: str, path: Path, *, ticker: str, rights_basis: str, max_items: int = 10_000,
    receipt: dict | None = None,
) -> dict:
    """Read an existing permissioned dataset and return the local export manifest."""
    manifest = {
        "platform": "X",
        "source_name": "Apify",
        "acquisition_method": "authorized_local_export",
        "access_authorized": True,
        "intended_asset": ticker.upper(),
        "intended_purpose": "research",
        "rights_basis": rights_basis,
        "dataset_id": dataset_id,
        "historical_text_point_in_time_verified": False,
    }
    if (
        not isinstance(dataset_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]+", dataset_id)
        or dataset_id.upper().startswith(("REPLACE_", "TODO", "UNKNOWN"))
        or not isinstance(rights_basis, str)
        or not rights_basis.strip()
        or rights_basis.strip().upper().startswith(("REPLACE_", "TODO", "UNKNOWN"))
        or not _SYMBOL.fullmatch(manifest["intended_asset"])
    ):
        raise ProvenanceError("Download requires a dataset ID, ticker, and documented rights")
    if path.suffix.lower() != ".json" or path.exists() or not path.parent.is_dir():
        raise DataError("Download requires a new local .json path in an existing directory")
    if type(max_items) is not int or max_items < 1:
        raise DataError("Download requires a positive integer max_items")

    headers = _authorization()
    items: list[dict] = []
    total = None
    pages = 0
    total_bytes = 0
    try:
        with closing(http.client.HTTPSConnection("api.apify.com", timeout=30)) as connection:
            while total is None or len(items) < total:
                offset = len(items)
                limit = min(1000, max_items - offset)
                response, raw = _download_response(
                    connection, f"/v2/datasets/{dataset_id}/items?format=json&offset={offset}&limit={limit}&desc=false",
                    headers, receipt=receipt,
                )
                total_bytes += len(raw)
                if total_bytes > _MAX_EXPORT_RESPONSE_BYTES:
                    raise DataError("Apify dataset exceeds the local byte limit")
                batch = _items(raw.decode("utf-8"), ".json")
                page_total = int(response.getheader("X-Apify-Pagination-Total"))
                page_count = int(response.getheader("X-Apify-Pagination-Count"))
                page_offset = int(response.getheader("X-Apify-Pagination-Offset"))
                desc = response.getheader("X-Apify-Pagination-Desc")
                if (
                    page_total > max_items
                    or (total is not None and page_total != total)
                    or page_offset != offset
                    or page_count != len(batch)
                    or page_count > limit
                    or (desc is not None and desc.lower() not in {"0", "false"})
                    or page_total < offset + page_count
                    or (page_count == 0 and offset < page_total)
                ):
                    raise DataError("Apify dataset pagination inconsistent or exceeds max_items")
                total = page_total
                items.extend(batch)
                pages += 1
        payload = json.dumps(items, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (OSError, TypeError, ValueError, http.client.HTTPException):
        raise DataError("Unable to read the complete authorized Apify dataset") from None

    if any(key and key.encode() in payload for key in (
        os.environ.get("APIFY_TOKEN", "").strip(), os.environ.get("TAVILY_API_KEY", "").strip(),
    )):
        raise DataError("Apify dataset contains a configured credential")
    _publish_new(path, payload)
    return {
        **manifest,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": len(items),
        "dataset_pages": pages,
        "export_sha256": hashlib.sha256(payload).hexdigest(),
    }

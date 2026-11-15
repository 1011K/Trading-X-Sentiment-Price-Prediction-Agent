"""Import local, permissioned Apify X exports with explicit availability evidence."""

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
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .exceptions import DataError, ProvenanceError

_SOURCE = "apify_x_export"
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
    "post_id", "author", "text", "has_cashtag", "source", "created_at", "observed_at",
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
        "source_name": "Apify",
        "acquisition_method": "authorized_local_export",
        "intended_asset": ticker,
        "intended_purpose": "research",
        "export_sha256": digest,
    }
    for key, expected in required.items():
        if manifest.get(key) != expected:
            raise ProvenanceError(f"X export manifest has missing or invalid {key}")
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
        raise ProvenanceError("X export manifest requires an Apify dataset ID")
    if type(manifest.get("historical_text_point_in_time_verified")) is not bool:
        raise ProvenanceError("X export manifest requires a boolean historical text attestation")
    if type(manifest.get("row_count")) is not int:
        raise ProvenanceError("X export manifest requires an integer raw row_count")
    return manifest, _timestamp(manifest.get("retrieved_at_utc"), "retrieved_at_utc", ProvenanceError)


def _field(row: dict, *aliases: str):
    for alias in aliases:
        if alias in row and row[alias] not in (None, ""):
            return row[alias]
        value = row
        for part in alias.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if value not in (None, ""):
            return value
    return None


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


def load_x_export(path: Path, manifest_path: Path, ticker: str) -> tuple[pd.DataFrame, dict]:
    """Return explicit-cashtag posts and source metadata for a permissioned local export."""
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
    cashtag = re.compile(rf"(?<![\w$])\${re.escape(ticker)}(?![\w$]|[.-][\w])", re.IGNORECASE)
    seen: dict[str, dict] = {}
    posts: list[dict] = []
    for row in items:
        post_id = _identity(_field(row, "id", "tweetId", "tweet_id", "post_id", "id_str"), "post ID")
        author = _identity(_field(
            row, "author.id", "author.id_str", "user.id", "authorId", "author_id",
            "author.userName", "user.screen_name", "author",
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
        counts = {name: _count(_field(row, *aliases), name) for name, aliases in _COUNTS.items()}
        matched = bool(cashtag.search(body))
        observed = pd.NaT
        if matched and attested:
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
        if matched:
            posts.append({
                "post_id": post_id, "author": author, "text": body, "has_cashtag": True,
                "source": _SOURCE, "created_at": created, "observed_at": observed,
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
        "provenance": _SOURCE,
        "source_hash": export_hash,
        "export_sha256": export_hash,
        "manifest_sha256": manifest_hash,
        "dataset_id": manifest["dataset_id"],
        "retrieved_at_utc": acquired.isoformat(),
        "ticker": ticker,
        "raw_rows": len(items),
        "deduplicated_rows": len(seen),
        "matched_rows": len(frame),
        "historical_eligible": attested and not frame.empty,
        "historical_engagement_verified": False,
        "coverage_independently_verified": False,
    }
    frame.attrs.update(meta)
    return frame, meta


def download_authorized_apify_dataset(
    dataset_id: str, path: Path, *, ticker: str, rights_basis: str, max_items: int = 10_000,
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

    token = os.environ.get("APIFY_TOKEN", "").strip()
    if not token or not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        raise ProvenanceError("Set APIFY_TOKEN locally before downloading an authorized dataset")

    items: list[dict] = []
    total = None
    try:
        with closing(http.client.HTTPSConnection("api.apify.com", timeout=30)) as connection:
            while total is None or len(items) < total:
                offset = len(items)
                limit = min(1000, max_items - offset)
                connection.request(
                    "GET", f"/v2/datasets/{dataset_id}/items?format=json&offset={offset}&limit={limit}",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                )
                response = connection.getresponse()
                if response.status != 200:
                    raise DataError(f"Apify dataset request returned HTTP {response.status}")
                batch = _items(response.read().decode("utf-8"), ".json")
                page_total = int(response.getheader("X-Apify-Pagination-Total"))
                page_count = int(response.getheader("X-Apify-Pagination-Count"))
                page_offset = int(response.getheader("X-Apify-Pagination-Offset"))
                if (
                    page_total > max_items
                    or (total is not None and page_total != total)
                    or page_offset != offset
                    or page_count != len(batch)
                    or page_count > limit
                    or page_total < offset + page_count
                    or (page_count == 0 and offset < page_total)
                ):
                    raise DataError("Apify dataset pagination inconsistent or exceeds max_items")
                total = page_total
                items.extend(batch)
        payload = json.dumps(items, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (OSError, TypeError, ValueError, http.client.HTTPException):
        raise DataError("Unable to read the complete authorized Apify dataset") from None

    try:
        with tempfile.NamedTemporaryFile(dir=path.parent) as temporary:
            temporary.write(payload)
            temporary.flush()
            os.link(temporary.name, path)
    except OSError:
        raise DataError("Unable to write the new local Apify export") from None
    return {
        **manifest,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": len(items),
        "export_sha256": hashlib.sha256(payload).hexdigest(),
    }

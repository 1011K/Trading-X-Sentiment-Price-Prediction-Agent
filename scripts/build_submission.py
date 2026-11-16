#!/usr/bin/env python3
"""Build a local AAPL submission from one replay."""
from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

from cwt_quant.calendar import XNYSCalendar
from cwt_quant.exceptions import CWTQuantError, DataError
from cwt_quant.replay_prices import capture_prices
from cwt_quant.submission import evaluate
from render_aapl_submission import render

ROOT = Path(__file__).resolve().parents[1]
FROZEN_END = date(2026, 11, 13)
FROZEN_PRICE_HASH = "1b6c3babe4d176320a4b4f4c9e6203da045a243061d2d347cf2758636eaab1ff"
REPLAY_FILES = (
    "open-nowcast.csv", "post-close-forecasts.csv", "model_comparison.csv",
    "trade_ledger.csv", "research-figure.png", "outlook.md", "evaluation.md",
    "manifest.json", "x-coverage.json",
)


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("frozen", "fresh", "test-only"))
    parser.add_argument("--end", type=date.fromisoformat, default=FROZEN_END)
    parser.add_argument("--prices-dir", type=Path, help="Directory containing AAPL.json")
    parser.add_argument("--reuse-prices", action="store_true", help="Replay an existing fresh snapshot offline")
    parser.add_argument("--news-snapshot", type=Path, help="Optional saved Tavily capture")
    parser.add_argument("--x-export", type=Path, help="TEST ONLY X fixture")
    parser.add_argument("--x-manifest", type=Path, help="TEST ONLY X fixture attestation")
    parser.add_argument("--out", type=Path, required=True, help="New local delivery directory")
    args = parser.parse_args()
    if args.mode == "frozen" and args.end != FROZEN_END:
        parser.error("Frozen mode requires --end 2026-11-13")
    if args.reuse_prices and args.mode != "fresh":
        parser.error("--reuse-prices applies only to fresh mode")
    if bool(args.x_export) != bool(args.x_manifest) or (args.x_export and args.mode != "test-only"):
        parser.error("X fixture files must be supplied together in test-only mode")
    if args.mode == "test-only" and args.prices_dir is None:
        parser.error("test-only mode requires --prices-dir")

    try:
        if args.out.exists() or args.out.is_symlink():
            raise DataError("Output directory already exists. Choose a new --out directory.")
        commit = git("rev-parse", "HEAD")
        dirty = bool(git("status", "--porcelain", "--untracked-files=no"))
        if args.mode == "fresh":
            prices_dir = args.prices_dir or Path("private_data") / f"fresh-{args.end}"
        else:
            prices_dir = args.prices_dir or Path("private_data/prices")
        prices = prices_dir / "AAPL.json"
        day = args.end
        calendar = XNYSCalendar()
        for _ in range(5):
            day = calendar.next_trading_day(day)
        if args.mode == "fresh" and not args.reuse_prices:
            if prices.exists() or prices.is_symlink():
                raise DataError("Fresh snapshot already exists. Use --reuse-prices or choose a new --prices-dir.")
            capture_prices(prices, "AAPL", args.end)

        news, news_hash = None, None
        if args.news_snapshot is not None:
            try:
                capture = args.news_snapshot.read_bytes()
            except FileNotFoundError:
                news = {"note": "The requested Tavily capture was unavailable."}
            else:
                from cwt_quant.connectors.tavily import validate_news_context
                news = validate_news_context(json.loads(capture), "AAPL")
                news_hash = sha256(capture).hexdigest()

        args.out.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".aapl-build-", dir=args.out.parent) as scratch:
            replay = Path(scratch) / "replay"
            bundle = Path(scratch) / "bundle"
            result = evaluate(
                "AAPL", args.end, prices, replay, args.x_export, args.x_manifest, news,
                expected_price_hash=FROZEN_PRICE_HASH if args.mode == "frozen" else None,
                build_context={
                    "build_mode": args.mode, "source_commit": commit, "source_dirty": dirty,
                    "news_snapshot_sha256": news_hash, "reportlab_version": version("reportlab"),
                },
            )
            render(replay, bundle, commit)
            for name in REPLAY_FILES:
                shutil.copyfile(replay / name, bundle / name)
            checksums = [
                f"{sha256(file.read_bytes()).hexdigest()}  {file.name}"
                for file in sorted(bundle.iterdir())
            ]
            (bundle / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="utf-8")
            bundle.rename(args.out)
    except (CWTQuantError, ImportError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"AAPL submission failed: {exc}", file=sys.stderr)
        return 1

    label = "TEST ONLY | " if args.mode == "test-only" else ""
    print(f"{label}AAPL {args.mode}: {result['evaluation_sessions']} sessions, "
          f"X {result['historical_x_status']}, run {result['run_id']}")
    print(f"Bundle: {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

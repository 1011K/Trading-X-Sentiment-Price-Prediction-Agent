#!/usr/bin/env python3
"""
Multi-ticker real-data audit runner for CWT Quant.

Runs leakage-safe walk-forward + forward forecasts on a basket of liquid
US equities using free open-source data only:

  - Prices: yfinance (daily, auto-adjusted)
  - Sentiment proxies:
      * StockTwits public stream (keyless, recent)
      * CrowdWisdomTrading free daily score (context only, NOT historical feature)
      * Optional NewsAPI if NEWSAPI_KEY is set

Default basket (chosen for liquidity + relevance to the Tesla/SpaceX request):
  TSLA, AAPL, NVDA, MSFT, AMZN

Produces per-ticker output folders and a consolidated AUDIT_SUMMARY.md.
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Ensure package is importable
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from cwt_quant.config import Config
from cwt_quant.logging_utils import setup_logging, get_logger
from cwt_quant.pipeline import run_pipeline
from cwt_quant.exceptions import CWTQuantError

DEFAULT_TICKERS = ["TSLA", "AAPL", "NVDA", "MSFT", "AMZN"]


def run_one(ticker: str, out_root: Path, history_days: int = 180) -> dict:
    log = get_logger("audit")
    out_dir = out_root / ticker
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = Config(
        ticker=ticker,
        history_calendar_days=history_days,
        outputs_dir=out_dir,
        enable_influence=True,
        real_data_present=True,
        fail_on_missing_sessions=False,  # soft for real data
        min_train_sessions=40,
        log_level="INFO",
        seed=42,
    )
    cfg.validate()

    log.info("=" * 60)
    log.info("AUDIT RUN: %s  history=%d calendar days", ticker, history_days)
    log.info("=" * 60)

    try:
        result = run_pipeline(
            cfg,
            force_synthetic=False,
            out_dir=out_dir,
        )
        result["status"] = "ok"
        result["ticker"] = ticker
        return result
    except Exception as exc:
        log.error("FAILED %s: %s", ticker, exc)
        traceback.print_exc()
        return {
            "status": "failed",
            "ticker": ticker,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


def summarise(results: list, out_root: Path) -> Path:
    lines = []
    lines.append("# CWT Quant — Multi-Ticker Real-Data Audit")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"**Status:** EXPERIMENTAL / RESEARCH")
    lines.append("")
    lines.append("## Design locks (from original adversarial audit)")
    lines.append("")
    lines.append("| Item | Decision |")
    lines.append("|------|----------|")
    lines.append("| Bars | Daily only (XNYS) |")
    lines.append("| Target | log(C[t+h]/C[t]), h=1..5 |")
    lines.append("| Walk-forward | Expanding, label rule i+h ≤ t |")
    lines.append("| Models | No-change · Price Ridge · Price+Sentiment · (gated) Influence |")
    lines.append("| Sentiment sources | StockTwits recent + optional news; CWT daily score context only |")
    lines.append("| True historical X engagement | **NOT available free** — influence remains gated |")
    lines.append("")
    lines.append("## Basket results")
    lines.append("")

    ok = [r for r in results if r.get("status") == "ok"]
    failed = [r for r in results if r.get("status") != "ok"]

    lines.append(f"- Successful: **{len(ok)}** / {len(results)}")
    if failed:
        lines.append(f"- Failed: {', '.join(r['ticker'] for r in failed)}")
    lines.append("")

    for r in ok:
        ticker = r["ticker"]
        meta = r.get("meta", {})
        metrics = r.get("metrics", {})
        lines.append(f"### {ticker}")
        lines.append("")
        lines.append(f"- Sessions: {meta.get('n_sessions')}")
        lines.append(f"- Posts / sentiment rows: {meta.get('n_posts')}")
        lines.append(f"- Mode: {meta.get('mode')}")
        lines.append(f"- Influence enabled: {r.get('influence_enabled')}")
        lines.append(f"- Sentiment model enabled: {r.get('sentiment_enabled')}")
        lines.append(f"- Source note: {meta.get('source_note', 'n/a')}")
        lines.append("")
        if metrics:
            lines.append("Walk-forward metrics (research only — **no skill claimed**):")
            lines.append("")
            lines.append("```")
            lines.append(json.dumps(metrics, indent=2, default=str)[:2500])
            lines.append("```")
            lines.append("")
        if r.get("warnings"):
            lines.append(f"Warnings ({len(r['warnings'])}):")
            for w in r["warnings"][:5]:
                lines.append(f"- {w}")
            lines.append("")
        lines.append(f"Artifacts: `{ticker}/`")
        lines.append("")

    lines.append("## Honesty statement")
    lines.append("")
    lines.append(
        "This audit uses free, publicly available data only. "
        "True point-in-time historical engagement snapshots from X/Twitter "
        "are not available without a paid full-archive product. "
        "Therefore the influence-weighted model is either gated off or "
        "is withheld without evidence and must not be presented as validated alpha. "
        "Forward forecasts (n+1 … n+5) are produced for research and CV "
        "demonstration; they are **not** trading signals."
    )
    lines.append("")
    lines.append("## Recommended next steps for personal research bot")
    lines.append("")
    lines.append("1. Schedule daily after US close: `python -m cwt_quant.cli --ticker TSLA --real-data --out outputs/TSLA`")
    lines.append("2. Inspect `forward_forecasts.csv`")
    lines.append("3. Log every forecast with origin timestamp and model version")
    lines.append("4. Never size real capital from the diagnostic alone")
    lines.append("5. If budget allows later: paid X full-archive for true historical engagement")
    lines.append("")

    path = out_root / "AUDIT_SUMMARY.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main():
    setup_logging("INFO")
    log = get_logger("audit")

    tickers = DEFAULT_TICKERS
    out_root = Path("outputs_audit_180d")
    out_root.mkdir(parents=True, exist_ok=True)

    log.info("Starting multi-ticker real-data audit on: %s", tickers)
    results = []
    for t in tickers:
        res = run_one(t, out_root, history_days=180)
        results.append(res)

    summary = summarise(results, out_root)
    log.info("Audit complete. Summary → %s", summary)

    # Also write machine-readable summary
    (out_root / "audit_results.json").write_text(
        json.dumps([{"ticker": r.get("ticker"), "status": r.get("status"),
                     "error": r.get("error"),
                     "meta": r.get("meta") if r.get("status") == "ok" else None,
                     "sentiment_enabled": r.get("sentiment_enabled"),
                     "influence_enabled": r.get("influence_enabled")}
                    for r in results], indent=2, default=str), encoding="utf-8"
    )
    print(f"\n=== AUDIT FINISHED ===")
    print(f"Summary: {summary}")
    print(f"JSON:    {out_root / 'audit_results.json'}")
    return 1 if any(r.get("status") != "ok" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())

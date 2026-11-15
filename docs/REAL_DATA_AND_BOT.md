# Real Data, Forward Forecasts & Personal Bot Path

## Honest constraints (2026)

| Source | Practical status | Cost |
|--------|------------------|------|
| Daily prices (yfinance) | Adapter implemented; current live access not re-tested | Free research access subject to provider terms |
| News headlines (NewsAPI) | Optional connector; current live access not re-tested | Subject to provider plan / retention limits |
| StockTwits recent stream | Connector included, live endpoint/terms not verified; may fail | Not a historical X corpus |
| X / Twitter history | Not implemented here; provider terms and cost require independent verification | Varies |
| True historical engagement *snapshots* at past closes | Extremely hard | Usually unavailable |

Most open-source “Twitter stock sentiment” repos on GitHub either:
- use **live** recent tweets only, or
- ignore point-in-time engagement, or
- are abandoned after the free X API ended.

Our package is stricter: leakage-safe walk-forward + optional influence gate.

## What this package does today

1. **Synthetic** — full red-team validation (default).
2. **Real prices** — `yfinance` daily auto-adjusted bars.
3. **Real news → sentiment** — historical news fetched today is excluded from older decision windows; no fabricated replay coverage.
4. **Walk-forward backtest** — no-change / price-only; sentiment/influence models are withheld when history lacks verified timestamp coverage.
5. **Forward valuation** — fits models on all available labels and emits **n+1 … n+5** forecasts from the latest origin (`forward_forecasts.csv`).

## How to run real mode

```bash
export NEWSAPI_KEY=your_key   # optional but recommended
pip install -r requirements-real.txt
PYTHONPATH=src python -m cwt_quant.cli --ticker AAPL --real-data --out outputs_real
```

## Personal research bot (no auto-trading)

- Run daily after US close.
- Read `forward_forecasts.csv`.
- Treat signals as **research only**.
- Never size capital from the diagnostic alone.
- Log every forecast with origin timestamp and model version.

## CV / GitHub positioning

Strong points to highlight:
- Leakage-safe expanding walk-forward with explicit `i + h ≤ t` rule
- Point-in-time engagement validity checks
- Fail-fast / soft-audit on missing sessions
- Honest WITHHELD language when skill is unproven
- Pure-numpy Ridge (no heavy deps required for core)
- Forward multi-horizon forecast artifact

Avoid claiming:
- Proven alpha
- Live X historical snapshots without paid archive
- Commercial FinBERT rights

## Recommended next connectors (in order of cost/value)

1. Verify StockTwits access rights and live endpoint before considering ingestion
2. Reddit finance subreddits via PRAW
3. Finnhub or Polygon news
4. Optional paid X full-archive only if budget allows

## Reference repos studied

- shirosaidev/stocksight (classic Twitter + news + Elasticsearch)
- TonyMa1/walk-forward-backtester
- advlya/stock-sentiment-analysis-trading-strategy (VADER + buy-hold)
- breathworklabs/sentiment-scanner (Reddit + StockTwits + VADER/FinBERT)
- Multiple abandoned X-stream bots that broke after paid API

This package deliberately prioritises methodology honesty over marketing claims.

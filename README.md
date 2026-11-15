> **Release status (15 Nov 2026): EXPERIMENTAL.** Synthetic tests and a local smoke run verify execution and selected point-in-time invariants, **not** historical X coverage, forecasting alpha, or deployable trading performance. Original five-ticker backtest output was deliberately excluded. Remaining Grok submissions are pending a neutral code review.

# CWT Quant — Research-Grade Reference Implementation

**Status: EXPERIMENTAL / INDEPENDENT CANDIDATE**  
Prepared 15 November 2026. Assessment target ~17 November 2026.

This is a **unified, leakage-safe** daily equity + X-sentiment research pipeline.  
It is **not** a merger of the earlier Grok / DeepSeek / ChatGPT prototypes.  
Those contained conflicting assumptions (hourly Yahoo, BTC calendar, engagement leakage, same-close fills, celebrity intercepts). Merging them would multiply bugs.

## Design locks (from the adversarial audit)

| Item | Decision |
|------|----------|
| Bars | Daily only (XNYS). Yahoo intraday ≤60 days; 180-day hourly rejected. |
| Target | log(C[t+h]/C[t]), h=1..5. Explicit units. |
| Post mapping | First *strictly later* session close (exact close → next; early closes respected). |
| Sentiment | Transparent lexical baseline. Pre-scored columns only with provenance. |
| Influence | Experimental formula, **gated** by historical engagement coverage. Reach does **not** create positive score. |
| Models | No-change · Price Ridge · Price+Sentiment Ridge · (optional) Price+Influence Ridge. Fixed α=10. Scaler train-only. |
| Walk-forward | Expanding. Label rule: train origin *i* usable at test *t* for horizon *h* only if `i+h ≤ t`. |
| Trading diagnostic | Next-open long-or-cash only. Costs declared. Not a trading system. |
| Complexity | LightGBM / RL / FinBERT ensembles **deferred**. Sample size does not support them. |
| FinBERT | Weights CC BY-NC-SA-4.0. Do not assume commercial rights. |

## Added robustness (v0.1.1)

- Structured logging with configurable level
- Custom exceptions (`ConfigError`, `DataError`, `LeakageError`, ...)
- Input validation (prices, posts, panel) with fail-fast or soft audit
- Missing session detection + configurable hard/soft policy
- Author frequency cap per session (spam control)
- Post-id deduplication with logging
- Run manifest (`run_manifest.json`) for reproducibility
- CLI exit codes + richer flags (`--log-level`, `--allow-missing-sessions`, ...)
- Influence coverage gate messaging
- Honest report includes warnings and adjustment policy

## CI and source-integrity improvements

- StockTwits HTTP access is an **optional** live-data dependency; offline regression tests do not require `requests`.
- Raw StockTwits posts and news headlines are never altered to invent a cashtag. Current CWT aggregate scores cannot be backdated.
- Offline CI checks Python 3.10 and 3.12, dependency consistency, and a synthetic CLI smoke run.
- These checks protect reproducibility; **they are not an X-data backtest or proof of alpha**.

## Quick start (synthetic)

```bash
cd cwt_quant
pip install -r requirements.txt
PYTHONPATH=src python -m cwt_quant.cli --ticker AAPL --out outputs
pytest tests/ -q
```

Expected: research report under `outputs/` and all deterministic offline tests green. Synthetic engagement coverage is not evidence of real-world influence.

## What is deliberately withheld

- Genuine forecasting skill / alpha  
- Real 180-day X corpus & live connectors  
- Corporate-action-adjusted price audit on real data  
- Commercial FinBERT authorization  
- Any claim that celebrity reach is proven predictive weight  

## P0 remaining work (before any submission claim)

1. Lawful 180-calendar-day X corpus with `created_at`, `post_id`, availability timestamps, and engagement *snapshots* (not current totals).  
2. Verified adjusted / raw OHLC policy for one exchange-traded stock.  
3. Run the identical pipeline on real data; produce the same honest report.  
4. External score provenance if any non-lexical sentiment is used.  
5. Full red-team re-run on the real corpus.

## License note

This reference code is provided for research evaluation. Model weights from third parties (e.g. ProsusAI/finbert) retain their original licenses.


## Real data mode (prices + news)

```bash
pip install -r requirements-real.txt
export NEWSAPI_KEY=...          # optional
PYTHONPATH=src python -m cwt_quant.cli --ticker AAPL --real-data --out outputs_real
```

Produces:
- `panel.csv`, walk-forward predictions
- `forward_forecasts.csv` — **n+1 … n+5** close forecasts from the latest origin
- research report + run manifest

See `docs/REAL_DATA_AND_BOT.md` for X API cost reality, alternative free sources (StockTwits/Reddit), and personal-bot usage notes.

## Verified implementation boundaries (15 November 2026)

- A historical X archive with verified availability and engagement snapshots is **not included**.
- A news headline or StockTwits message retrieved after a past market close is **not backdated** into that close.
- `price_sentiment` is **not trained or reported** when eligible historical coverage is insufficient.
- Influence requires point-in-time engagement **and follower-count** snapshots; author popularity alone adds no bullish score.
- Calendar hard-coded for **2024–2026** only, with explicit failure outside those years. Refer to the [official NYSE holiday schedule](https://www.nyse.com/markets/hours-calendars) before extending dates.
- CWT current daily score is contextual only and excluded from historical training. Its API data must not be republished.
- Supported research workflow: local synthetic test → lawful input acquisition → validation → isolated empirical audit.
- No LICENSE is published yet. The repository owner should approve a license before accepting external contributions or reuse.

### Optional live connectors

```bash
pip install -r requirements-real.txt
PYTHONPATH=src python -m cwt_quant.cli --ticker AAPL --real-data --out outputs_real
```

A live connection succeeding does **not** establish 180-day X coverage or statistical significance.

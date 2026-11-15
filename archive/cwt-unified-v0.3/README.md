# entiment-price-prediction

**CrowdWisdomTrading X Sentiment Price Prediction Agent**

**Implementation:** v0.3, research-only. Python-based X sentiment and walk-forward n+0 to n+5 asset-price forecasting.

**Research-only, paper-trading only. No synthetic market demo. No invented historical X posts.** The software does not include real X data, API credentials or actual forecast returns; those need a legitimate external source and a local live-data run. No trading orders are placed.

## Exactly what is delivered
- AAPL / NYSE real-price daily CSV downloader (`yfinance` optional, external connection needed).
- Permission-gated Apify Actor launcher, or import an existing authorized JSON/CSV export or Apify dataset ID.
- Source manifest checks; 180-day calendar/price coverage; six-bin X date coverage; unique post/sessions minimum; stable deduplication; SQLite join.
- Real post lexical or VADER sentiment; no retrospective likes/followers used for historic influence weights.
- Walk-forward direct n+1..n+5 Ridge forecasts against unchanged-close and price-only models; independently measurable outputs.
- Outcome metrics, research-only idealized next-open PnL diagnostic, chart and current-news optional separate Tavily/Exa context.
- Tests for early closes, future leakage, incomplete inputs, ticker ambiguity, and manifest authorization.

## Local setup (Mac or Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[data,test]'
pytest -q
```

## Step 1 — download actual 180-day NYSE daily prices (requires internet)

```bash
python -m cwt_unified.prices --ticker AAPL \
   --start 2026-05-18 --end-exclusive 2026-11-14 \
   --out raw_data/prices_AAPL.csv
```

This window is only an **example pinned to the last complete NYSE close on Friday November 13, 2026**. To forecast from a later day, recompute the dates from the actual exchange close and record that cutoff. This command was not run against Yahoo in this environment (no outbound network).

## Step 2 — supply REAL X posts, legally and with exact source proof

- Obtain a permissioned JSON/CSV export from your authorized provider or an existing Apify dataset ID. Do not fetch using an unauthorized cookie/account scraper.
- The raw export must have timestamps and text and ideally stable post IDs. A third-party provider's history claims require verification.
- Copy `examples/source_manifest.example.json` to `source_manifest.json`, fill **actual** values and document your rights to the data. Do NOT put API tokens in this file or GitHub. `access_authorized=true` only after verifying.
- Optional custom Actor run: provide verified Actor ID and input schema yourself, set `APIFY_TOKEN` and `CWT_AUTHORIZED_X_COLLECTION=YES` locally, and execute:

```bash
pip install -e '.[apify]'
python -m cwt_unified.apify_acquire \
  --actor-id YOUR_VERIFIED_ACTOR_ID \
  --actor-input actor_input.json \
  --out raw_data/actual_x_posts.json --max-items 5000
```

This is explicit cost-incurring action, not automatically executed by the forecast command. **Do not upload a token**; choose allowed collection and review costs first.

## Step 3 — real-data forecasting

```bash
python -m cwt_unified.real_run \
   --ticker AAPL \
   --prices-csv raw_data/prices_AAPL.csv \
   --x-export raw_data/actual_x_posts.json \
   --source-manifest source_manifest.json \
   --cutoff-utc 2026-11-13T21:00:00Z \
   --sentiment vader --out output_real
```

Alternative instead of `--x-export`: `--apify-dataset-id YOUR_EXISTING_AUTHORIZED_ID` with `APIFY_TOKEN` in local environment.

A run with inadequate source coverage aborts and records `readiness.json`. A genuinely valid run writes `output_real/results/latest_forecasts.csv`, `walkforward_predictions.csv`, `forecast_metrics.csv`, `sentiment_vs_price.png`, `one_page_outlook.md`, `audit_manifest.json`, `result_status.json`, `readiness.json` and SQLite inputs.

## Step 4 — optional current news (never historical model features)

```bash
pip install -e '.[news]'
# set TAVILY_API_KEY and/or EXA_API_KEY in your shell, NOT in code
python -m cwt_unified.news_context --query 'AAPL earnings today' \
    --out output_real/current_news.json
```

## Core truthfulness and limitations

- 180 calendar days of posts ≠ 180 sessions, nor proof of complete search coverage.
- News is context only. Retrospective likes are never time-travelled into X sentiment weighting.
- Posts downloaded after the historical event could have been edited or deleted; source snapshots are a higher bar than a date-matched export.
- n+5 refers to five **trading sessions**, not calendar days.
- Models predict prices, **not fundamental fair values**. No guaranteed investment returns.
- Statistical conclusions on ~125 sessions are fragile; no live portfolio execution is claimed.
- `.gitignore` prevents raw data, provider secrets and output payloads from being committed accidentally; verify before publishing.

## Required report states
`VERIFIED SOFTWARE` for passing tests, `PROVISIONAL RETROSPECTIVE RESEARCH` for legitimate but non-PIT X archives, `WITHHELD` for no licensed 180-day X data, `REJECTED` for missing rights or future-label leakage. There is no default `PROFITABLE` state.

See `docs/IMPLEMENTATION_SPEC.md` and `docs/COMPARATIVE_ARCHITECTURE_AND_REA.md`.

## GitHub repository status and CI

- GitHub Actions runs offline unit tests on Python 3.11, 3.12, and 3.13; it **does not** fetch live X or price data in CI.
- No live signal, profitable strategy, validated 180-day X corpus, or trading integration is claimed.
- Check `VALIDATION_STATUS.md` before citing any metrics on a CV.
- This snapshot has no declared open-source license yet; the repository owner must choose one separately. External dependency licenses remain their own.

## Additional research and audit documents

- [`docs/audits/unified-architecture-audit-2026-11-15.md`](docs/audits/unified-architecture-audit-2026-11-15.md)
- [`docs/audits/data-readiness-plan-2026-11-15.md`](docs/audits/data-readiness-plan-2026-11-15.md)
- [`docs/audits/repository-integration-audit-2026-11-15.md`](docs/audits/repository-integration-audit-2026-11-15.md)
- [`docs/REPOSITORY_CONTENTS.md`](docs/REPOSITORY_CONTENTS.md)
- [`archive/README.md`](archive/README.md) (older prototype ZIPs, not canonical)

**Current publication status:** Local Git-ready package. Repository creation and remote GitHub push must be independently verified.

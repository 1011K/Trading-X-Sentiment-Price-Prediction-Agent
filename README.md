# CWT Quant — AAPL forecasting research

A reproducible Python replay for the CrowdWisdomTrading assessment. It scores authorized X observations when availability is documented, aligns them to exchange sessions, and compares direct Ridge forecasts with simple baselines. Recent news is contextual and stays outside model inputs.

## Start here for employer review

**Status.** Live Apify and Tavily checks are verified. The AAPL assessment is partial because zero historical X posts qualified for evaluation.

| Review task | Where to start |
| --- | --- |
| Run provider checks with your own free keys | [Free-tier setup and commands](#verify-the-free-tier-apis) |
| Inspect live execution evidence | [Apify authentication](docs/api-evidence/apify.json), [Hello World execution and output](docs/api-evidence/apify-demo.json), [demo dataset read](docs/api-evidence/apify-demo-dataset.json), [Tavily quota and AAPL search](docs/api-evidence/tavily.json) |
| Review the price-only result | [AAPL evaluation and requirement matrix](docs/FINAL_SUBMISSION_AUDIT.md) |
| Reproduce the evaluation and run tests | [Fresh and frozen replay](docs/SUBMISSION_REPLAY.md), [offline test commands](docs/SUBMISSION_REPLAY.md#offline-tests) |
| Check outstanding limitations | [Historical X and review limits](docs/FINAL_SUBMISSION_AUDIT.md#outstanding-limitations) |

## Generate your own AAPL result

Use Git and Python 3.12 from a terminal. The fresh run fetches historical daily bars from Yahoo Finance and requires internet access. No coding agent, API key or Tavily capture is needed.

```sh
git clone https://github.com/1011K/Trading-X-Sentiment-Price-Prediction-Agent.git
cd Trading-X-Sentiment-Price-Prediction-Agent
git fetch origin refs/pull/1/head
git switch --detach FETCH_HEAD
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-real.txt -r requirements-submission.txt
PYTHONPATH=src python scripts/build_submission.py fresh --end 2026-11-13 --out outputs_submission/aapl-fresh
(cd outputs_submission/aapl-fresh && shasum -a 256 -c SHA256SUMS.txt)
```

Open `AAPL-evaluation.pdf` for evaluation and `latest-n0-n5.csv` for the latest forecast table. `manifest.json` records the price snapshot hash, run ID, source commit, and diagnostic risk metrics. A fresh download has its own snapshot and can reflect vendor revisions. The [exact frozen replay](docs/SUBMISSION_REPLAY.md#frozen-aapl-partial-submission) requires the original local price file. Both modes produce the PDF without news.

## Verify the free-tier APIs

Create your own free keys in the [Apify Console](https://console.apify.com/) and [Tavily dashboard](https://app.tavily.com/). Use Tavily Researcher with pay-as-you-go disabled. In Bash, read the keys without echoing them and export them for this terminal session only.

```bash
read -r -s -p "Apify token: " APIFY_TOKEN
printf '\n'
read -r -s -p "Tavily key: " TAVILY_API_KEY
printf '\n'
export APIFY_TOKEN TAVILY_API_KEY

PYTHONPATH=src python -m cwt_quant.api_verify apify-auth --inventory --out private_data/api-evidence/apify.json
PYTHONPATH=src python -m cwt_quant.api_verify apify-demo --out private_data/api-evidence/apify-demo.json
PYTHONPATH=src python -m cwt_quant.api_verify tavily-search --out private_data/api-evidence/tavily.json
```

`apify-auth` reads account metadata and optional inventory counts. `apify-demo` checks the free-plan cap and remaining allowance before starting one [official Hello World Actor](https://apify.com/apify/hello-world) with 128 MB and a 30-second timeout. It checks the Actor's key-value output. `tavily-auth` checks authentication and quota only. `tavily-search` repeats that check and sends one basic AAPL news request when free capacity is verified.

To verify the demo dataset separately, set `DEMO_DATASET_ID` to the `default_dataset_id` from **your** demo receipt. Confirm your included storage allowance before the read.

```bash
PYTHONPATH=src python -m cwt_quant.api_verify apify-dataset --demo-records \
  --dataset-id "$DEMO_DATASET_ID" --rights-basis "Own Hello World demo storage" \
  --max-items 10 --confirm-included-storage --out private_data/api-evidence/apify-demo-dataset.json
unset APIFY_TOKEN TAVILY_API_KEY
```

For an existing authorized X dataset, omit `--demo-records` and supply its actual ID, documented rights, and a bound that covers the entire dataset. The check runs the repository's X importer. An API download remains retrospective and supplies no forecast-time attestation. Each command writes a new receipt with sanitized counts, timestamps, HTTP responses and hashes. Use new filenames to repeat a check. Keep private receipts and credentials local.

### Live API results

On 16 November 2026 UTC, Apify authentication and both inventory requests returned HTTP 200. The inventory was empty before the official non-X Hello World run. The launch returned HTTP 201, the run succeeded, and its output read returned HTTP 200. A separate dataset read returned HTTP 200 with one generic demo record. Tavily returned HTTP 200 for both the quota check and one basic AAPL search, with three usable results.

Historical X stays **WITHHELD**. No X Actor ran and no historical posts were ingested. The demo record and Tavily news stayed outside the forecasting models. Tavily was the verified news provider. Exa was unused.

## Method and evidence

- The 180-calendar-day evaluation ends 13 November 2026. The 126 evaluation sessions and separate 68-session warm-up use observed OHLCV and a complete US equities calendar.
- n+0 is a same-day close forecast from information available at the open. n+1 through n+5 are post-close forecasts. Expanding folds use only mature labels and train-only scaling.
- Retrospective X text and cutoff-eligible observations are tracked separately. Retrieved engagement is never backdated. X forecasts remain withheld when eligible coverage is inadequate.
- Forecast comparisons use matched origins. The n+1 target is close-to-close. The trading diagnostic simulates next-session open-to-close positions with 10 bps per round trip and explicit cash periods. Its Sharpe measures that retrospective simulation.
- On the frozen AAPL sample, Ridge had lower RMSE at n+1 and higher RMSE at n+2 through n+5. The opening-price baseline had lower n+0 RMSE. These results describe one retrospective window.

## Partial submission index

- `AAPL-evaluation.pdf` and `outlook.md` cover the price results, zero verified historical X posts, and optional Tavily context. News remains outside all models.
- `latest-n0-n5.csv` and `research-figure.png` show the frozen forecasts and available evidence. `open-nowcast.csv`, `post-close-forecasts.csv`, `model_comparison.csv`, and `trade_ledger.csv` support reconciliation.
- [Reproduction guide](docs/SUBMISSION_REPLAY.md) gives the frozen-input checks and local packaging command. [Data source audit](docs/DATA_SOURCES_ZERO_COST.md) records the historical X coverage gap.

The builder also writes `evaluation.md`, `manifest.json`, `x-coverage.json`, and `SHA256SUMS.txt`. Generated files stay local pending redistribution clearance. The public PR contains code, instructions, and aggregate evidence.

[Current integration register](docs/INTEGRATION_MATRIX.md) maps all 62 prior candidates to this implementation.

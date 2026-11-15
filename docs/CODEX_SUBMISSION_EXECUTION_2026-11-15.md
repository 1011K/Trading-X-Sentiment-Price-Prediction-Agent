# CWT Quant: Codex execution brief | 15 November 2026

**Status:** execution handoff. This document does **not** certify a completed historical X backtest. The employer's reported submission deadline is **17 November 2026** (verify the exact hour).

**Source repository:** `1011K/Trading-X-Sentiment-Price-Prediction-Agent`.
**Baseline main commit:** `ebd50295c6c5c0dd29ae06fc28db60d8ce2c7a8e`.
**Working branch:** `handoff/cwt-submission-2026-11-15` (make a new implementation branch from current main if preferred).
**Employer brief:** https://docs.google.com/document/d/1OWrHpiqUSkqjncbRaQ3Z2Lb3EOBmFIYTCO0_BwGdhFw/edit
**Historical dataset link:** https://docs.google.com/document/d/1w-Y86OjkiOjlIIth0VgTAohql9zcGi3uoDNYTaTsZuw/edit

## Important provided files

The user also provided `cwt_submission_upgrade.py`, `test_cwt_submission.py`, a 10-stock forecast CSV, two PNGs and a five-page `CrowdWisdomTrading_Evaluation_Report.pdf` **in ChatGPT attachments**. They are **not** assumed to be present in this GitHub repository or Codex's workspace. Ask the user to attach them to Codex if missing. Treat all as **reference candidates, not validated results**.

## Must-not-publish claims and defects

- The proposed 10-stock demonstration creates **synthetic social posts, news and parts of OHLCV**, including synthetic social sentiment built from `fwd_1d` (future price information). The 26,560 posts, 632 news records, and associated Sharpe improvements are **not verified historical X backtest evidence**.
- `--tickers` is parsed in the candidate script but the benchmark runner does not honor the selection.
- A fixed 16:00 New York close is wrong for early-close sessions, including 27 Nov 2026.
- Historical likes, views, replies and followers downloaded today are not point-in-time engagement snapshots from the historical forecast cutoff.
- Candidate `n+0` nowcast implicitly changes the origin to market open while other horizons are post-close forecasts.
- The candidate contextual-bandit test validates only action membership in {0, 0.5, 1}, not chronological out-of-sample learning, transaction-cost accounting or profitability.
- Candidate performance calculations are not a verified executable next-session trading ledger.
- **Never silently delete** `docs/INDEPENDENT_AUDIT.md`, `docs/CODEX_HANDOFF.md`, `run_multi_audit.py`, or `archive/`. Preserve current repository work.

## Exact implementation order

1. **Freeze and re-run baseline:** `python -m pip install -r requirements.txt`, `PYTHONPATH=src python -m pytest -q tests`, and `PYTHONPATH=src python -m cwt_quant.cli --ticker AAPL --out outputs_synthetic`. Record commit SHA and output. Keep synthetic data labeled synthetic.

2. **Provide a real X ingest path:** create an approved Apify actor adapter and/or strict export loader (JSON, JSONL, CSV). Check actor name, schema, pricing, pagination and permitted use. Require true `post_id`, ticker, `created_at`, actual text, source and `observed_at`; handle pagination, duplicate IDs and missing values. Preserve retrieval/availability timestamps. No historical-as-of proof means label records retrospective and disable historical influence features. Do not invent `followers=1000`, `likes=0` as if observed, or synthetic replacements.

3. **Price import and exact evaluation window:** verify real AAPL daily OHLCV and corporate actions, save source, hash and price policy. For an inclusive 180-calendar-day window ending 2026-11-13, start 2026-05-18. Keep training warm-up separate from evaluation and verify XNYS session calendar including holidays/DST/early close.

4. **Database and point-in-time features:** use SQLite (price bars, X posts, source manifests, as-of session panel, forecast ledger) with keys/indexes and idempotent writes. Keep recent Tavily/Exa news distinct from the historical X + price ML feature set. News belongs in the current one-page outlook unless separately pre-registered and historically point-in-time proven.

5. **Correct forecast semantics:** at post-close origin t, `n+0 = observed C[t]`, and direct `n+h = C[t]*exp(y_hat[t,h])` for h=1..5 trading sessions. Train at origin t only on i with `i+h <= t`; all scalers fit on train exclusively. If a pre-close nowcast is wanted, report it as an independent experiment with its own cutoff.

6. **Model comparison:** no-change, price-only Ridge, price+X Ridge on **identical valid origins**. Withhold the price+X result if insufficient licensed historical X coverage. Optional influence ablation only when point-in-time engagement and follower snapshots are present. Treat RL as experimental and do not claim observed alpha from a unit test.

7. **Executable performance accounting:** compute per-horizon MAE/RMSE/direction accuracy and matched-origin sample counts; simulate any strategy via a chronological next-eligible-fill trade ledger with 10 bps documented costs and position transitions. Sharpe/Sortino/max drawdown must be derived from that ledger, not overlapping h-day predictions counted as separate daily trades. If no valid fills/prices, mark risk metrics WITHHELD.

8. **Rebuild outputs from actual saved replay:** current sentiment outlook (1 page), matrix chart, CSV forecasts, Markdown evaluation report and optional PDF. State exact data coverage, X source, run timestamp, model versions, OOS dates, provenance hashes, and limitations. Do **not** reuse unsupported synthetic tables or the existing Gemini PDF as real-market evidence.

9. **Acceptance tests:** future post and engagement leakage; XNYS early close; different tickers; missing historical corpus fail-closed; no news backdating; duplicate posts; data provenance; `n+0` correctness; exact 180-day window; direct-horizon purge; deterministic replay; trading cost ledger; `--tickers` selection (if implemented); secret scanning; CI on Python 3.10/3.12 or clearly justified supported versions.

10. **Publish through a review branch:** push actual source and test outputs, verify CI, open PR against main. Do not merge until the checked output has provenance. Existing public repo is sufficient; do not create a replacement repo. Keep `main` intact during review.

## Scope discipline

The employer requests **one chosen asset**, not 10, and mentions *machine learning / reinforcement learning*: an auditable ML pipeline is within the permitted formulation. Finish one genuine historical asset first. Optional 10-stock support and ASTRA integration are **after** submission correctness. Keep ASTRA's private `1011K/astra-financial-platform` private. Integrate later via existing Mosaic News / engine interfaces, with separate evidence and validation status.

## Secrets and delivery

`APIFY_TOKEN`, `TAVILY_API_KEY`, `EXA_API_KEY`, and optional price-data key must be environment variables; commit `.env.example` with **names only**. Actor ID `apidojo/tweet-scraper` is an identifier, **not an API key**, and must be verified against current actor schema. Do not email unprotected working API keys. The employer's requested deliverables are a public repository URL, reproducibility details (including actor identifiers and secure credential provision as appropriate), and an evaluation report (Markdown/PDF).

If historical X data cannot be obtained lawfully before the deadline, **submit an honestly labeled prototype** with synthetic test results and price-only real-data baseline, clear list of unmet requirements, and a request for authorized historical sample or acceptance of a limited submission. Do not claim complete real X performance.

## What Codex should return

- implementation branch and PR URLs, exact commit SHA;
- command transcript and green/failed test count;
- actual input source/availability/coverage table;
- genuine output manifest, report and charts;
- list of VERIFIED / DISPUTED / WITHHELD / REJECTED / EXPERIMENTAL claims;
- a short, truthful employer submission email, with only verified attachments named;
- separate ASTRA integration backlog **without changing private ASTRA in this phase**.

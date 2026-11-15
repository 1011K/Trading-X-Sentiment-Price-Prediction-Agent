# CWT data acquisition: exact next actions | 15 November 2026

**Status: executable import layer, NO actual 180-day X corpus is included.** Do not substitute fabricated posts or mislabel older X/StockTwits data as contemporary X.

## 1. What the employer requires

Source: https://docs.google.com/document/d/1OWrHpiqUSkqjncbRaQ3Z2Lb3EOBmFIYTCO0_BwGdhFw/edit

- One asset; previous agreed default AAPL/NYSE.
- Last 180 **calendar** days of X posts (ticker/cashtag/keywords), historical prices for the period, post timestamps UTC/EST, text, likes/reposts/views/followers.
- News from Tavily (for outlook); Exa listed for credentials/reproduction. News must not enter predictive feature matrix because brief limits predictors to sentiment and price only.
- Database join; sentiment and price features; prices n+0 observed and n+1..n+5 future forecasts; time-respecting walk-forward evaluation; chart; one-page current outlook; Sharpe/Sortino/max drawdown for clearly documented trading simulation; code repository and emailed delivery.

Historical source list: https://docs.google.com/document/d/1w-Y86OjkiOjlIIth0VgTAohql9zcGi3uoDNYTaTsZuw/edit

The historical link is a *list* of disparate datasets, NOT a ready-made last-180-day X export. The 2025–2026 Bitcoin Tweets dataset can only be used after actual maximum/minimum dates, 180-day coverage, license and fields are verified, and would require crypto 24/7 calendar changes. The current AAPL model **cannot** ingest BTC with NYSE trading sessions.

## 2. Data acquisition path

Preferred: rights-cleared, authorized X data from the employer/provider or official authorized API, exported through Apify into a local JSON/JSONL/CSV. Confirm the provider's right to access/redistribute, exact input query and 180-day historical coverage. X's current terms restrict unauthorized scraping; the employer's explicit Apify request does not alone override X's terms.

Verify a provider Actor's price and sample quality **before** paying or triggering a collection job. Credits consumed by a hosted data Actor are independent of ChatGPT/Claude/Codex credits. Do not run unlimited crawls or route around blocks. Use account-level spending caps. If no compliant source at an affordable price, document the limitation and ask the employer whether a historical licensed dataset is acceptable instead.

## 3. Actual preparation commands

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
pytest -q

# Export daily 1d prices to a CSV with Date,Open,Close in a consistent raw or adjusted policy.
# Download a permitted 180+ day source separately; verify ticker, timezone, splits, dividends.
# Then use downloaded authorized Apify post export (JSON, JSONL or CSV):
python -m cwt_unified.ingest \
  --posts-export path/to/apify_posts.json \
  --prices-export path/to/AAPL_daily_prices.csv \
  --ticker AAPL \
  --cutoff-utc 2026-11-13T21:00:00Z \
  --out input_real

# Or fetch an existing permitted Apify dataset by ID (no actor execution):
# export APIFY_TOKEN=...  # set in shell locally; never share or commit
python -m cwt_unified.ingest \
  --apify-dataset-id YOUR_ACTUAL_DATASET_ID \
  --actor-id ACTUAL_ACTOR_ID \
  --prices-export path/to/AAPL_daily_prices.csv \
  --ticker AAPL \
  --cutoff-utc 2026-11-13T21:00:00Z \
  --out input_real

# Now train/evaluate with existing core:
python -m cwt_unified.cli run --prices input_real/prices.csv \
  --posts input_real/posts.csv --ticker AAPL --out results_real
```

- Output posts.csv; prices.csv; research.sqlite containing prices/posts/post_session_map plus daily_post_counts view; data_audit.json.
- The input code strictly filters `$AAPL` cashtags for precision. This is a *narrow initial subset* and does **not** alone fulfill the employer's broader keyword coverage. Expand after a reviewed ticker disambiguation test.
- The importer does not supply historical engagement snapshots, because retrospective likes are not valid point-in-time features. It preserves their counts for descriptive audit only; `--allow-influence` must remain OFF.
- The importer fails if requested price sessions are missing rather than silently joining different dates.
- `cutoff-utc` is a pinned research as-of timestamp, not the current clock. 13 Nov 2026 21:00Z equals the normal NYSE 16:00 ET close. November 15 is a Sunday; latest complete NYSE session then is Friday Nov 13.
- Raw Open/Close are not interchangeable with adjusted Close. Preserve same units; independently verify corporate actions and tradability.

## 4. Debug gates

D0: actual post-export rows exist, data rights and source documented.
D1: coverage spans the target window; provider query completeness and missing date pockets logged.
D2: source post timestamps and price cutoff align; no future posts or engagements.
D3: full X/price data maps into DB; raw counts reconcile with mapped session counts.
D4: price-only and sentiment-plus-price model share identical origins; no leakage.
D5: real forecast error comparisons against no-change; n+1 costed strategy with realistically timed signal and fill assumptions.
D6: Tavily/Exa current context, reproducibility, one-page outlook, report, repository, secret scan and emailed submission.

## 5. Outstanding risks

- No live provider was authenticated or executed here: this ZIP contains only a deterministic importer plus synthetic tests.
- Day coverage alone cannot prove every relevant post was collected; record search queries, pagination total, retrieval timestamps, and provider limitations. Sparse posts are not necessarily missing data.
- Per the original document, deadline is 5–7 days from assignment issue. A separate Internshala message was previously reported as 17 Nov 2026. Verify exact cutoff if necessary; don't assume the PDF sets a fixed date.
- Don't email unrestricted private API tokens or publish secrets. Give employer actor IDs, `.env.example`, scoped/revocable credentials through an agreed secure channel if absolutely necessary.

## Optional automated daily prices and local sentiment scoring

For the pinned Friday 13 November 2026 research close, the 180-calendar-day window starts 18 May 2026. The actual end date supplied to yfinance must be **exclusive**; 14 Nov includes 13 Nov.

```bash
pip install -e '.[data]'
python -m cwt_unified.prices --ticker AAPL --start 2026-05-18 \
  --end-exclusive 2026-11-14 --out raw_data/AAPL_daily_prices.csv
# No external sentiment API or LLM credit required for VADER (downloads Python package only).
python -m cwt_unified.score --posts input_real/posts.csv --method vader \
  --out input_real/posts_vader.csv
python -m cwt_unified.cli run --prices input_real/prices.csv \
  --posts input_real/posts_vader.csv --ticker AAPL --out results_real_vader
```

The default `lexical` and optional `vader` models are both *weak sentiment baselines*. VADER handles emoji/intensifiers/negation better than a few hand-picked keywords but does **not** reliably infer asset-specific stance or sarcasm. Optional later experiment: CardiffNLP Twitter-RoBERTa sentiment (CC BY 4.0, review model license) with manual finance-statement labels and a price-predictive ablation; do not download or use it blindly. ProsusAI FinBERT weights are CC BY-NC-SA 4.0 and cannot be assumed permitted for employer commercial use.

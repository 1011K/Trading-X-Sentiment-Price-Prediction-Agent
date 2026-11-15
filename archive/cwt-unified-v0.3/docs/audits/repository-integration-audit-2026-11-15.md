# CWT Sentiment + Price: 62-repository integration and red-team register

Audit timestamp: 2026-11-15. Sources: public repository metadata, README/root inspections for priority repos, official model card, official X terms, and inspected current local `CWT_Quant_DataReady_v0_2_15Nov2026` code. A recent push and recognized license are *not* proof of correct behavior or a successful integration. License column says **Not detected** when GitHub metadata lacked an SPDX match; this is not a legal ruling. Most low-priority repos received metadata-level review, not line-by-line code review.

## Executive decision

**Core to retain:** local Python/SQLite + `exchange_calendars` + scikit-learn Ridge/naive baselines + Matplotlib + pytest. Add Apify's official client only as an **authorized** dataset/Actor interface, yfinance daily price verification, VADER baseline, optional CardiffNLP Twitter-RoBERTa model, Tavily context and corrected Exa SDK (`exa-labs/exa-py`) if credentials exist. Keep actual 180-day market results WITHHELD until licensed X-source data is verified.

**Compliance gate:** Official X Terms effective 2026-10-09 expressly prohibit scraping without prior written consent. The fact that a third-party Actor or repo provides a technical method does not demonstrate that source rights, redistribution and employer use are authorized. Confirm provider rights or use rights-cleared licensed historical data; never use account/cookie pool tools to evade controls. No API keys in a public repository or emailed as reusable secrets; provide scoped reproducibility procedures and secure credential handoff.

**Four non-negotiable data caveats:** (1) X `created_at` != retrieval timestamp; (2) engagement seen now != historical engagement; (3) 180-calendar-day coverage != complete X search coverage; (4) news collected now is context only and cannot be used to predict past closes.

## Verified code-level gaps in the local v0.2 package

1. `src/cwt_unified/data.py::is_relevant()` only accepts a literal `$TICKER`. Assignment wants ticker/cashtag **and keyword** searches; keep cashtag precision as baseline, introduce asset-aware keyword matching + false-positive audit as a separate variant.
2. `src/cwt_unified/ingest.py` imports existing datasets but does not initiate an Apify Actor run. True actor ingestion and permission checks are outstanding; do not call the live source acquired merely because an actor URL exists.
3. The `historical_engagement_snapshots_verified` audit flag is false for ordinary exports. Influence weighting is disabled correctly; adding libraries does not fix missing point-in-time snapshots.
4. Prices: `load_prices` checks contiguous listed exchange sessions; still need split adjustment/source license and last-close timestamp verification. XNYS cannot be reused for a BTC/24-hour asset.
5. The fixture tests verify software mechanics, not real predictive skill. Close-to-next-open practical signal and next-open-to-close trade diagnostic are economically different objects; do not conflate their metrics.
6. `n+0` is an *observed* close, not a learned prediction; n+1..n+5 targets overlap and require horizon-specific label eligibility + dependence-robust uncertainty.

## Comprehensive repository decision table

### X ingestion / Apify

| Repository | Decision | License metadata | Last pushed UTC | How to use / why not |
|---|---|---|---|---|
| [apify/apify-client-python](https://github.com/apify/apify-client-python) | **USE** | Apache-2.0 | 2026-11-13 | Official actor and dataset API, retry/pagination; only if data acquisition is authorized. |
| [apify/apify-docs](https://github.com/apify/apify-docs) | **REFERENCE** | Apache-2.0 | 2026-11-15 | Provider API examples and dataset pagination contracts. |
| [0xrish/X-Twitter-Advanced-Search-Tweet-Scraper](https://github.com/0xrish/X-Twitter-Advanced-Search-Tweet-Scraper) | **REJECT** | Not detected | 2026-08-03 | Repo contains only a marketing README linking a commercial Actor; no usable Python collector source to merge. |
| [Xquik-dev/x-twitter-scraper](https://github.com/Xquik-dev/x-twitter-scraper) | **REFERENCE** | MIT | 2026-11-13 | Third-party commercial X service/skills, not proven permission to ingest X. Do not install agent skills or share credentials. |
| [robbyczgw-cla/x-apify](https://github.com/robbyczgw-cla/x-apify) | **ADAPT** | MIT | 2026-08-31 | Study defensive field maps and local caching; actor-specific inputs require verification; no need to install wrapper. |
| [apidojo-io/social-media-skills](https://github.com/apidojo-io/social-media-skills) | **REFERENCE** | Not detected by GitHub | 2026-09-02 | Actor schema/reference; README claims Apache-2.0 but no recognized LICENSE. Free plan limited; do not assume rights. |
| [akshathakurr/gtm-engine](https://github.com/akshathakurr/gtm-engine) | **REJECT** | MIT | 2026-08-22 | Marketing workflow; Twitter profile feature is irrelevant to historic asset sentiment. |
| [itsmohitkumar/Stock-Sentimental-Analysis](https://github.com/itsmohitkumar/Stock-Sentimental-Analysis) | **REFERENCE** | Not detected | 2024-08-23 | Legacy demonstration, not maintained or licensed for code reuse. |

### X alternatives

| Repository | Decision | License metadata | Last pushed UTC | How to use / why not |
|---|---|---|---|---|
| [tweepy/tweepy](https://github.com/tweepy/tweepy) | **CONDITIONAL USE** | MIT | 2026-07-02 | First-party X API Python client if an authorized historical endpoint and suitable plan are available. |
| [vladkens/twscrape](https://github.com/vladkens/twscrape) | **REJECT** | MIT | 2026-11-13 | Logged-in account-pool rotation; avoid non-authorized scraping. |
| [d60/twikit](https://github.com/d60/twikit) | **REJECT** | MIT | 2026-03-10 | Internal/GraphQL API route; operational and permission risks; not appropriate for deadline. |
| [JustAnotherArchivist/snscrape](https://github.com/JustAnotherArchivist/snscrape) | **REJECT** | GPL-3.0 | 2023-11-15 | X functionality stale; not a safe current-data source. |
| [twintproject/twint](https://github.com/twintproject/twint) | **REJECT** | MIT | 2023-02-23 | Archived and historically broken for current X. |

### Prices

| Repository | Decision | License metadata | Last pushed UTC | How to use / why not |
|---|---|---|---|---|
| [ranaroussi/yfinance](https://github.com/ranaroussi/yfinance) | **USE** | Apache-2.0 | 2026-11-12 | Daily OHLC prices only; independently verify corporate-action adjustment, session coverage and permitted usage. |
| [ccxt/ccxt](https://github.com/ccxt/ccxt) | **CONDITIONAL** | MIT | 2026-11-13 | Only if changing asset to BTC and venue-specific crypto prices; do not merge with NYSE calendar. |
| [planet-winter/ccxt-ohlcv-fetcher](https://github.com/planet-winter/ccxt-ohlcv-fetcher) | **REJECT** | MIT | 2022-12-08 | Old, redundant wrapper. |
| [alpacahq/alpaca-trade-api-python](https://github.com/alpacahq/alpaca-trade-api-python) | **REJECT** | Apache-2.0 | 2024-12-02 | Archived legacy SDK; replaced by alpaca-py if ever needed. |
| [binance/binance-connector-python](https://github.com/binance/binance-connector-python) | **REJECT** | MIT | 2026-11-12 | Single exchange; unnecessary for AAPL and adds venue-specific assumptions. |

### News / context

| Repository | Decision | License metadata | Last pushed UTC | How to use / why not |
|---|---|---|---|---|
| [tavily-ai/tavily-python](https://github.com/tavily-ai/tavily-python) | **USE** | MIT | 2026-10-26 | News search for the one-page *current* context report, NOT historical model features. |
| [exa-labs/exa-py](https://github.com/exa-labs/exa-py) | **CONDITIONAL USE** | MIT | 2026-11-06 | CORRECTED URL: original exa-ai/exa-py returned 404. Optional corroboration/source discovery; logging and limits. |
| [kobyal/ai-news-briefing](https://github.com/kobyal/ai-news-briefing) | **REJECT** | Not detected | 2026-11-15 | Ten-agent framework unnecessary for one-asset report; no recognized license. |
| [ranahaani/GNews](https://github.com/ranahaani/GNews) | **REFERENCE** | MIT | 2026-10-24 | Optional supplementary news discovery; verify original publishers and timestamp. |
| [mattlisiv/newsapi-python](https://github.com/mattlisiv/newsapi-python) | **REFERENCE** | MIT | 2025-12-22 | Alternative news API client, but unnecessary extra account/limits. |

### Sentiment

| Repository | Decision | License metadata | Last pushed UTC | How to use / why not |
|---|---|---|---|---|
| [yya518/FinBERT](https://github.com/yya518/FinBERT) | **REFERENCE** | Apache-2.0 (repo) | 2023-07-23 | Finance-language benchmark, not assumed best for X slang; model WEIGHTS license must be checked separately. |
| [FinBERT-SIMF/FinBERT-SIMF](https://github.com/FinBERT-SIMF/FinBERT-SIMF) | **REJECT** | Not detected | 2022-10-20 | Old FX/BTC-specific experiment without recognized license. |
| [cardiffnlp/tweeteval](https://github.com/cardiffnlp/tweeteval) | **CONDITIONAL USE** | Not detected (repo) | 2022-07-08 | Use published CC-BY-4.0 Twitter-RoBERTa *model* through Transformers, not unlicensed repository code. |
| [cjhutto/vaderSentiment](https://github.com/cjhutto/vaderSentiment) | **USE** | MIT | 2026-03-02 | Fast reproducible social-text baseline; optional data-ready module already has integration. |
| [sloria/TextBlob](https://github.com/sloria/TextBlob) | **REJECT** | MIT | 2026-11-09 | Redundant and less context-aware sentiment baseline. |
| [laugustyniak/awesome-sentiment-analysis](https://github.com/laugustyniak/awesome-sentiment-analysis) | **REFERENCE** | Not detected | 2026-07-20 | Reading list; no pipeline code to integrate. |

### Storage

| Repository | Decision | License metadata | Last pushed UTC | How to use / why not |
|---|---|---|---|---|
| [duckdb/duckdb](https://github.com/duckdb/duckdb) | **DEFER** | MIT | 2026-11-13 | Excellent Parquet analytics but redundant at 180-day one-asset scale; keep existing SQLite. |

### Models / horizons

| Repository | Decision | License metadata | Last pushed UTC | How to use / why not |
|---|---|---|---|---|
| [skforecast/skforecast](https://github.com/skforecast/skforecast) | **REFERENCE** | BSD-3-Clause | 2026-11-15 | Direct multi-step wrappers; existing five-horizon Ridge already implements transparent target eligibility. |
| [unit8co/darts](https://github.com/unit8co/darts) | **REJECT** | Apache-2.0 | 2026-11-13 | Too large and too many model choices for tiny daily training set. |
| [Nixtla/neuralforecast](https://github.com/Nixtla/neuralforecast) | **REJECT** | Apache-2.0 | 2026-11-12 | Deep neural forecasting overfits risk at 180 calendar days. |
| [Nixtla/statsforecast](https://github.com/Nixtla/statsforecast) | **DEFER** | Apache-2.0 | 2026-11-13 | Statistical baseline optional, but simple last-close and return-mean baselines first. |
| [jdb78/pytorch-forecasting](https://github.com/jdb78/pytorch-forecasting) | **REJECT** | Unverified | unverified | Redirecting repository; heavy temporal-fusion models unjustified. |
| [microsoft/LightGBM](https://github.com/microsoft/LightGBM) | **DEFER** | Unverified here | unverified | Library available, but tiny sample means heavy tuning/multiple comparisons. |
| [dmlc/xgboost](https://github.com/dmlc/xgboost) | **DEFER** | Apache-2.0 | 2026-11-11 | One predeclared non-linear comparison only if sufficient data and holdout. |
| [microsoft/forecasting](https://github.com/microsoft/forecasting) | **REJECT** | 404 | not found | Given repository path returned 404; not a component. |

### Validation / backtesting

| Repository | Decision | License metadata | Last pushed UTC | How to use / why not |
|---|---|---|---|---|
| [eslazarev/purged-cross-validation](https://github.com/eslazarev/purged-cross-validation) | **ADAPT** | MIT | 2026-11-14 | Reference leakage-safe time splits; existing origin/horizon label-release logic should remain explicit. |
| [polakowo/vectorbt](https://github.com/polakowo/vectorbt) | **DEFER** | NOASSERTION | 2026-11-11 | Useful research diagnostics, but uncertain detected license and extra dependency unnecessary for one simple strategy. |
| [kernc/backtesting.py](https://github.com/kernc/backtesting.py) | **REJECT** | AGPL-3.0 | 2026-08-05 | AGPL obligations and duplication; no need for engine. |
| [ranaroussi/quantstats](https://github.com/ranaroussi/quantstats) | **REFERENCE** | Apache-2.0 | 2026-11-02 | Optional tearsheet; compare metrics against deterministic native implementation. |
| [mementum/backtrader](https://github.com/mementum/backtrader) | **REJECT** | GPL-3.0 | 2024-08-19 | Event-driven trading framework and GPL not justified for this assignment. |

### Visualization

| Repository | Decision | License metadata | Last pushed UTC | How to use / why not |
|---|---|---|---|---|
| [streamlit/streamlit](https://github.com/streamlit/streamlit) | **DEFER** | Apache-2.0 | 2026-11-15 | Optional demo UI after report and real-data evaluation are complete. |
| [plotly/plotly.py](https://github.com/plotly/plotly.py) | **DEFER** | MIT | 2026-11-13 | Can improve visuals, but existing Matplotlib already meets PNG chart requirement. |

### End-to-end examples

| Repository | Decision | License metadata | Last pushed UTC | How to use / why not |
|---|---|---|---|---|
| [liamhavers/Financial-Sentiment-Alpha-Prediction-System](https://github.com/liamhavers/Financial-Sentiment-Alpha-Prediction-System) | **ADAPT IDEAS** | Not detected | 2026-07-08 | Thesis, sentiment decay, post-volume floor, relative/benchmark comparisons; uses StockTwits, NOT X. Do not copy unlicensed code. |
| [mmkeskar/Stock-Price-Prediction-with-Sentiment-Analysis](https://github.com/mmkeskar/Stock-Price-Prediction-with-Sentiment-Analysis) | **REJECT** | Not detected | 2021-02-17 | Old LSTM demonstration; no advantage over leakage-safe baseline. |
| [Aaron-Paul/Bitcoin-Price-Twitter-Sentiment-Analysis](https://github.com/Aaron-Paul/Bitcoin-Price-Twitter-Sentiment-Analysis) | **REFERENCE** | Not detected | 2021-03-02 | Historical BTC/X case study; dated data and no recognized license. |
| [Prerna77Arora/Stock_Price_Prediction_Tool](https://github.com/Prerna77Arora/Stock_Price_Prediction_Tool) | **REJECT** | Not detected | 2025-10-27 | LSTM/FinBERT/Streamlit combination adds complexity without validation. |
| [scorpionhiccup/StockPricePrediction](https://github.com/scorpionhiccup/StockPricePrediction) | **REFERENCE** | MIT | 2023-08-08 | Classical methods; audit target/feature times before reusing any pattern. |
| [alvarobartt/twitter-stock-recommendation](https://github.com/alvarobartt/twitter-stock-recommendation) | **REFERENCE** | MIT | 2020-01-02 | Historical recommendation approach, dated; avoid copying train/validation. |
| [AshwiniDPrabhu/Stock-Prediction-Using-Twitter-Sentiment-Analysis](https://github.com/AshwiniDPrabhu/Stock-Prediction-Using-Twitter-Sentiment-Analysis) | **REJECT** | Not detected | 2020-05-13 | Older RandomForest/SVR example; no recognized license. |
| [letsbegincode/stock_trends_prediction](https://github.com/letsbegincode/stock_trends_prediction) | **REFERENCE** | Apache-2.0 | 2025-10-29 | Repo description mentions Reddit, not necessarily X; not direct schema match. |
| [quantinsti/AI-in-Trading-Workflow](https://github.com/quantinsti/AI-in-Trading-Workflow) | **REFERENCE** | NOASSERTION | 2026-01-13 | News/LLM workflow reference, but model feature scope excludes news; verify individual notebook licenses. |
| [VAnkataBot/TraderAI](https://github.com/VAnkataBot/TraderAI) | **REJECT** | Not detected | 2026-02-18 | News-driven trading agent outside one-asset X research scope. |
| [YashBoda/AInvest](https://github.com/YashBoda/AInvest) | **REJECT** | Not detected | 2025-09-05 | Unlicensed agent and no clear validation advantage. |
| [aryangoshalia/ml-market-forecasting](https://github.com/aryangoshalia/ml-market-forecasting) | **ADAPT IDEAS** | Not detected | 2026-09-07 | Strong negative-case README, adversarial leakage tests, realistic cost baseline; do not copy unlicensed code or accept claimed numbers unchecked. |
| [sunandha01/financial-market-prediction](https://github.com/sunandha01/financial-market-prediction) | **REFERENCE** | Not detected | 2026-09-26 | Time-split techniques; little reusable value above existing walk-forward. |
| [tejaaa69/Alpha-Engine-for-Commodities-](https://github.com/tejaaa69/Alpha-Engine-for-Commodities-) | **REFERENCE** | Not detected | 2026-06-18 | Purged validation concept; commodities/triple-barrier are not assignment targets. |
| [nyannbob/ARIMA-LSTM-price-prediction](https://github.com/nyannbob/ARIMA-LSTM-price-prediction) | **REJECT** | GPL-3.0 | 2024-11-29 | Heavy LSTM hybrid + licensing complications; low sample. |
| [arshkazi/Commodities_price_prediction](https://github.com/arshkazi/Commodities_price_prediction) | **REFERENCE** | Not detected | 2026-08-09 | General time-series concepts only; wrong market/target. |

### Catalogs

| Repository | Decision | License metadata | Last pushed UTC | How to use / why not |
|---|---|---|---|---|
| [wilsonfreitas/awesome-quant](https://github.com/wilsonfreitas/awesome-quant) | **REFERENCE** | Not detected | 2026-11-15 | Discovery index, not software; every candidate still requires its own license/code verification. |

**Repos enumerated:** 62, comprising the provided list with the broken Exa path replaced by the current official SDK. All originally named projects are covered.

## High-value additions not present in initial list

- [`gerrymanoim/exchange_calendars`](https://github.com/gerrymanoim/exchange_calendars), Apache-2.0. **ALREADY IN CURRENT CODE**; pinned NYSE half-day/holiday close mapping. Keep.
- [`huggingface/transformers`](https://github.com/huggingface/transformers), Apache-2.0. **OPTIONAL** local CardiffNLP model runner; model card weights CC-BY-4.0 with attribution. First compare against VADER and manually annotated ticker-specific stance sample.
- [`unionai-oss/pandera`](https://github.com/unionai-oss/pandera), MIT. **OPTIONAL** typed schemas/data contracts, helpful if Apify data has multiple schema variants, not mandatory.
- [`pytest-dev/pytest`](https://github.com/pytest-dev/pytest), MIT. **ALREADY USED**; add property/metamorphic leakage tests, strict fixtures and real-data smoke tests.
- [`scikit-learn/scikit-learn`](https://github.com/scikit-learn/scikit-learn), BSD-3-Clause. **ALREADY IN CURRENT CODE**; keep small deterministic Ridge and on-train-only scaling.
- [`alpacahq/alpaca-py`](https://github.com/alpacahq/alpaca-py), Apache-2.0. Supported successor to the archived Alpaca SDK **only if** actual broker market data is needed later; not needed now.
- `ruff` for fast lint and `pip-audit` for vulnerability checks. **OPTIONAL** release QA, no agents or ongoing subscriptions needed.

## Implementation plan

**P0: reproducible real-data pipeline**

1. Freeze asset = AAPL, exchange = XNYS, data cutoff, 180 calendar-day window, tickers/keywords, source permissions, adjusted/unadjusted close policy.
2. Acquire **licensed X data** or permissioned provider export, preserving `post_id`, `author_id`, `created_utc`, `observed_asof_utc` (if genuinely known), full text, engagement and follower snapshots *if timestamped*, queries/actor/version/pages/total retrieval, retrieved UTC and source-use rights. If inaccessible, mark P0 blocked and make the limitation explicit to employer.
3. Verify daily price bars with an independently auditable download, schedule coverage, corporate actions, symbol/exchange match and UTC close.
4. Normalize schema to SQLite with unique keys, provenance hashes, immutable raw export, data-quality audit, strict point-in-time gates and source cost ledger.
5. Write a search coverage matrix by month/week/query; label missing data explicitly. Do not infer full coverage from presence of one post in a week.

**P1: reduce model uncertainty**

6. Compare naive/no-change, price-only Ridge, price+VADER, optionally price+Twitter-RoBERTa on identical test origin dates. Evaluate both price RMSE skill and directional metrics by horizon.
7. Annotate 50-100 asset-specific posts with bullish/bearish/neutral stance and ambiguity to challenge sentiment classifier; do not conflate generic positive tone with upward stock direction.
8. Validate with expanding walk-forward and per-horizon release cutoffs; label dependence across 2-5-day overlapping targets; report uncertainty if sample permits.
9. Model influence ONLY with proven historical engagement snapshots; otherwise keep experimental section disabled.
10. Compute Sharpe/Sortino/drawdown on a separately declared executable-style strategy. Require next-open fills, cost assumptions, use price data available at close(t), no cash-to-close magical fills. Report sample size and limitations.
11. Latest Tavily/Exa news appears **only** in current sentiment narrative, never past model features.
12. Publish a secret-clean README/report with actor ID and permissioned reproducibility procedure, without sharing X credentials or commercially restricted raw tweets.

**Explicit stop conditions:** missing source permission; missing historical time coverage; wrong calendar; unsupported corporate-action adjustment; leakage of future engagement; implausible 5-day OOS performance without independent test; unauthorized model/data licenses; no usable benchmark comparison. Any such failure must block a claim of predictive skill or employer-ready evaluation.

## Ready-to-send free-agent review tasks

**Grok (source auditor):** 'Audit our 180-day AAPL X-data acquisition plan against the original CWT assignment. Check each proposed provider for actual 180-day historical coverage, UTC created-time, author/engagement fields, pagination/completeness, source rights, Apify pricing and schema. Return repository/file/line evidence and classify VERIFIED/DISPUTED/WITHHELD. Do not implement scraping circumventions or manufacture results.'

**DeepSeek (quant/methodology auditor):** 'Review the current cwt_unified modules and tests. Identify precise leakage, calendar/session alignment, overlapping-horizon statistical and execution flaws. Write failing pytest cases for each confirmed defect. Do not add deep learning, RL, or optimize on held-out data. Submit narrowly scoped patches plus an independent output comparison.'

**Codex (final gate only):** 'Merge only reviewed patches into the existing project, preserve module contracts, run tests/ruff/secret scan, validate real-data provenance, generate final metrics without synthetic leakage, build a reproducibility README and report. Reject incompatible improvements. No unauthorized X collection.'

## Primary references

- [CrowdWisdomTrading original assignment](https://docs.google.com/document/d/1OWrHpiqUSkqjncbRaQ3Z2Lb3EOBmFIYTCO0_BwGdhFw/edit)
- [Assignment historical dataset index](https://docs.google.com/document/d/1w-Y86OjkiOjlIIth0VgTAohql9zcGi3uoDNYTaTsZuw/edit)
- [X Terms of Service (effective 2026-10-09)](https://x.com/en/tos)
- [Apidojo Actor pricing](https://apidojo.io/pricing/)
- [Official Exa SDK](https://github.com/exa-labs/exa-py)
- [CardiffNLP current Twitter RoBERTa model card](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest)
- Public GitHub repository links in individual audit rows

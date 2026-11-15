# CrowdWisdomTrading Quant Project: Independent Adversarial Audit and Merge Plan

**Audit date:** 15 November 2026 (IST)  
**Disposition:** Research-only, pre-submission; no verified X-based prediction skill  
**Candidates deliberately anonymized to reduce authorship bias:**
- **Candidate A:** `CWT_Quant_Complete_Package.zip`, a complete Python source tree with reports and 15 tests.
- **Candidate B:** `Pasted text(20261115-101924).txt`, an inline multi-file Python proposal using Apify, Tavily, FinBERT, HistGradientBoosting, and purgedcv.
- **Additional Grok proposals:** Not among the uploaded source files. No final three/four-way judgment until the actual code is provided.

## 1. Executive judgment

**Choose Candidate A as a temporary foundation, not as an approved solution.** Its code actually exists, its 15 local tests passed independently, and it has sounder horizon notation and model-comparison structure. Candidate B contributes optional ideas for a licensed X connector, batched FinBERT inference, plots, and statistical diagnostics, but **its pasted code is not runnable as supplied** and its time alignment can invalidate an apparent backtest.

Neither candidate currently meets the critical requirement of a **historical 180-calendar-day X corpus with credible post timestamps, measurable sentiment coverage, and point-in-time engagement snapshots**. StockTwits and the current CrowdWisdom score are separate products, not X datasets. Calling them "X sentiment" would misrepresent the project.

## 2. Audit method and what was actually executed

- Inspected ZIP contents: 95 archive entries, including code, tests, five ticker reports and output CSVs.
- Ran the original ZIP's tests with `PYTHONPATH=src python -m pytest -q tests`: **15 passed**.
- Independently parsed each ticker's saved daily sentiment and paired prediction files.
- Reproduced a forward-contamination case: Saturday 14 Nov 2026 noon post was assigned to Friday 13 Nov 2026 closing session by Candidate A, with sentiment score +1.0 despite an invalid influence flag.
- Patched a **separate candidate copy**, adding five regression tests, and ran its test suite: **20 passed**; synthetic CLI end-to-end run also completed.
- No network-dependent real-data run was executed in this audit environment: `yfinance` and `crowdwisdomtrading` are not installed here and external network ingestion is not available. Original real-data CSVs are supplied artifacts, **not independently source-verified data**.
- Candidate B could not be executed as a repository because it consists of pasted file fragments, not an unpackable code tree. Findings below are static analysis, not an invented test result.

## 3. Candidate A: important findings

| ID | Status | Severity | Code/evidence | Required action |
|---|---|---|---|---|
| A-01 | VERIFIED defect | BLOCKER | `src/cwt_quant/features.py` lines 103–116 in original ZIP clip later session posts into the final price session | Exclude or hold for a future decision, never backdate |
| A-02 | VERIFIED defect | BLOCKER | `src/cwt_quant/data.py` `_map_stocktwits_to_posts`: unknown followers are set to `5_000`, and today's `likes` are timestamped `engagement_asof=created` | Unknown as unknown; separate publication, retrieval and engagement snapshot timestamps |
| A-03 | VERIFIED defect | HIGH | `_map_news_to_posts` invents `50_000` followers and marks engagement as of publication; CrowdWisdom daily score is injected as a fictitious high-weight post | Keep each source as a distinct feature with provenance and availability time |
| A-04 | VERIFIED | BLOCKER | Every original saved ticker has exactly **one** session in `daily_sentiment.csv`; price-only and price+sentiment `y_hat` arrays match exactly for all five tickers | WITHHOLD all sentiment-uplift claims; establish historical corpus |
| A-05 | VERIFIED limitation | HIGH | Influence gate uses total post count and sessions with posts, not count/sessions with **verified as-of engagement** | Gate on verified source coverage and snapshot age; reject proxy weights |
| A-06 | VERIFIED limitation | MEDIUM | Price source hash falls back to `"yfinance"` in all five supplied manifests, with `Price DataFrame lacks source_hash` warning | Persist immutable raw input files, content hashes and feed metadata |
| A-07 | VERIFIED limitation | HIGH | `calendar.py` contains manually maintained holiday and early-close schedules; test scope is narrow | Integrate an audited market-calendar library and compare against exchange schedule |
| A-08 | VERIFIED limitation | HIGH | The original report's ~530 rows/model sum overlapping horizons over a small sample; one 180-day window is insufficient for generalized alpha | Report per horizon and non-overlapping trial counts, uncertainty and minimum sample gate |
| A-09 | WITHHELD | HIGH | Real adjusted OHLC from saved outputs not cross-checked against primary provider/exchange; no live repeat | Validate splits, dividends, provider timestamp, ticker mapping and time zone |
| A-10 | VERIFIED limitation | HIGH | No actual X historical connector or historical X corpus in ZIP | Add legally permitted provider adapter, archive and strict source-specific ablations |
| A-11 | VERIFIED scope | MEDIUM | Forward predictions exist, but production monitoring, forecast ledger and replay are absent | Append-only forecast snapshots; live monitoring and realized-outcome joins |
| A-12 | VERIFIED defect | HIGH | `connectors/prices.py` subtracts `history_calendar_days + 40`; the five purported 180-day panels run 9 Apr–13 Nov 2026, **219 calendar days** inclusive | Freeze the exact 180-day evaluation window; keep separate documented warm-up if required |

### Saved output cross-check

| Ticker | Price sessions saved | Saved sentiment sessions | Price-only predictions | Price+sentiment predictions | Numerical equality |
|---|---:|---:|---:|---:|---|
| TSLA | 153 | 1 | 530 | 530 | Identical |
| AAPL | 153 | 1 | 530 | 530 | Identical |
| NVDA | 153 | 1 | 530 | 530 | Identical |
| MSFT | 153 | 1 | 530 | 530 | Identical |
| AMZN | 153 | 1 | 530 | 530 | Identical |

Original panels actually span **9 April through 13 November 2026 (219 calendar days)**, contradicting the stated 180-calendar-day scope. Counts derived from the supplied archived CSVs, not an independent provider replay. It would be false to interpret **530 overlapping horizon observations** as 530 independent trading opportunities.

## 4. Candidate B: important findings

| ID | Status | Severity | Code/evidence | Required action |
|---|---|---|---|---|
| B-01 | VERIFIED static defect | BLOCKER | `build_features()` keeps price index and never creates `timestamp_utc`; `walk_forward()` requests `df["timestamp_utc"]`, and `run_audit()` also uses it | Normalize a single timestamp index/column contract |
| B-02 | VERIFIED static defect | BLOCKER | `strategy_returns()` multiplies current signal by `preds["actual_ret"]`; that column is `ret_1` from the **past**, not actual forward open-to-close trade return | Build executable trading ledger and use strictly future realized returns |
| B-03 | VERIFIED static defect | HIGH | `Config` uses `target_k[t] = C[t+k+1]/C[t]-1` for k=0..5, actually producing t+1..t+6, not an unambiguous t+0..t+5 specification | Freeze horizon definitions in trading **sessions**, with tests |
| B-04 | VERIFIED static defect | HIGH | `eval_times = pred_times + 6 calendar days`; labels span up to six **trading** sessions | Use market-calendar-derived label end timestamps |
| B-05 | VERIFIED static defect | BLOCKER | Tavily historical fallback stamps each article with a loop's queried day `e`, not the article's own publish timestamp | Use verified article publish timestamp; keep source separate from X |
| B-06 | VERIFIED static defect | HIGH | `df.get("verified", False).astype(int)` can raise when `verified` is missing (default scalar bool) | Enforce schema adapter validation and typed defaults |
| B-07 | VERIFIED static concern | HIGH | All likes/retweets/views are treated as available on tweet publication date, despite being scraped later | Never use current engagement for past-close prediction; preserve snapshots |
| B-08 | VERIFIED scope | HIGH | A 180-day day-by-day Tavily query is expensive in requests and not proof of 180-day complete news coverage | Source-specific coverage audit and provider history limits |
| B-09 | VERIFIED scope | MEDIUM | Gradient boosting over ~120 observations and multiple horizons is unnecessarily expressive relative to available data | Baseline Ridge first; advanced models only if pre-registered tests support them |
| B-10 | VERIFIED static concern | HIGH | DSR/DM, return/cost and significance claims rely on incorrectly aligned trading results and potentially misused APIs | Rebuild evaluation from execution events, then test metric implementations independently |
| B-11 | WITHHELD | HIGH | The pasted `audit_all.csv` numbers are described as *expected output shape*, not actual executed results | Do not repeat them as observed model performance |

**Potentially reusable from B:** Apify connector concept (validate exact actor schema and legality), FinBERT batched scorer as an optional licensed module, chart types, serious out-of-sample diagnostics. **Do not copy B's current backtesting or trading-metrics implementation.**

## 5. Recommended combined architecture

```
LICENSED X / approved social / news / price source
  -> [Source-specific ingestors; idempotency, rate limits, typed schema]
  -> [Immutable raw store + source_id + fetched_at + content hash]
  -> [Event normalization]
       created_at | published_at | observed_at | engagement_asof
       post_id | author_id | ticker mapping | channel | edits | raw text
  -> [Trading session map]
       exchange holidays | early close | publication vs origin cutoff
  -> [Feature store / session-level as-of joins]
       text sentiment | volume | reply stance | attention | novelty
       missingness | verified point-in-time reach | crowd divergence
  -> [Research models]
       no-change -> price-only Ridge -> price+X Ridge -> influence ablation
       optional text embedding / non-linear models after data/skill gates
  -> [Leakage-proof walk-forward per horizon]
  -> [Forecast ledger + feature snapshot fingerprint + uncertainty]
  -> [Scorecards: calibration / RMSE / directional / lift / coverage]
  -> [Paper-only strategy diagnostic with next-open fills and costs]
  -> [CLI + evidence report + optional dashboard]
```

**Invariants:**
1. `origin` is a close timestamp, not a publication date or API-fetch time. Origin `t`, horizon `h`, target `log(C[t+h]/C[t])`; h=1..5 explicitly means **next 1–5 trading sessions**. If the assessment requires `n+0`, define *its own economic interval* and avoid a silent one-day shift.
2. At a decision cutoff, every **feature value** must have been observable by then. Text timestamps can be historical publication timestamps where provider provenance supports them; engagement counts need actual snapshot `as_of` times. An API fetch today is not itself a historical engagement snapshot.
3. The forecasting model must not synthesize tweets from aggregated sentiment services or invent account followers for missing records. Each source is a separate feature block and clearly labeled.
4. Session calendars and raw vs adjusted prices must be stable, source checked and unit tested. Distinguish return prediction from price-level forecast (`forecast_close=C_t exp(y_hat)`).
5. Always train base models on matched origin dates. If sentiment historical coverage is zero, **withhold** the price+sentiment comparison rather than calling it a meaningful sentiment test.
6. Do not mix ASTRA's technical outputs with this project's independent conclusions. If ASTRA technicals are evaluated, add them as a separate predeclared feature ablation after the core model is validated.

## 6. Influence and comments model (experimental only)

The suggested celebrity +0.4, comment +0.4 scheme should **not** be treated as a predictive law. No observed dataset validates those coefficients. Use a bounded attention measure, not an intercept that gives popular authors sentiment they did not express:

- Base signed sentiment `s_text ∈ [-1,1]` from pre-specified NLP or lexicon, with neutral retained as 0.
- Source credibility/reach feature `r = min(log1p(followers_at_t)/log1p(F_cap),1)` only where `followers_at_t` has genuine as-of evidence.
- Engagement feature `e = min(log1p(likes_t+2·reposts_t+comments_t)/log1p(E_cap),1)`, observed at origin or absent.
- Comment stance/reply distribution with enough independently timestamped replies: supportive, opposed, neutral, bot/duplicate-filtered. Do **not** infer from today's replies for old decisions.
- A candidate experimental score `signed_pressure = Σ(s_text × bounded_weight) / Σ(bounded_weight)` and disagreement/volume separately; validate incrementally and tune coefficients **only inside training windows**, never after reviewing test performance.
- Handle Tesla-related posts that mention SpaceX, celebrities and brands with an explicit **entity relevance** model; TSLA is not an economic proxy for SpaceX equity.
- Per-author frequency caps, verified source labels, duplicate/repost de-amplification, bot suspicion and drift tests.

## 7. Recommended integration order for Codex / Antigravity

**P0: Data truth and schema (must pass first).** Correct event timestamp semantics, split price and social provenance, reject post backdating, correct CWT daily-score usage, add schema and no-coverage tests. Freeze CLI/config and normalizing model dimensions.

**P1: Real X acquisition.** Add X retrieval only through a permitted, actually functioning provider. Verify 180-day corpus coverage by ticker/day, IDs, dates, spend and provider TOS. If not obtained, explicitly report X component WITHHELD rather than quietly substituting news or StockTwits.

**P2: Baselines and ablation.** Run fixed holdout horizons 1..5, zero/naive, price-only, price+X, price+X+influence, same origins, leakage-safe train data, immutable logs. Baseline confidence bands and source-coverage gates.

**P3: Evaluation and research report.** Evaluate MAE/RMSE vs naive, directional hit rate with class balance and non-zero-call fraction, calibrated intervals, paired loss differentials, overlapping-label dependence, paper-only costed strategy diagnostic.

**P4: User-facing report.** CLI, deterministic reproducibility, timestamped forecast ledger, optional browser UI. No auto-execution of financial orders and no returns promises.

**P5: Controlled publication.** Make a separate repository (`cwt-quant-research` is a suggested name), commit code/docs/tests, publish only example/synthetic fixtures and permitted derived metrics. Never push API keys, raw CWT data or source material with redistribution restrictions. Protect main and open a draft PR; merge only when verification is green.

## 8. Acceptance gates

| Gate | Pass condition | Current standing |
|---|---|---|
| Source evidence | Valid actual licensed X corpus with timestamps and coverage report | WITHHELD |
| Reproducible code | Clean offline install and deterministic tests | Candidate A locally passes 15; hardened candidate 20; network install WITHHELD |
| Time integrity | No post/label after origin cutoff enters features/training | Original A REJECTED; targeted hardened corrections verified locally |
| Data provenance | All external content source IDs, hashes, publication and observation times | INCOMPLETE |
| Evaluation | Identical test origins, true 1..5 session horizons, matched baselines | Partial baseline evidence only |
| Model value | Sentiment beats price-only consistently on held-out data | WITHHELD: original all five equal |
| Execution | Price bars, strategy returns and cost assumptions independently reconciled | WITHHELD |
| Portfolio/CV | Research-focused, truthful description and reproducible code | Draft-capable, subject to final provenance |

## 9. Verification resources

- PurgedCV open-source, MIT, available as `purgedcv`, with documented `WalkForwardSplit`: https://github.com/eslazarev/purged-cross-validation
- ProsusAI/FinBERT model license **CC BY-NC-SA-4.0**, not generally commercial: https://huggingface.co/ProsusAI/finbert
- NewsAPI Developer free: limited to **one month historical search**, 24-hour article delay: https://newsapi.org/pricing
- CrowdWisdomTrading PyPI/API: code MIT; API data terms restrict redistribution, including raw/derived data: https://pypi.org/project/crowdwisdomtrading/
- Apify actor schema/price must be validated at deployment. A posted code snippet is not proof of 180-day access.

## 10. GitHub decision

The linked GitHub account currently exposes `astra-quants`, `astra-financial-platform`, `internship`, etc., but no explicitly named dedicated CWT repository. The available connector can write to **existing** repositories but cannot create a new one. To avoid contaminating ASTRA with an independently experimental assignment, this audit **did not write to existing GitHub repositories**. The hardened candidate ZIP attached alongside this audit is a prepared staging artifact, not a deployed public repo. After the remaining Grok files are inspected, compare them against these P0 gates before choosing any extra module or making a final pull request.

**Bottom line:** verified code execution is valuable; claiming a validated X-sentiment edge without a point-in-time X dataset would be a scientific and reputational failure. The priority is data integrity, not another model family.

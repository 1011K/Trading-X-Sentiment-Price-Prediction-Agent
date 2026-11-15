# CWT Quant: four-role adversarial audit and unified method
Prepared 15 November 2026, IST. Status: **EXPERIMENTAL / PRE-CODEX**. Assessment target deadline reported for 17 November 2026; independently confirm submission time.

## 0. Evidence boundaries
- **DIRECTLY REVIEWED:** 14/15 November earlier CWT Python ZIP archives (`CWT_Quant_Audited_Starter_15_Nov_2026.zip`, `CWT_X_Sentiment_Quant_Assignment_PROVISIONAL.zip`) and their source/test files. The two prior ZIPs contain the same 274-line `pipeline.py`, 97-line `connectors.py`, 62-line `cli.py`, and six baseline tests.
- **IN CONVERSATION / PARTIAL:** One AAPL hourly revised `Config` excerpt (`ticker=AAPL`, `bar_freq=1h`, `history_days=180`), and summary of a separate BTC-USD daily v2 proposal with SQLite, VADER/FinBERT, LightGBM and walk-forward. The complete code from those two rival proposals and confirmed Grok/DeepSeek authorship are **NOT AVAILABLE** in this evidence. Do not attribute defects to a named model without its actual source.
- **NEW IMPLEMENTATION:** This reference package is independent, Python-only, no network/creds, tested on synthetic fixtures. No real data, genuine alpha, model profitability, 180-day X coverage, or live connector is verified.

## 1. Source/Data Auditor

| Register | Earlier approach / risk | Disposition | Proposed gate |
|---|---|---|---|
| D01 | 180-day AAPL 1-hour from Yahoo Finance | REJECTED as default | Use daily 1d, since Yahoo intraday beyond 60 days is not supported. |
| D02 | BTC-USD with 16:00 NYSE session logic | REJECTED | AAPL/XNYS US-equity target. BTC needs 24/7 calendar and different trading cutoffs. |
| D03 | Historical engagement numbers queried today | REJECTED for historical predictive features | Separate engagement `asof` snapshot; otherwise disable influence variant. |
| D04 | Tweets assigned to fixed 16:00 ET | REPLACED | Use XNYS open/close schedule, DST, closures and early close. |
| D05 | Missing price sessions silently skipped | REJECTED | Fail fast and audit missing sessions; investigate genuine halt or data outage separately. |
| D06 | Tweets about unrelated meanings of a ticker | PARTIAL MITIGATION | Cashtag-only initial gate, manually inspect precision/recall; log coverage loss. |
| D07 | Missing explicit post identity | PARTIAL | Dedup using `post_id` where possible; hash fallback is fixture support only. |
| D08 | Provider/source rights, timestamps, adjustment policy | WITHHELD | Preserve raw input hashes, retrieval timestamps, legitimate access evidence, price-adjustment & corporate-action audit. |
| D09 | Current Tavily/Exa news mixed into historical prices | REJECTED | News is current narrative context only; never a historical ML feature. |
| D10 | Historical X post edits/deletes | OPEN | `created_at` alone does not prove point-in-time text integrity. Label retrospective observation. |

## 2. Methodology Auditor

**Fixed scope:** one US stock, daily exchange sessions, 180 *calendar* days. For each close-of-session origin t, `n+0 = C[t]` observed. Direct h-session target is `y[t,h] = log(C[t+h]/C[t])`, h=1..5. Forecast `C_hat[t+h] = C[t] * exp(y_hat[t,h])`. If corporate actions or normalization make adjusted close differ from tradeable close, report adjusted forecast units explicitly and prevent use in trading metrics.

**Post availability:** A post is mapped to the *first strictly later actual exchange closing timestamp*. At the exact close, or after close, it belongs to the next session. Different providers may timestamp content creation vs indexing; the latter is not interchangeable. Both fields and latency should be independently logged.

**Text and replies:** Default text sentiment is a transparent, weak lexical baseline [-1,1], not accurate stance or sarcasm analysis. Precomputed signed `sentiment` and `reply_sentiment` are permitted only when their own provenance/model version and as-of validity are documented. With contemporaneously observed, asset-targeted replies, `s_conversation = 0.6*s_post + 0.4*s_reply`. Without valid reply evidence, the full score equals the post score. An engagement *count* does not reveal whether replies agree or disagree.

**Experimental influence hypothesis (not fitted):**

- `reach = min(1, log(1+followers)/log(1+1,000,000))`.
- `engagement = min(1, log(1+likes+2*reposts+comments)/log(1+10,000))`.
- `weight = min(1.5, 1 + 0.3*reach + 0.2*engagement)`.
- `daily_mean = mean(s_conversation)`.
- `daily_influence = sum(weight*s_conversation) / sum(weight)`.
- `influence_pressure = tanh(sum(weight*s_conversation)/(3*sqrt(post_count)))`.

The coefficients and caps are **chosen research hypotheses**, not fitted or backed by an empirical effect estimate. They preserve score polarity and avoid turning celebrity status into a positive intercept. A celebrity's name is not a sentiment class. A highly viewed neutral post remains neutral. A single post's weighted average stays its sentiment; the pressure feature may change, and therefore requires separate out-of-sample verification. Likes, followers and comments are only eligible when an actual timestamped historical snapshot existed no later than the forecast-origin close. Avoid ex-post percentiles and globally fitted scalers.

**Model experiment fixed before seeing results:** no-change, historical-price-only Ridge, price + lexical/scored sentiment Ridge; point-in-time influence Ridge only if full snapshot coverage, at least 50 posts across 20 sessions, and separately approved. Same horizon, as-of origin and origin-close units for all variants. Train-only `StandardScaler`, fixed alpha=10. Never claim the best variant from testing multiple settings on the final period.

**Leakage guard:** a train origin i is permitted at test origin t for horizon h only if `i + h <= t` because the label at i+h must already be known. No random split. No current news, late-retrieved replies, retrospective engagement counts, or future full-sample normalizations.

## 3. Sector / Quant Specialist

- Fewer than ~125 daily sessions can fall in 180 calendar days, so five-day targets are overlapping and uncertainty is high. An observed positive backtest after multiple experiments may be selection noise.
- Output MAE, RMSE, model-vs-naive skill, direction accuracy, held-out origin counts, and scatter or rolling error diagnostics per horizon. The no-change model's zero directional predictions make its direction accuracy an unsuitable comparator; evaluate error skill for naive, plus a separate pre-registered sign baseline if needed.
- Forecasting close(t+1) at close(t) is distinct from **executing** a trade. The prototype uses next session open-to-close long-or-cash as an **idealized** diagnostic, with declared round-trip costs. Overnight gaps, realistic spreads, broker fees, taxes, sizing, and capacity remain unresolved.
- Sharpe, Sortino, and Max Drawdown only refer to this constrained diagnostic; no trading advice or proof of positive alpha follows.
- Price-only Ridge is the main sanity benchmark. With merely 180 days, do not default to LSTM, RL, LightGBM, enormous VADER/FinBERT ensembles, embeddings, or Bayesian celebrity factors. Complexity is a liability without sample size.
- If using ProsusAI FinBERT, model weights are CC BY-NC-SA-4.0; do not assume commercial authorization simply because repo training code is Apache-2.0. Alternative sentiment solutions require separate license checks and calibration.

## 4. Red Team: mandatory adversarial cases

| Test | Expected |
|---|---|
| After NYSE early close but before 16:00 ET | Move to next session, not same day |
| Post timestamp equals a close | Move to following session |
| Engagement snapshot arrives one minute after origin close | No influence feature for that origin |
| Current total likes increases retrospectively | Previously scored forecasts unchanged |
| Neutral Elon Musk post | No positive score created by reach alone |
| $AAPL and unrelated 'apple fruit' | Only exact cashtag accepted in prototype |
| Duplicate post ID / repeated same author | Deduplicate / cap repeated known author per session |
| Unknown exchange holiday or missing price | Fail rather than pretending adjacent bars are consecutive sessions |
| Post written at origin t+1 | No appearance in features for t |
| Non-available price label t+h | Excluded from training/evaluation until available |
| Change future closes | Earlier date features/predictions unaffected |
| Missing next-open data | Strategy statistics WITHHELD |
| Scarce / zero post days | Zero signal plus separate no-post flag |
| Live API inaccessible | Source status WITHHELD; never substitute synthetic prices as real |
| Future dividend/split | Prices, returns, trading fills audited and consistent, else WITHHELD |

## 5. Reconciliation: AAPL hourly vs BTC daily vs prior scaffold

| Design source | Reusable | Weakness / fix |
|---|---|---|
| AAPL hourly excerpt (unverified full code) | Equity ticker and explicit UTC | Hourly 180-day Yahoo source infeasible; explicit hourly-to-daily target bridge absent |
| BTC-USD daily proposal (unverified full code) | Modular separation, deterministic baseline ideas | Crypto is not a stock; XNYS time alignment invalid; RL and LightGBM overkill for 180-day daily training sample |
| 14/15 Nov prior ChatGPT ZIP **directly inspected** | Mature CLI, CSV ingestion, basic sentiment, horizons, naive benchmark, reproducibility fixtures | 6 tests insufficient; engagement leakage, early-close bug, loose ticker filtering, non-executable same-close fills, limited provenance |
| **This unified reference** | Explicit time gates, relevant X data, optional influence, three fair baseline variants, next-open diagnostic, early-close tests, source hashes | Still not submission ready until real corpus, licensed provider, adjusted prices, external score provenance, rigorous report, and genuine OOS run verified |

## 6. Priority before actual Codex implementation

**P0 (required):** normalize legitimate 180-calendar-day X corpus + source manifests; verify one exchange-traded stock and adjusted/raw OHLC policy; score with transparent baseline; run leakage-safe no-change/price-only/price+sentiment; render genuine metrics and chart; review news separately; submit honest report.

**P1 (eligible only after P0):** capture historical engagement snapshots; classify asset-specific replies/stance; test capped influence as an ablation; compare improvement on identical origins. Do not claim effect until supported.

**P2 (defer):** LightGBM, transformer ensembles, RL, continuously learned influence coefficients, live signals, trading integrations, elaborate UI, AI autonomous agents. The short assessment is not a hedge fund research platform.

## 7. Acceptance / evidence register

- **VERIFIED locally:** synthetic CLI run and unit tests in this archive (see `LOCAL_VALIDATION.txt`).
- **EXPERIMENTAL:** fixed-weight influence formula and open-to-close trading diagnostic.
- **WITHHELD:** actual Grok/DeepSeek source audit (their full responses absent), live X/posts, actual 2026 prices/source licenses, 180-day genuine data coverage, real forecasting skill, commercial use permissions, and repository publication.
- **REJECTED:** claim of validated celebrity impact; future likes used historically; 180-day Yahoo hourly; BTC on XNYS calendar; same-close trading entry; AI model voting to select empirically best forecast.

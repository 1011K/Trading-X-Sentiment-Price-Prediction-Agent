# Final AAPL implementation and submission audit

Started from PR #1 commit `59eea79c8c08773f9a9b5048a1e952d0ffe45f73`. The submission remains partial. [No-cost source review](DATA_SOURCES_ZERO_COST.md) · [Replay commands](SUBMISSION_REPLAY.md)

| Requirement | Status | Evidence |
| --- | --- | --- |
| Real, authorized 180-day AAPL X data | BLOCKED | 0 verified posts, 0 covered dates and 0 forecast-eligible posts. No valid historical observation or engagement snapshots. A dated public archive check found no verified target sample. |
| AAPL price inputs and exchange sessions | VERIFIED | 126 evaluation and 68 warm-up sessions. Verified all 194 dates from the saved vendor snapshot against the US exchange schedule and checked AAPL origin-close and corporate-action records. |
| n+0 and n+1 through n+5 | VERIFIED | Price-only benchmark. 126 paired opening nowcasts, and 121 matched held-out origins per post-close horizon. Opening forecasts use the observed opening quote and earlier prices. |
| Look-ahead protection and baseline checks | VERIFIED | Reject unordered or repeated origins before training. Independent replay recalculated all 1,210 post-close outcomes and 252 n+0 outcomes from underlying prices. |
| Tavily live articles and timestamps | VERIFIED | Authenticated free-plan usage check and one basic search on 16 November 2026. Three dated results were stored in a single capture. Timestamps came from the search provider. |
| One-page market outlook and news isolation | PARTIAL | Current Tavily news is in the one-page outlook. Both model feature sets exclude news. The X sentiment section remains withheld. |
| Relevance and lexical evaluation | VERIFIED | AAPL issuer phrases and ticker-in-context preserve genuine keyword-only hits without setting the cashtag flag. 2,387 held-out publisher-labelled texts were evaluated. |
| Influence and celebrity weighting | EXPERIMENTAL | Neither enters the empirical replay. Archived retrieval-time counts remain unverified for historical use. |
| Trading ledger accounting | VERIFIED | 242 model-by-session rows independently reconciled. Risk withholds on missing or invalid fills, with the dated issue carried to logs and report. |
| Trading performance | EXPERIMENTAL | Intraday hypothetical execution with 10 bps round-trip cost. Positive close-to-close forecasts are signals for a different holding interval. On 25 of 121 opportunities, realized close-to-close and open-to-close direction differed. |
| Frozen replay, chart, and SQLite | VERIFIED | Saved AAPL snapshot, deterministic replay outputs, coverage JSON, nowcast/forecast ledgers, and a four-panel research graphic that marks unavailable X panels. SQLite integrity and foreign keys checked. |

## Frozen sources and independence

AAPL source SHA-256 is `1b6c3babe4d176320a4b4f4c9e6203da045a243061d2d347cf2758636eaab1ff`. Evaluation window was 18 May–13 November 2026. The saved price feed was retrieved on 15 November 2026. Vendor revision history and original publication timestamps were unavailable. [Prior price evidence and fingerprints at the pre-cleanup commit](https://github.com/1011K/Trading-X-Sentiment-Price-Prediction-Agent/blob/24b1ab8bcdc69d5782e270b01752a465592a60aa/docs/SUBMISSION_EVIDENCE.md) · [Nasdaq holiday schedule](https://www.nasdaq.com/market-activity/stock-market-holiday-schedule) · [Apple dividend history](https://investor.apple.com/dividend-history/)

At n+0 the flat-open benchmark had lower RMSE. Ridge improved n+1 RMSE on this sample and underperformed at n+2 through n+5. Intraday P&L uses next-session open and close, not realized close-to-close labels. The public branch contains methodology and aggregate evidence. Raw quotes, individual forecast rows, news payloads and posts are kept local.

## Verified issuer context

- 13 November 2026. Apple announced that HomeView went on sale in selected regions. [Apple Newsroom release](https://www.apple.com/newsroom/2026/11/apple-homeview-available-today/)
- 2 November 2026. Apple reported fiscal fourth-quarter revenue of $114.5 billion, up 12% year over year, and declared a $0.27 dividend per share. [Apple earnings release](https://www.apple.com/newsroom/2026/11/apple-reports-fourth-quarter-results/)

These dates are the issuer's published release dates. The articles are context for the outlook and have no historical feature exposure or sentiment label.

## Labelled sentiment benchmark

Revision `ccbe24de388e287beb92dd393a335c376b350ac3` of the publisher's MIT-labelled dataset. Used its 9,543 training and 2,388 validation file rows. Six repeated training records and one validation record overlapping training were excluded after case/whitespace normalization. The majority classifier selected neutral from training only. [Dataset card](https://huggingface.co/datasets/zeroshot/twitter-financial-news-sentiment/blob/ccbe24de388e287beb92dd393a335c376b350ac3/README.md) · [Pinned train CSV](https://huggingface.co/datasets/zeroshot/twitter-financial-news-sentiment/resolve/ccbe24de388e287beb92dd393a335c376b350ac3/sent_train.csv) · [Pinned validation CSV](https://huggingface.co/datasets/zeroshot/twitter-financial-news-sentiment/resolve/ccbe24de388e287beb92dd393a335c376b350ac3/sent_valid.csv)

| Model | Held-out n | Accuracy | Macro F1 |
| --- | ---: | ---: | ---: |
| Training majority, neutral | 2,387 | 65.61% | 0.2641 |
| Existing lexical scorer | 2,387 | 66.02% | 0.3961 |

Bearish recall was 7.80% and bullish recall was 18.74%. The lexicon was unchanged and the metric calculation independently cross-checked. These figures establish a limited text-classification diagnostic.

## Independent fit reconciliation

A separate standard-library solver reconstructed 605 held-out Ridge forecasts, 126 Ridge opening nowcasts and the five latest Ridge forecasts directly from the frozen price snapshot. Maximum absolute prediction difference was `2.78e-17`. The earliest post-close evaluation origin had 68 available n+1 labels and 64 available n+5 labels. The earliest opening nowcast had 62 prior-session labels. Both post-close models contributed 605 candidate rows and retained all 605 matched rows.

The [AAPL archive query evidence](community-archive-query-audit.json) stores query timestamps, digests and counts without including post content or identifiers.

## Repository cleanup

The active tree retains the `cwt_quant` implementation, its connectors, the existing test suite and CI. The separate archived `cwt_unified` package had no imports, dependency entries or workflow references from the active project. Its separate suite passed 24 tests before removal. The standalone multi-audit script wrapped the active pipeline, whose dated ticker selection remains available through `cwt_quant.submission`.

The prototypes, their ZIPs, historical validation notes and handoff reports remain recoverable at the [previous PR head](https://github.com/1011K/Trading-X-Sentiment-Price-Prediction-Agent/tree/24b1ab8bcdc69d5782e270b01752a465592a60aa). The current audit preserves the eligibility, market-calendar and redistribution constraints.

## Final API check and frozen replay

On 16 November 2026, Apify returned HTTP 200 for the runs and datasets listings. Both were empty. No actor was launched. The current evidence is zero real X posts and zero covered days. An authorized historical corpus and credible cutoff-time evidence are still required, including separate snapshots for likes, reposts, views and followers. Exa is outside the active submission path.

Tavily authenticated and reported a free plan with available included credits. One basic search at 05:33 UTC returned three dated AAPL-related results. Its response digest is `39545256b4ffc20616711ec3e0a20d220230d910d6ea3812eae6e125ef17236f`. The articles are current context collected after the frozen forecast origin. Provider dates are not evidence that an article was available at a model cutoff.

A separate standard-library check confirmed the exact price input digest, all 194 source bars, 1,210 walk-forward target rows, 252 n+0 rows, and all 242 ledger rows. It recalculated MAE, RMSE, directional accuracy, round-trip charges, Sharpe, Sortino and drawdown. The final SQLite database passed integrity and foreign-key checks and contains one news capture with three articles and no X posts. The four-panel figure reads these replay records and keeps unobserved X series empty.

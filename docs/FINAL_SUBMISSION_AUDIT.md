# Final AAPL implementation and submission audit

Started from PR #1 commit `59eea79c8c08773f9a9b5048a1e952d0ffe45f73`. The submission remains partial. [No-cost source review](DATA_SOURCES_ZERO_COST.md) · [Replay commands](SUBMISSION_REPLAY.md)

| Requirement | Status | Evidence |
| --- | --- | --- |
| Real, authorized 180-day AAPL X data | BLOCKED | 0 verified posts, 0 covered dates and 0 forecast-eligible posts. No valid historical observation or engagement snapshots. A dated public archive check found no verified target sample. |
| AAPL price inputs and exchange sessions | VERIFIED | 126 evaluation and 68 warm-up sessions. Verified all 194 dates from the saved vendor snapshot against the US exchange schedule and checked AAPL origin-close and corporate-action records. |
| n+0 and n+1 through n+5 | VERIFIED | Price-only benchmark. 126 paired opening nowcasts, and 121 matched held-out origins per post-close horizon. Opening forecasts use the observed opening quote and earlier prices. |
| Look-ahead protection and baseline checks | VERIFIED | Reject unordered or repeated origins before training. Independent replay recalculated all 1,210 post-close outcomes and 252 n+0 outcomes from underlying prices. |
| Tavily live articles and timestamps | BLOCKED | The connector is tested with fixtures. No local key was available for the frozen empirical run. |
| One-page market outlook and news isolation | PARTIAL | Manually verified issuer-release context is listed below. The replay contains zero Tavily captures and excludes news from both model feature sets. |
| Relevance and lexical evaluation | VERIFIED | AAPL issuer phrases and ticker-in-context preserve genuine keyword-only hits without setting the cashtag flag. 2,387 held-out publisher-labelled texts were evaluated. |
| Influence and celebrity weighting | EXPERIMENTAL | Neither enters the empirical replay. Archived retrieval-time counts remain unverified for historical use. |
| Trading ledger accounting | VERIFIED | 242 model-by-session rows independently reconciled. Risk withholds on missing or invalid fills, with the dated issue carried to logs and report. |
| Trading performance | EXPERIMENTAL | Intraday hypothetical execution with 10 bps round-trip cost. Positive close-to-close forecasts are signals for a different holding interval. On 25 of 121 opportunities, realized close-to-close and open-to-close direction differed. |
| Frozen replay, chart, and SQLite | VERIFIED | Saved AAPL snapshot, deterministic replay outputs, coverage JSON, nowcast/forecast ledgers, and a chart that marks both sentiment series withheld. SQLite integrity and foreign keys checked. |

## Frozen sources and independence

AAPL source SHA-256 is `1b6c3babe4d176320a4b4f4c9e6203da045a243061d2d347cf2758636eaab1ff`. Evaluation window was 18 May–13 November 2026. The saved price feed was retrieved on 15 November 2026. Vendor revision history and original publication timestamps were unavailable. [Existing price evidence and fingerprints](SUBMISSION_EVIDENCE.md) · [Nasdaq holiday schedule](https://www.nasdaq.com/market-activity/stock-market-holiday-schedule) · [Apple dividend history](https://investor.apple.com/dividend-history/)

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

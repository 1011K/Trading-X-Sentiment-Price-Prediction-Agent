# Final AAPL implementation and submission audit

**Ready for partial submission.** This report describes retrospective price-only research. [Employer brief](https://docs.google.com/document/d/1OWrHpiqUSkqjncbRaQ3Z2Lb3EOBmFIYTCO0_BwGdhFw/edit) · [No-cost source review](DATA_SOURCES_ZERO_COST.md) · [Replay commands](SUBMISSION_REPLAY.md)

| Employer requirement | Status | Evidence and remaining work |
| --- | --- | --- |
| 180 days of AAPL prices | VERIFIED | Yahoo Finance OHLCV, 18 May to 13 November 2026. 126 evaluation and 68 warm-up sessions. Split-bearing or incomplete snapshots fail validation. |
| 180 days of X posts from ticker, cashtag and keyword searches | WITHHELD | Zero verified posts and zero covered dates. The historical source index does not establish a May to November 2026 AAPL archive. |
| X timestamps, text, likes, reposts, views and followers | PARTIAL | The authorized importer records available fields and aligns observation cutoffs to New York sessions. Forecast-time text and engagement or follower snapshots remain unavailable for the assessment. Fixture tests exercise the gates. |
| Apify actor and source provenance | PARTIAL | `apidojo/tweet-scraper` is the planner candidate. Import validates existing actor, run, build and dataset evidence. No actor ran and there is no empirical actor run ID. |
| Recent Tavily news | VERIFIED | A prior saved basic search returned three results after evaluation. The final presentation uses two independently checked Apple releases as context. All news stays outside model features. |
| Exa configuration and execution | NOT IMPLEMENTED | No Exa integration was configured or used for the assessment. |
| Time-based sentiment and price features | PARTIAL | Lagged price returns, volatility and opening-gap features run on real bars. Lexical scores and aligned activity execute on eligible test data. The empirical replay uses prices alone. |
| Database integration | VERIFIED | Local SQLite stores price bars, forecast and trade ledgers, and provenance. Authorized X exports and Tavily captures have separate tables. The assessment X table is empty. |
| n+0 to n+5 forecast | PARTIAL | Two price-only variants run at all six horizons. n+0 uses the 09:30 New York opening print and prior prices. Later horizons use the close. The X-assisted assessment remains withheld. |
| Walk-forward validation | VERIFIED | Expanding windows train on mature labels with train-only scaling. Comparison uses paired models on 126 opening and 121 post-close origins per horizon. |
| X sentiment versus price chart | PARTIAL | The four-panel chart explicitly marks unavailable X sentiment and activity. It charts observed prices and price-only forecasts. |
| One-page sentiment outlook | PARTIAL | The outlook includes the latest price forecasts and issuer context with separate publication and retrieval dates. Historical X sentiment remains withheld. |
| Sharpe, Sortino and maximum drawdown | VERIFIED | Retrospective Ridge execution diagnostic, 121 opportunities, 71 longs and 50 cash sessions. It models next-session open-to-close execution with a 10 bp round-trip charge and approximate fills. |
| GitHub submission and reproducibility | VERIFIED | PR #1 documents fresh and frozen modes. Fresh mode needs provider access. Exact frozen replay needs the original snapshot with the recorded digest. No coding agent, Tavily key or Apify token is required for the price-only workflow. |
| Tokens and actor IDs for reviewer reproduction | WITHHELD | No reusable tokens are included. There is no empirical actor run ID. A reviewer can provide their own authorized credentials for optional acquisition. |

## Price-only evaluation

| Horizon | Matched origins per model | Naive MAE | Ridge MAE | Naive RMSE | Ridge RMSE |
| --- | ---: | ---: | ---: | ---: | ---: |
| n+0 | 126 | 0.01083 | 0.01092 | 0.01425 | 0.01438 |
| n+1 | 121 | 0.01268 | 0.01267 | 0.01753 | 0.01746 |
| n+2 | 121 | 0.01756 | 0.01790 | 0.02476 | 0.02485 |
| n+3 | 121 | 0.02235 | 0.02232 | 0.03059 | 0.03077 |
| n+4 | 121 | 0.02567 | 0.02532 | 0.03457 | 0.03520 |
| n+5 | 121 | 0.02851 | 0.02821 | 0.03764 | 0.03894 |

Errors are in log-return units. The naive reference is the session open for n+0 and the origin close for n+1 to n+5. Close-to-close forecasts and open-to-close execution use different return intervals. Ridge diagnostic Sharpe was **2.30**, Sortino **3.81** and maximum drawdown **−12.74%**. Observed quote fills are approximations. The results cover one sample and live trading performance remains unvalidated.

Request a rights-cleared historical AAPL X export with documented cutoff-time observations. To test influence, request separately timestamped likes, reposts, views and follower snapshots.

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

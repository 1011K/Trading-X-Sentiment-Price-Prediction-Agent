# Final AAPL implementation and submission audit

**Ready for partial submission.** This report describes retrospective price-only research. [Employer brief](https://docs.google.com/document/d/1OWrHpiqUSkqjncbRaQ3Z2Lb3EOBmFIYTCO0_BwGdhFw/edit) · [No-cost source review](DATA_SOURCES_ZERO_COST.md) · [Replay commands](SUBMISSION_REPLAY.md)

| Employer requirement | Status | Evidence and remaining work |
| --- | --- | --- |
| 180 days of AAPL prices | VERIFIED | Yahoo Finance OHLCV, 18 May to 13 November 2026. 126 evaluation and 68 warm-up sessions. Split-bearing or incomplete snapshots fail validation. |
| 180 days of X posts from ticker, cashtag and keyword searches | WITHHELD | Zero verified posts and zero covered dates. The historical source index does not establish a May to November 2026 AAPL archive. |
| X timestamps, text, likes, reposts, views and followers | PARTIAL | The authorized importer records available fields and aligns observation cutoffs to New York sessions. Forecast-time text and engagement or follower snapshots remain unavailable for the assessment. Fixture tests exercise the gates. |
| Apify platform verification | VERIFIED | [Authentication and inventory](api-evidence/apify.json), [Hello World run and output](api-evidence/apify-demo.json), and [one-row demo dataset read](api-evidence/apify-demo-dataset.json) each have a live receipt. |
| Apify historical X acquisition | WITHHELD | `apidojo/tweet-scraper` is the planner candidate. The importer can verify an authorized run, build and dataset. No X actor ran and no historical X data was ingested. |
| Recent Tavily news | VERIFIED | A [live basic search](api-evidence/tavily.json) returned three usable AAPL articles after evaluation. The final presentation uses two independently checked Apple releases as context. All news stays outside model features. |
| Exa configuration and execution | NOT IMPLEMENTED | No Exa integration was configured or used for the assessment. |
| Time-based sentiment and price features | PARTIAL | Lagged price returns, volatility and opening-gap features run on real bars. Lexical scores and aligned activity execute on eligible test data. The empirical replay uses prices alone. |
| Database integration | VERIFIED | Local SQLite stores price bars, forecast and trade ledgers, and provenance. Authorized X exports and Tavily captures have separate tables. The assessment X table is empty. |
| n+0 to n+5 forecast | PARTIAL | Two price-only variants run at all six horizons. n+0 uses the 09:30 New York opening print and prior prices. Later horizons use the close. The X-assisted assessment remains withheld. |
| Walk-forward validation | VERIFIED | Expanding windows train on mature labels with train-only scaling. Comparison uses paired models on 126 opening and 121 post-close origins per horizon. |
| X sentiment versus price chart | PARTIAL | The four-panel chart explicitly marks unavailable X sentiment and activity. It charts observed prices and price-only forecasts. |
| One-page sentiment outlook | PARTIAL | The outlook includes the latest price forecasts and issuer context with separate publication and retrieval dates. Historical X sentiment remains withheld. |
| Sharpe, Sortino and maximum drawdown | VERIFIED | Retrospective Ridge execution diagnostic, 121 opportunities, 71 longs and 50 cash sessions. It models next-session open-to-close execution with a 10 bp round-trip charge and approximate fills. |
| GitHub submission and reproducibility | VERIFIED | PR #1 documents fresh and frozen modes. Fresh mode needs provider access. Exact frozen replay needs the original snapshot with the recorded digest. No coding agent, Tavily key or Apify token is required for the price-only workflow. |
| Credentials for reviewer reproduction | WITHHELD | Reviewers supply their own free keys using the [verification commands](../README.md#verify-the-free-tier-apis). The non-X demo run ID is published in its receipt. No historical X run ID exists. |

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

## Live API verification and frozen replay

On 16 November 2026 UTC, Apify account authentication and inventory requests returned HTTP 200. Both inventories were empty before the demo. The official `apify/hello-world` launch returned HTTP 201 and completed with status `SUCCEEDED`. Reading its key-value output and its dataset both returned HTTP 200. The dataset contained one generic demo record.

The later Tavily verification at 19:56 UTC returned HTTP 200 for quota and HTTP 200 for search, with three usable AAPL news results. Its receipt records counts and a response digest. The optional private capture at 05:33 UTC is a different response with digest `39545256b4ffc20616711ec3e0a20d220230d910d6ea3812eae6e125ef17236f`. Both were collected after the evaluation cutoff. The final presentation uses reviewed Apple releases, and all news stays outside model features.

A separate standard-library check confirmed the exact price input digest, all 194 source bars, 1,210 walk-forward target rows, 252 n+0 rows, and all 242 ledger rows. It recalculated MAE, RMSE, directional accuracy, round-trip charges, Sharpe, Sortino and drawdown. The earlier SQLite replay with the optional private Tavily capture passed integrity and foreign-key checks and stored three news articles and zero X posts. The four-panel figure keeps unobserved X series empty.

## Outstanding limitations

- Historical X evaluation is **WITHHELD**, with zero verified posts and zero covered dates. It needs a rights-cleared AAPL corpus with documented cutoff-time observations for 18 May to 13 November 2026. Influence tests also need separately timestamped likes, reposts, views and follower counts.
- Apify demo execution verifies the platform and a generic dataset read. Historical X acquisition, X-assisted forecast accuracy and sentiment alpha remain unverified. Exa was unused.
- Exact frozen replay requires the original price snapshot. The public checkout supports a fresh replay. Provider snapshots, article payloads and price-derived bundles stay local pending redistribution clearance.

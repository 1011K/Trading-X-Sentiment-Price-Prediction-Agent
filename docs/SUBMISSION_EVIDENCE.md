# AAPL submission evidence

**Status: partial research submission.** The price replay and model diagnostics ran on a saved provider snapshot. This submission has no observed X or Tavily coverage. It does not establish a sentiment edge or full assignment compliance.

| Evidence | Verified scope |
| --- | --- |
| Evaluation calendar | 18 May to 13 November 2026 inclusive, 180 calendar days |
| Market data | 126 AAPL sessions in evaluation and 68 earlier sessions for warm-up |
| X | 0 rows, 0 covered days, 0 rows eligible at a historical cutoff |
| Apify | Actor candidate `apidojo/tweet-scraper`. No authorized run ID, build ID, or dataset ID was supplied. No actor was launched |
| Tavily | 0 captures and articles in the empirical replay. Credentialed behavior was tested with mocks |
| n+0 | 126 opening-time nowcasts per model, with same-day closes used only for evaluation |
| n+1 through n+5 | 121 identical held-out origins per horizon for no-change and price Ridge |
| Trade ledger | 121 chronological fill opportunities per model. Ridge took 71 hypothetical long trades and held cash for 50 sessions |
| Costs | 10 basis points per long round trip, zero cost on cash sessions |

The opening-price baseline had lower n+0 RMSE than Ridge. For the post-close comparison, Ridge had lower n+1 RMSE and higher n+2 through n+5 RMSE. These are results for one retrospective sample. The trading ledger reconciled against saved source open and close prices, forecast signals, costs and compounded equity. No-change remained in cash, so its annualized risk ratios are undefined.

Use the [replay instructions](SUBMISSION_REPLAY.md) to generate the forecast tables, risk metrics, X coverage audit, chart, and one-page outlook from permitted inputs. The code and this report are public. Source quotes, individual predictions and fills, raw post text, news capture files, and databases remain local while redistribution rights are unverified. The input snapshot digest identifies the exact private bytes used in this evaluation.

- Input provider: Yahoo Finance via yfinance 1.8.0, retrieved 15 November 2026 at 15:24:36 UTC.
- Input SHA-256: `1b6c3babe4d176320a4b4f4c9e6203da045a243061d2d347cf2758636eaab1ff`.
- Reproduction environment: Python 3.12.15, NumPy 2.5.4, pandas 2.3.3, matplotlib 3.11.2.
- Tested acquisition and news fixtures exercise data handling. They do not substitute for an authorized archived X export or actual Tavily observations.

## License and credential review

The root repo has no general software license. The repair uses repository code and installed dependencies. No code from an external repository was copied into this change. Installed metadata identifies yfinance and Requests as Apache-2.0, pandas as BSD-3-Clause, pytest and CrowdWisdomTrading as MIT, and separate Matplotlib and NumPy license files. These software terms confer no right to republish vendor data.

Use an authorized X collection or licensed export. A successful actor run, public post URL, or active API key does not establish redistribution rights or historical observation. Tavily content and linked sources have separate terms. Keep API credentials in the local environment and share access through reviewer-owned accounts or an approved secret channel. [X terms](https://x.com/en/tos) · [Apify acceptable use](https://docs.apify.com/legal/acceptable-use-policy) · [Tavily terms](https://www.tavily.com/terms) · [yfinance license and data notice](https://github.com/ranaroussi/yfinance#readme)

## Replay fingerprints

| Local evidence file | SHA-256 |
| --- | --- |
| `open-nowcast.csv` | `c491cfd757a7c496c6f6ce3b858c4a5ddd5199279b058acd1743b21c55f92d83` |
| `post-close-forecasts.csv` | `db64f2586b88b3ff94ee5b58137cd6203e1b37ce27a904d81579b12b30bbe8fe` |
| `model_comparison.csv` | `fcf79cb38d3fb49c9553ec55a35b87075d5c2bc698c0a1ad462c72d1340f3cc4` |
| `trade_ledger.csv` | `225e2970ac87343e830ca945a545f511d12abc05b84416b4119f5e05f33bda0f` |
| `x-coverage.json` | `990473cac1025698f87f3fdd4cf4b6c966f7dbcc8afe4ccd9c5d5c8bdfff09d7` |
| `x-sentiment-series.csv` | `7745c6b2cbf8d99de66c216c26771e0c3302b745f7237e71561d6735df7da188` |

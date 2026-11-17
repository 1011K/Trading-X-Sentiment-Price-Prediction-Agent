# Reproduce the submission replay

This path uses the repository’s existing direct-horizon Ridge model, with an isolated 180-calendar-day evaluation window. Python 3.10 and 3.12 are supported. The exchange calendar covers 2024–2026. Use eligible USD-listed US equities or ETFs with a complete price history and a split-free input window. Symbols with a different exchange calendar, unsupported instrument type, or incomplete bars fail closed.

## API verification

Run the [reviewer-owned free-key commands](../README.md#verify-the-free-tier-apis) separately from the forecast replay. Apify authentication and inventory are read-only checks. The optional Hello World check launches an official non-X Actor, verifies its output, and supplies a dataset ID for a separate read. The live demo dataset contained one generic record. Tavily verifies free quota before one basic AAPL search. [Live receipts](api-evidence/) record statuses, timestamps, counts and digests. They contain no article bodies or replayable news capture. No historical X posts came from these checks.

## Offline tests

From the repository root in an activated virtual environment, run:

```sh
python -m pip install -r requirements-submission.txt
PYTHONPATH=src python -m pytest -q tests
```

The suite uses fixtures for provider calls and does not need credentials. The live receipts document the separate credentialed checks.

## Independent run from a clean checkout

From the root of the checked-out PR branch, activate a Python 3.12 virtual environment and run:

```sh
python -m pip install -r requirements-real.txt -r requirements-submission.txt
PYTHONPATH=src python scripts/build_submission.py fresh --end 2026-11-13 --out outputs_submission/aapl-fresh
(cd outputs_submission/aapl-fresh && shasum -a 256 -c SHA256SUMS.txt)
```

Fresh mode retrieves historical AAPL OHLCV from Yahoo Finance using yfinance. It saves the provider snapshot to `private_data/fresh-2026-11-13/AAPL.json`. The download requires provider availability. Choose a completed US exchange session with five subsequent sessions supported by the repository's 2024 to 2026 calendar. The loader requires a complete series of valid USD session bars with no splits. The model uses provider closes without dividend adjustments. A fresh download can include later vendor revisions. Its digest and retrieval time identify that run's input.

To repeat the fresh run offline, add `--reuse-prices` and supply a new output directory. Use `--prices-dir` in either run to choose a different private input directory. The builder rejects an existing output directory and an existing fresh snapshot unless explicitly reusing prices. For a new acquisition, choose a new private directory.

## Frozen AAPL partial submission

The frozen window runs from 18 May to 13 November 2026. An earlier 100-calendar-day window supplies warm-up prices. The original local snapshot is required to reproduce the historical assessment. Its SHA-256 is enforced before model execution. A fresh download stays separate, even with the same evaluation end date.

| Local input | SHA-256 |
| --- | --- |
| `private_data/prices/AAPL.json` | `1b6c3babe4d176320a4b4f4c9e6203da045a243061d2d347cf2758636eaab1ff` |
| Original Tavily capture, optional | `2e612d26ff49c96e91b847c4e23e81885bb8bc1d3209be6d2313d59289fc3bb0` |

```sh
python -m pip install -r requirements-submission.txt numpy==2.5.4 pandas==2.3.3 matplotlib==3.11.2
PYTHONPATH=src python scripts/build_submission.py frozen --out outputs_submission/aapl-frozen
(cd outputs_submission/aapl-frozen && shasum -a 256 -c SHA256SUMS.txt)
```

Optionally pass `--news-snapshot private_data/tavily-capture.json` to either build. A missing file produces a news-withheld report. An invalid capture fails validation. The saved Tavily capture adds context to the original report. The forecasts, figure and trading diagnostic come from prices and stay identical when the capture is omitted.

For the final assessment presentation, pass `--issuer-context` in place of `--news-snapshot`. It uses two [reviewed Apple releases](AAPL_ISSUER_CONTEXT.json) for the 13 November assessment, with publication dates and retrieval time shown separately. Both context options remain outside model inputs.

The builder runs the existing replay once and copies the deliverables from that run. The PDF uses its research figure and model metrics. The latest forecast table combines the same-day opening nowcasts with the n+1 to n+5 rows from the post-close forecast table. `manifest.json` records the Git commit and local modification flag, runtime, mode, input fingerprints, results, and trading risk. `SHA256SUMS.txt` covers all other bundle files. Run timestamps and runtime metadata can change between executions. Exact rendering hashes depend on the same dependencies and fonts.

`test-only` accepts locally authored test fixtures and marks the PDF, chart, evaluation and outlook. Run `PYTHONPATH=src python -m pytest -q tests/test_submission_builder.py` to exercise both the price-only workflow and the historical X eligibility gate offline. The fixture results document software behavior only.

The lower-level replay CLI remains available for authorized data research and SQLite inspection. The standalone builder emits the documented evaluation bundle. Keep snapshots, raw source payloads and credentials local.

## Authorized X input

`--x-export` accepts a JSON, JSONL, or CSV export from an already-authorized Apify dataset, and `--x-manifest` accepts its JSON provenance file. Required values are listed in the example below. Keep both under `private_data/`. Record rights, acquisition metadata and actual availability from the source rather than inferring it from publication dates.

```json
{
  "platform": "X",
  "source_name": "Apify",
  "acquisition_method": "authorized_local_export",
  "intended_asset": "AAPL",
  "intended_purpose": "research",
  "access_authorized": true,
  "rights_basis": "",
  "dataset_id": "",
  "retrieved_at_utc": "",
  "row_count": 0,
  "export_sha256": "",
  "historical_text_point_in_time_verified": false
}
```

For retrospective data, preserve that final field as false. The storage layer retains the records and retrieved counts. Only export rows with a true post ID, source text, verified symbol relevance and supported creation timestamp are candidates for sentiment. Historical use additionally requires verified, per-row `observed_at` timestamps carrying a timezone. An attested export can still fail sample coverage and does not prove complete 180-day collection. The current export loader keeps follower and engagement counters out of historical influence features.

To download an existing authorized dataset with `APIFY_TOKEN` set in the local shell, use `download_authorized_apify_dataset` from `cwt_quant.x_export`. It reads paginated dataset items, writes a new local JSON, and returns the manifest to save beside it. It does not launch an actor. A newly downloaded scrape is retrospective by default. [Apify dataset export](https://docs.apify.com/storage/dataset)

Optional `--tavily-news` uses `TAVILY_API_KEY` for current headlines in the outlook. Collection time is recorded and these headlines never enter historical model inputs. [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search)

The supported workflow uses no LLM provider or broker credentials. The no-change baseline and price-only Ridge can complete without credentials. A full evaluation of the X request requires an authorized corpus with point-in-time text evidence and verified coverage. No code or reports from Gemini’s generated ten-ticker results are used in this evaluation.

## Opening nowcast and post-close forecasts

`open-nowcast.csv` contains a separate, genuine n+0 same-day closing-price forecast made with an opening-print information cutoff. It compares a flat-open baseline with the existing Ridge method. Ridge uses the current opening gap, prior returns and prior volatility. Every fitted fold uses completed earlier sessions. The retrospective feed does not independently prove historical opening-print release times or executable fills. These are price-only nowcasts. X-assisted n+0 remains unvalidated.

`post-close-forecasts.csv` contains only predictions for n+1 through n+5. The legacy `forecasts.csv` keeps one row for the observed close for compatibility. Use `is_prediction` and `kind` to distinguish that row from a forecast. The opening nowcast has its own SQLite table, evaluation metrics and model cutoff.

## Planning and importing an authorized actor run

Before collecting, establish permission for the acquisition and research use. The planner prints the proposed input for `apidojo/tweet-scraper`. It makes no provider request. In the Apify Console, review the actor input, actual query cap, plan limits and price before manually launching any authorized collection. A purchased run or token alone does not establish rights to process X content. [Apify actor input](https://apify.com/apidojo/tweet-scraper/input-schema) · [Apify terms](https://docs.apify.com/legal/general-terms-and-conditions) · [X terms](https://x.com/en/tos)

```sh
PYTHONPATH=src python -m cwt_quant.apify_runs plan \
  --ticker AAPL --keyword 'Apple Inc' --end 2026-11-13
PYTHONPATH=src python -m cwt_quant.apify_runs import \
  --ticker AAPL --keyword 'Apple Inc' --end 2026-11-13 --run-id "$AUTHORIZED_APIFY_RUN_ID" \
  --rights-basis "$DOCUMENTED_RESEARCH_PERMISSION" \
  --out private_data/x.json --manifest private_data/x.manifest.json
PYTHONPATH=src python -m cwt_quant.submission \
  --ticker AAPL --end 2026-11-13 \
  --x-export private_data/x.json --x-manifest private_data/x.manifest.json
```

The importer reads only an existing successful run. It verifies its actor, build, run and dataset relationships, matches the stored input to the planned query, and checks pagination. It records UTC query windows and search terms, export SHA-256, observed response counts and run provenance. The planner is a bounded search design. It cannot establish completeness of X search. [Apify dataset pagination](https://docs.apify.com/api/v2/dataset-items-get)

`x-coverage.json` records daily New York and UTC creation-date counts, in-window and out-of-window totals, and model-eligible totals by priced session. UTC query bounds include padding for the final New York evening. AAPL matches include the exact cashtag, issuer-specific phrases such as `Apple Inc` or `Apple earnings`, and the standalone uppercase ticker with financial context. Other symbols retain the cashtag rule. The relevance basis is recorded independently of cutoff eligibility. Sample dates and actual cutoff eligibility use America/New_York. A zero daily count represents zero returned records. It cannot establish that no relevant posts existed.

`x-sentiment-series.csv` and `x-versus-price.png` display two separately labelled series. Retrospective scores use captured text and creation dates. Strict scores require source-attested observations known by the session cutoff. Missing days retain missing scores. Counts fetched at retrieval remain provenance fields. They have no historical availability timestamp and do not affect either historical model. The one-page outlook reports both series using available records in the latest seven calendar days ending at the replay cutoff. [X developer policy](https://docs.x.com/developer-terms/policy)

## Current news, evidence and distribution

`--tavily-news` stores a local normalized `tavily-news.json` capture. For reproducible offline context, pass that file with `--news-snapshot`. SQLite stores captures and articles separately under the historical run ID. The collection timestamp and provider-reported article date are separate fields. Provider dates may be update dates and are never feature-availability timestamps. The X/price panel and all forecasts exclude Tavily data. [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search) · [Tavily terms](https://www.tavily.com/terms)

The root repository does not declare a general open-source license. It uses dependency distributions without vendoring new external source. The yfinance library's software license and Yahoo market-data rights are distinct. Keep raw price snapshots, chart points, provider articles, exported post text and SQLite files local unless a source license explicitly permits redistribution. Public review evidence contains original methodology, coverage counts, input and output digests, and reproduction instructions. A token should be provisioned with the reviewer’s own account or through an approved secret channel. [yfinance usage notice](https://github.com/ranaroussi/yfinance#readme) · [Yahoo Finance terms information](https://help.yahoo.com/kb/yahoo-finance-plus/yahoo-terms-service-information-sln7179.html)

## No-cost archives and labelled benchmark

See [zero-cost sources](DATA_SOURCES_ZERO_COST.md) for data availability and access boundaries. A permitted non-Apify archive can use the local importer. In its manifest use `acquisition_method: "authorized_archive_export"`, a publisher `source_name`, a public HTTPS `source_url`, a stable `dataset_id`, the same required file SHA-256, and a documented `rights_basis`. An archive export in this mode must declare `historical_text_point_in_time_verified: false`. Its rows can feed the retrospective plot and coverage audit. Historical forecasting, historical engagement weighting and inferred observation timestamps remain disabled for this import mode.

The lexical scorer can be evaluated offline against the pinned publisher training and validation CSVs. Download them to a local ignored directory from the links recorded in the [benchmark evidence](FINAL_SUBMISSION_AUDIT.md). The evaluator verifies file digests, removes overlap and never emits raw labelled text.

```sh
PYTHONPATH=src python -m cwt_quant.sentiment_eval   --train private_data/sent_train.csv --validation private_data/sent_valid.csv
```

The final replay also writes `research-figure.png`. The four panels cover observed close and X sentiment, aligned X post activity, observed versus predicted next-session close, and the latest n+0–n+5 forecasts. If there are no eligible X observations, both X panels explicitly show that the evidence is withheld. The figure and report derive their prices and predictions from the same replay.

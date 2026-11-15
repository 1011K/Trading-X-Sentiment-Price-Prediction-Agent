# Reproduce the submission replay

This path uses the repository’s existing direct-horizon Ridge model, with an isolated 180-calendar-day evaluation window. Python 3.10 and 3.12 are supported. The exchange calendar covers 2024–2026. Use eligible USD-listed US equities or ETFs with a complete price history and a split-free input window. Symbols with a different exchange calendar, unsupported instrument type, or incomplete bars fail closed.

```sh
python -m pip install -r requirements-real.txt
PYTHONPATH=src python -m pytest -q tests
PYTHONPATH=src python -m cwt_quant.submission \
  --ticker AAPL --end 2026-11-13 --fetch-prices
```

The AAPL window runs from 18 May through 13 November 2026 inclusive. The preceding 100 calendar days are warm-up. The CLI saves provider OHLCV, adjusted closes and action fields in `private_data/prices/AAPL.json`. The models use provider OHLC and unadjusted-for-dividend close-to-close price returns. Realized splits inside the input window require a separate adjustment policy. Source hashes bind the observed local bytes. Historical bars are vendor snapshots fetched on the date in the manifest.

Run the command again without `--fetch-prices` to replay the same snapshot offline. Select a different `--prices-dir` for a different evaluation end. Use `--tickers AAPL MSFT` for independent runs in separate directories. A failed ticker returns a nonzero exit status. No replacement or synthetic prices are used.

Generated files under `outputs_submission/<TICKER>/` include the one-page outlook, evaluation report, observed close and forward forecasts, matched walk-forward metrics, chronological trade ledger, chart, and source manifest. SQLite stores those data relationships and uses a run ID derived from the inputs and model version. Input snapshots, source manifests, raw posts and replay artifacts are local. Check your provider’s redistribution terms before sharing derived outputs or raw data.

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

For retrospective data, preserve that final field as false. The storage layer retains the records and retrieved counts. Only export rows with a true post ID, source text, explicit cashtag and supported creation timestamp are candidates for sentiment. Historical use additionally requires verified, per-row `observed_at` timestamps carrying a timezone. An attested export can still fail sample coverage and does not prove complete 180-day collection. The current export loader keeps follower and engagement counters out of historical influence features.

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

`x-coverage.json` records daily New York and UTC creation-date counts, in-window and out-of-window totals, and model-eligible totals by priced session. UTC query bounds include padding for the final New York evening. The keyword and ticker broaden discovery; the strict model still requires an explicit cashtag. Sample dates and actual cutoff eligibility use America/New_York. A zero daily count represents zero returned records. It cannot establish that no relevant posts existed.

`x-sentiment-series.csv` and `x-versus-price.png` display two separately labelled series. Retrospective scores use captured text and creation dates. Strict scores require source-attested observations known by the session cutoff. Missing days retain missing scores. Counts fetched at retrieval remain provenance fields. They have no historical availability timestamp and do not affect either historical model. The one-page outlook reports both series using available records in the latest seven calendar days ending at the replay cutoff. [X developer policy](https://docs.x.com/developer-terms/policy)

## Current news, evidence and distribution

`--tavily-news` stores a local normalized `tavily-news.json` capture. For reproducible offline context, pass that file with `--news-snapshot`. SQLite stores captures and articles separately under the historical run ID. The collection timestamp and provider-reported article date are separate fields. Provider dates may be update dates and are never feature-availability timestamps. The X/price panel and all forecasts exclude Tavily data. [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search) · [Tavily terms](https://www.tavily.com/terms)

The root repository does not declare a general open-source license. It uses dependency distributions without vendoring new external source. The yfinance library's software license and Yahoo market-data rights are distinct. Keep raw price snapshots, chart points, provider articles, exported post text and SQLite files local unless a source license explicitly permits redistribution. Public review evidence contains original methodology, coverage counts, input and output digests, and reproduction instructions. A token should be provisioned with the reviewer’s own account or through an approved secret channel. [yfinance usage notice](https://github.com/ranaroussi/yfinance#readme) · [Yahoo Finance terms information](https://help.yahoo.com/kb/yahoo-finance-plus/yahoo-terms-service-information-sln7179.html)

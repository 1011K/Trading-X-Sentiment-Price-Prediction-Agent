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

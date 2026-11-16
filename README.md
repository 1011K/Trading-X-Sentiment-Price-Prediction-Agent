# CWT Quant — AAPL forecasting research

A reproducible Python replay for the CrowdWisdomTrading assessment. It scores authorized X observations when availability is documented, aligns them to exchange sessions, and compares direct Ridge forecasts with simple baselines. Recent news is contextual and stays outside model inputs.

Current submission status: **partial**. The frozen AAPL replay includes real prices and an independently checked forecast and trading ledger. The historical X experiment requires an authorized corpus with point-in-time observations. [Final evidence and limits](docs/FINAL_SUBMISSION_AUDIT.md)

## Install and run

Python 3.10 and 3.12 are tested.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-real.txt
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m cwt_quant.submission --ticker AAPL --end 2026-11-13 --fetch-prices
```

The first run saves the Yahoo Finance snapshot locally. Omit `--fetch-prices` to reuse the same inputs without network access. The price replay needs no API key. Use `--tavily-news` with a local `TAVILY_API_KEY` to capture current news, then `--news-snapshot` to replay that capture. Authorized X data requires a local export and source manifest. [Step-by-step reproduction](docs/SUBMISSION_REPLAY.md)

## Method and evidence

- The 180-calendar-day evaluation ends 13 November 2026. The 126 evaluation sessions and separate 68-session warm-up use observed OHLCV and a complete US equities calendar.
- n+0 is a same-day close forecast from information available at the open. n+1 through n+5 are post-close forecasts. Expanding folds use only mature labels and train-only scaling.
- Retrospective X text and cutoff-eligible observations are tracked separately. Retrieved engagement is never backdated. X forecasts remain withheld when eligible coverage is inadequate.
- Forecast comparisons use matched origins. The trading diagnostic applies positive n+1 signals to a hypothetical next-session open-to-close position, with 10 bps per round trip and explicit cash periods.
- On the frozen AAPL sample, Ridge had lower RMSE at n+1 and higher RMSE at n+2 through n+5. The opening-price baseline had lower n+0 RMSE. These results describe one retrospective window.

## Submission outputs

The CLI writes the source manifest, SQLite replay, forecast tables, matched metrics, trade ledger, X coverage, two research charts plus a four-panel overview, one-page outlook, and evaluation under `outputs_submission/AAPL/`. Keep credentials, vendor snapshots and licensed source data local. [No-cost source audit](docs/DATA_SOURCES_ZERO_COST.md)

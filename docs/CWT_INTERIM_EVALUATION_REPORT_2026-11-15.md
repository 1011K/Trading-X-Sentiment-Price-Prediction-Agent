# CrowdWisdomTrading: provisional evaluation evidence (15 Nov 2026)

**Status: EXPERIMENTAL / PARTIAL. This is not a certified historical X-sentiment backtest.**

Repository: https://github.com/1011K/Trading-X-Sentiment-Price-Prediction-Agent

## Verified engineering evidence

- Current `main` commit baseline: `ebd50295c6c5c0dd29ae06fc28db60d8ce2c7a8e`.
- GitHub Actions succeeded for Python 3.10 and 3.12 on that commit with offline invariants and synthetic CLI integration: https://github.com/1011K/Trading-X-Sentiment-Price-Prediction-Agent/actions/runs/43708874829
- The versioned `LOCAL_VALIDATION.txt` reports 34 synthetic/offline tests passed and a TSLA synthetic fixture containing 128 sessions and 492 generated posts, with 405 walk-forward observations/model across 5 horizons. **These are fixture test statistics, not live-alpha evidence.**
- The daily equity pipeline offers no-change, price-only Ridge, and gated price+sentiment research models, with point-in-time checks. Forecast `n+0` from a post-close origin is the observed close; `n+1` through `n+5` are direct future trading-session forecasts.

## Unavailable market-evidence claims

| Metric | Classification | Reason |
|---|---|---|
| Real historical X model MAE/RMSE | WITHHELD | No authenticated 180-day historical X corpus and independently replayed forecast ledger |
| Incremental X sentiment forecasting benefit | WITHHELD | No matched-origin historical X and price-only comparison |
| Directional hit rate on real X model | WITHHELD | No validated historical forecast ledger |
| Sharpe / Sortino / maximum drawdown for real X strategy | WITHHELD | No audited executable trading fills and returns |

The separately supplied Gemini 10-stock results with 26,560 generated X posts and 632 generated news records come from synthetic sources and were not independently collected from X/Apify or Tavily. The synthetic sentiment used following-session returns to shape its values. **These results must not be represented as empirical forecasting performance.**

## Run existing offline checks

```bash
python3 -m pip install -r requirements.txt
PYTHONPATH=src python3 -m pytest -q tests
PYTHONPATH=src python3 -m cwt_quant.cli --ticker AAPL --out outputs_synthetic
```

Optional real-price mode, not a historical X backtest:

```bash
python3 -m pip install -r requirements-real.txt
PYTHONPATH=src python3 -m cwt_quant.cli --ticker AAPL --real-data --out outputs_real
```

The 180-calendar-day period ending 2026-11-13 begins 2026-05-18 inclusive. Any earlier data used for feature warm-up must be disclosed and excluded from the evaluation window.

## Full completion required

Acquire authorized historical X posts and provenance, validate price source and exchange calendar, implement point-in-time database joins, independently rerun matched-origin walk-forward models, calculate risk metrics from a valid chronological hypothetical trade ledger, regenerate the one-page outlook and charts, add reproducibility evidence, and publish tested code without secrets.

See [Codex execution plan](CODEX_SUBMISSION_EXECUTION_2026-11-15.md) on this branch. The employer requested a public repo, reproducibility details and evaluation report. Provide sensitive API keys only by an explicitly authorized, secure channel.

**Final classification: EXPERIMENTAL/PARTIAL. This report does not claim full completion of the employer's assignment.**

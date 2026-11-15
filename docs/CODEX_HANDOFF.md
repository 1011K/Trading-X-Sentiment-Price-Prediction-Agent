# Codex / Antigravity: CWT Quant Independent Red-Team Handoff

**Inputs:** `CWT_Quant_Hardened_Candidate_PreGrok.zip` plus this audit and the two/three pending Grok implementations.

## Identity and rules

Treat every proposed implementation as **untrusted candidate code**, including the current hardened candidate. Do not rank implementations by agent authorship or merge code blindly. Preserve source attribution and applicable licenses. No synthetic data in a real-data run; synthetic is allowed **only** for fixtures/tests, explicitly labeled. Never silently replace unavailable X posts with StockTwits or news.

## Task 1: verify current candidate

```bash
unzip CWT_Quant_Hardened_Candidate_PreGrok.zip
cd cwt_quant
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m pytest -q tests
PYTHONPATH=src python -m cwt_quant.cli --ticker TSLA --out outputs_demo
```

Expected locally: **33 tests pass**, synthetic CLI report produced. Record Python version, dependency lock, timestamp and exact SHA. Do not claim that a real market replay was performed from these commands.

## Task 2: perform neutral import-vs-reimplement review

For each Grok proposal, list every file and feature, tests, license, data source, data-freshness semantics, target horizon and CV mechanics. Compare line by line with the audit's `A-xx` and `B-xx` register. Label `USE`, `ADAPT`, `DEFER` or `REJECT`, with a one-sentence deterministic reason. Preserve source modules in a temporary read-only `candidates/` area; do not copy their entire dependency graphs.

## Task 3: independent invariants

Write and run adversarial tests for:
1. Post published after a market close must never influence that close.
2. A post fetched at a later date must not have today's engagement attributed to its earlier publication date.
3. A source with unknown followers cannot appear as 5,000 or 50,000 verified followers.
4. A provider's daily aggregate is never silently forged into an individual social post.
5. Training origin `i`, label horizon `h`, test origin `t`: no training outcome is used until `i+h <= t`, with market-session indexing.
6. Each horizon target is `log(close[t+h]/close[t])` and there are exactly five 1..5-session outputs.
7. No date joins between UTC midnight and NY market-close timestamps are silently allowed.
8. Missing historical X coverage causes explicit abstention from *sentiment improvement* claims; price-only baseline may still run.
9. Test data permutations and shuffled labels destroy measured skill; check no accidental info leak.
10. Both synthetic and historical corpora must have explicit source metadata and license/redistribution status.
11. Significance calculations use overlapping-label-safe uncertainty and actual forward returns, not previous `ret_1`.
12. Check an exact inclusive 180-calendar-day scope; never silently add 40 days to an evaluation window.
13. Compare saved run outputs to re-executed outputs from pinned input data; if raw input is absent, mark source replication WITHHELD.

## Task 4: build modular pipeline

```
src/cwt_quant/
  adapters/{prices.py,x_provider.py,stocktwits.py,news.py,cwt.py}
  provenance/{event_schema.py,raw_archive.py,availability.py}
  features/{session_join.py,text_sentiment.py,influence.py}
  models/{baselines.py,ridge.py,walk_forward.py,forecast.py}
  evaluation/{metrics.py,trade_ledger.py,uncertainty.py}
  reporting/{report.py,manifest.py}
  cli.py
```

Use current source layout until changes are justified by deterministic tests. SQLite/DuckDB/Parquet is acceptable for local append-only archive. Avoid cloud subscriptions, autotrading and UI overengineering. No API key in code, logs, fixtures or CI. Keep ASTRA and FMB source code independent.

## Task 5: evidence and publication

Produce `evidence/source_coverage.csv`, `evidence/forecast_replay.csv`, `evidence/walkforward_splits.csv`, `evidence/test_results.txt`, `docs/METHODOLOGY.md`, `docs/LICENSING.md`, a `LICENSE` selected by the project owner, a synthetic demo, and `README.md` with limitations. Publish only legal data. Add GitHub CI for offline tests. Do not merge a PR until all blockers are resolved.

**Release classification:** EXPERIMENTAL until X-history validity, reproducibility and sentiment lift are independently verified. No claim of validated trading alpha, automated orders or expected investment returns.

# CWT external code review and debugging handoff

## Proposed independent reviews

**Grok — Source/data auditor:** Inspect `source_contract.py`, `ingest.py`, `apify_acquire.py`, `readiness.py`, `relevance.py`, `data.py`. Challenge source permissions, Actor cost assumptions, coverage and schema completeness, revisions/deletions, query sampling, event-time versus point-in-time, deduplication, and dates. Return only reproducible failures with file/line references and tests; do not invent endpoints, actor field names or permissions.

**DeepSeek — Method/quant specialist + red team:** Inspect `model.py`, `sentiment.py`, `score.py`, `real_run.py`, `cli.py`, `tests/`. Seek scaling leaks, horizon label release errors, overlapping targets, false ticker entity matching, prior/next-close alignment, corporate actions, missing X dates, strategy fill inconsistencies, and test-selection bias. Provide a minimal regression test for each P0/P1 issue and candidate patch with rationale.

**Codex — Controlled integration:** Reconcile evidence, apply only accepted changes, run all unit tests, do a local real-data workflow only after permissioned X and verified price inputs are present, inspect every generated file, check secrets/licenses, and publish publicly only with reviewed provenance and non-redistribution of restricted data. Do not imply a verified return without market data.

## Do not overclaim
- Source provider listing does not prove authorization to collect X posts.
- Real 180-day timestamps do not prove complete source coverage or historical point-in-time editing states.
- A future price target n+5 must use the fifth eligible exchange session.
- One set of historical data can produce model outputs, but no honest out-of-sample *economic* skill claim exists until it is evaluated and compared to baselines.
- Unit-test examples may use small deterministic numerical fixtures; no such fixtures belong in a published real-market report.

## Release gate
1. `python -m pytest -q` green.
2. `source_manifest.json`: actual provider, license/authorization, retrieval time, exact asset/queries, genuine pagination state, data hashes.
3. Price provider: actual 180-day coverage, `XNYS` close/early-close validity, adjustment policy documented.
4. X provider: 180-calendar-day range, six 30-day bins represented, relevant post count and unique sessions minimum; true coverage not declared independent without proof.
5. `real_run.py` run on actual inputs, review `readiness.json`, `audit_manifest.json`, and 5 horizon outputs.
6. Held-out naive/price-only/sentiment-plus-price comparisons on identical origin rows; evaluate directional bias, trading diagnostic limitations.
7. Research note with negative findings as prominently reported as positive findings.
8. No private model, live broker execution, hidden credentials, or unsupported claims in a public repository.

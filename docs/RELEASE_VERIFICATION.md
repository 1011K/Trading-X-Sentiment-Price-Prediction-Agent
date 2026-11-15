# Release Verification Matrix (2026-11-15)

| Control | Status | Evidence |
|---|---|---|
| Offline deterministic tests | VERIFIED locally | `PYTHONPATH=src python -m pytest -q tests` |
| Synthetic CLI execution | VERIFIED locally | `PYTHONPATH=src python -m cwt_quant.cli ...` |
| 180-day historical X with observation timestamps | WITHHELD | No source archive supplied |
| Point-in-time follower snapshots | WITHHELD for real data | Synthetic only; missing snapshots force neutral weight |
| 180-day real-price replay | WITHHELD in this release | Requires internet on host; no rerun output shipped |
| Incremental X sentiment forecasting skill | WITHHELD | No historical X+price aligned data |
| Third-party data redistribution rights | NOT GRANTED BY DEFAULT | Keep CWT/API/source datasets out of git |
| Complete Grok comparison | WITHHELD | Grok source files not included |

Any future claim of VERIFIED must include dataset provenance, exact timestamps, git SHA, comparable model OOS origins, code+data hashes, run logs, and independent recomputation.

NYSE 2026 equities early closes (official): **November 27 and December 24**, 1 p.m. ET. The July 2 early close found on some calendars is a **SIFMA bond-market** schedule, not NYSE equities. Source: https://www.nyse.com/trade/hours-calendars

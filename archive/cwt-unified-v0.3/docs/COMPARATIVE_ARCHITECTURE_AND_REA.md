# Competitor/public-source architecture review — 15 November 2026

| Project | Evidence inspected | Useful principle | Integration decision |
|---|---|---|---|
| [REA](https://github.com/morluto/rea) | Official public repository/readme; MIT | Evidence-led static analysis of authorized local applications | REFERENCE; not necessary to execute CWT |
| [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) | Public docs/readme, and its publicly visible Forecaster demo `app.py`; MIT repository code | Task-specific financial-language sentiment experiments; the demo describes random sampling of market news and stochastic text generation | REFERENCE only; avoid stochastic prediction outputs as deterministic research labels; review model weights/license separately |
| [FinRL-X](https://github.com/AI4Finance-Foundation/FinRL-Trading) | Public README/module architecture; Apache-2.0 | Separate data, signal, simulation and execution; weight contract | ADAPT architectural separation, not clone |
| [QuantConnect Lean](https://github.com/QuantConnect/Lean) | Public engine docs/readme; Apache-2.0 | Exchange-clock and event-driven simulation | REFERENCE for later paper engine |
| [ml-market-forecasting](https://github.com/aryangoshalia/ml-market-forecasting) | Public readme and source tree | Negative controls, leakage tests, practical cost sensitivity | ADAPT tests independently; no license declared in repository metadata |
| [Financial Sentiment Alpha Prediction](https://github.com/liamhavers/Financial-Sentiment-Alpha-Prediction-System) | README and source tree | Fixed universe, no-alpha null, post-count floor | REFERENCE only; StockTwits not X and no license in metadata |

## REA usage boundary
REA was **not executed** here against any proprietary hosted app. There are no downloaded app binaries, authorized installations, or local REA runtime in this execution environment, and financial web app backends cannot be recovered by viewing public pages.

For a lawful public-code architecture audit, review the source tree and tests directly. For an application you own or have authorization to inspect, review [REA installation](https://github.com/morluto/rea) and its exact version before configuring a local coding agent. Avoid bypassing restrictions, extracting private algorithms, or treating inference as a verified implementation detail.

## Strongest objection
A more complex end-to-end AI trading agent may look impressive but makes a 180-calendar-day daily forecasting exercise statistically underpowered and harder to audit. Unless a simpler baseline is beaten in genuine held-out data after reasonable transaction costs, additional algorithms are not justified.

## Further improvements later, separate from employer acceptance
- Multi-ticker research with controlled multiple comparisons and asset-specific calendars.
- Larger historically licensed text archive with *documented* snapshots (no retrospective engagement leakage).
- Human-evaluated asset stance labels; compare VADER against a properly licensed contextual model.
- Prediction intervals calibrated only on past, non-overlapping residuals.
- Block bootstrap uncertainty and regime sensitivity when ample genuine history exists.
- Paper-execution simulator with next-open assumptions, spreads, cost sensitivity, cash/risk limits, and zero-broker credential requirements.
- Audit dashboards and experiment registry with explicit refusal to auto-select a winning model based on the same test set.

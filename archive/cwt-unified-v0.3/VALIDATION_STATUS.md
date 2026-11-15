# Validation status — 2026-11-15

**VERIFIED (local):** Code archive builds, unit regression checks for leakage/cutoffs/relevance/provenance, command-line parser is callable. A 24-test test suite passed locally on Python 3.13.

**NOT PERFORMED:** Downloading an actual 180-day X corpus, live Apify Actor run, authorized API entitlement validation, live yfinance daily data download, current Tavily/Exa queries, live provider parsing tests, financial backtest performance, trading execution, REA binary analysis of external apps, public GitHub deployment.

**NOT VALIDATED:** Real forecast performance, X coverage, historical text point-in-time guarantees, license/redistribution permissions, market execution costs, economic alpha and production operations.

**Research design:** Five direct log return Ridge regressors for horizons h=1..5, origin observed at close t; unchanged-price and price-only controls; strictly expanding labels i+h<=t; source manifest and data readiness gate; no synthetic fallback in production command.

**Strongest objection:** 180 calendar days of an equity's daily prices yields about 125 trading sessions. A few held-out observations with overlapping h=5 targets and retrospectively collected posts cannot demonstrate robust investable alpha. This tool is a reproducible research submission candidate, not a deployable money-making system.

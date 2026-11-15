# Final implementation specification: real-data gated CWT v0.3

## Objective
Forecast observed n+0 and future exchange-session closes n+1..n+5 using only actual historical prices and actual X posts. News from Tavily/Exa is separately stored as current context, never included in historical features. No brokerage execution. Research/paper trading only.

## Exact targets
For each forecast origin session t and horizon h=1..5, target y=ln(C_{t+h}/C_t). n+0 is C_t observed (not estimated). The model is a train-only StandardScaler plus regularized Ridge, separately fitted per horizon h. Naive unchanged close and price-only Ridge are baselines. Sentiment+price is an incremental hypothesis. Fixed alpha=10 avoids tuning on the same short test window.

## Data and integrity contract
1. Capture UTC creation timestamps, stable post IDs, actual source schema and query terms. Deduplicate IDs. Filter asset relevance with reason-coded, conservative matching; explicitly track false positives and missing entity matches.
2. Exchange calendar is XNYS for AAPL. At/after close posts map to next session. Early closes and US holidays are handled by exchange_calendars. A forecast made just after close t cannot use information from after that close.
3. Posts observed only retrospectively can produce **event-time historical simulation**, not verified point-in-time archive. Retrospectively fetched engagement/follower counts are excluded. Edit/delete survivorship remains an explicit limitation.
4. At the first test origin t, training row i is eligible only if i+h<=t. Train-only scaling. No random shuffle, no future model selection.
5. Require a real, permissioned source manifest and actual X posts in six approximately monthly periods. Insufficient coverage fails closed; no synthetic fallback.
6. Report price MAE/RMSE, naive RMSE, directional accuracy and horizon-specific counts. Adjacent h=5 errors overlap; do not treat them as independent samples.
7. Research trading diagnostic uses next-open-to-same-day-close if *open prices exist*, costs explicitly disclosed, and does not claim to trade n+5 forecasts at historical closing prices.

## Honest release gate
Code tests passing != economic accuracy. Mark model performance **WITHHELD** until real X posts have been acquired and processed, price periods verified, and out-of-sample results computed. Model impact is incremental: sentiment model must beat price-only and no-change on matching origins; a superior training fit does not count.

## Risk
This project does not place orders, bypass brokerage onboarding or provide a real-money trading mechanism. Only paper research and diagnostics. Any future regulated live trading requires legal eligibility, platform authorization, risk design and independent review.

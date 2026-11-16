# Current integration matrix

This matrix maps all 62 candidates from the [prior register](https://github.com/1011K/Trading-X-Sentiment-Price-Prediction-Agent/blob/24b1ab8bcdc69d5782e270b01752a465592a60aa/archive/cwt-unified-v0.3/docs/audits/repository-integration-audit-2026-11-15.md) to the active `cwt_quant` tree. Equivalent means the project implements the relevant capability locally. It makes no claim of numerical equivalence or code reuse.

| Status | Count | Code or decision |
| --- | ---: | --- |
| USED | 1 | yfinance is imported by `replay_prices.py` for fresh Yahoo Finance snapshots. The frozen replay reads saved bytes. |
| EQUIVALENT IMPLEMENTATION | 7 | `x_export.py` and `apify_runs.py` use authorized export/import and HTTPS metadata. `connectors/tavily.py` uses HTTPS. Local lexical scoring, direct Ridge, mature-label folds and risk metrics live in `features.py`, `models.py`, `backtest.py` and `metrics.py`. |
| NOT INTEGRATED | 19 | Reference material, examples and catalogs have no runtime role. |
| DEFERRED | 11 | Other asset venues, additional APIs, models, storage engines and dashboards remain outside the AAPL replay. |
| REJECTED | 24 | Excluded for the reasons recorded in the prior register, including authorization gaps, obsolete interfaces, and fit for this assessment. |

The register's supplementary scikit-learn and exchange_calendars suggestions correspond to the active NumPy Ridge and local XNYS calendar. pytest and Matplotlib are used directly. ReportLab is the PDF renderer's required dependency. This change copies no upstream implementation and grants no source-data rights.

## Candidate mapping

**USED** (1)

`ranaroussi/yfinance`.

**EQUIVALENT IMPLEMENTATION** (7)

`apify/apify-client-python`, `robbyczgw-cla/x-apify`, `tavily-ai/tavily-python`, `cjhutto/vaderSentiment`, `skforecast/skforecast`, `eslazarev/purged-cross-validation`, `ranaroussi/quantstats`.

**NOT INTEGRATED** (19)

`apify/apify-docs`, `Xquik-dev/x-twitter-scraper`, `apidojo-io/social-media-skills`, `itsmohitkumar/Stock-Sentimental-Analysis`, `ranahaani/GNews`, `mattlisiv/newsapi-python`, `yya518/FinBERT`, `laugustyniak/awesome-sentiment-analysis`, `liamhavers/Financial-Sentiment-Alpha-Prediction-System`, `Aaron-Paul/Bitcoin-Price-Twitter-Sentiment-Analysis`, `scorpionhiccup/StockPricePrediction`, `alvarobartt/twitter-stock-recommendation`, `letsbegincode/stock_trends_prediction`, `quantinsti/AI-in-Trading-Workflow`, `aryangoshalia/ml-market-forecasting`, `sunandha01/financial-market-prediction`, `tejaaa69/Alpha-Engine-for-Commodities-`, `arshkazi/Commodities_price_prediction`, `wilsonfreitas/awesome-quant`.

**DEFERRED** (11)

`tweepy/tweepy`, `ccxt/ccxt`, `exa-labs/exa-py`, `cardiffnlp/tweeteval`, `duckdb/duckdb`, `Nixtla/statsforecast`, `microsoft/LightGBM`, `dmlc/xgboost`, `polakowo/vectorbt`, `streamlit/streamlit`, `plotly/plotly.py`.

**REJECTED** (24)

`0xrish/X-Twitter-Advanced-Search-Tweet-Scraper`, `akshathakurr/gtm-engine`, `vladkens/twscrape`, `d60/twikit`, `JustAnotherArchivist/snscrape`, `twintproject/twint`, `planet-winter/ccxt-ohlcv-fetcher`, `alpacahq/alpaca-trade-api-python`, `binance/binance-connector-python`, `kobyal/ai-news-briefing`, `FinBERT-SIMF/FinBERT-SIMF`, `sloria/TextBlob`, `unit8co/darts`, `Nixtla/neuralforecast`, `jdb78/pytorch-forecasting`, `microsoft/forecasting`, `kernc/backtesting.py`, `mementum/backtrader`, `mmkeskar/Stock-Price-Prediction-with-Sentiment-Analysis`, `Prerna77Arora/Stock_Price_Prediction_Tool`, `AshwiniDPrabhu/Stock-Prediction-Using-Twitter-Sentiment-Analysis`, `VAnkataBot/TraderAI`, `YashBoda/AInvest`, `nyannbob/ARIMA-LSTM-price-prediction`.

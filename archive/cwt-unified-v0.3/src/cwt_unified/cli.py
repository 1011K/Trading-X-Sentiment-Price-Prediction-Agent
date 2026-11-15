"""CLI for reproducible off-line evaluation. NO scraping or brokerage integration."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd
import numpy as np
import exchange_calendars as xc
from .config import Config
from .data import load_prices, load_posts, sha256
from .sentiment import build_daily_sentiment
from .model import build_features, walkforward, forecast_latest, summarize, research_pnl
from .charts import sentiment_price_figure


def run(prices_path: str, posts_path: str, output: str, cfg: Config, synthetic: bool = False) -> dict:
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    prices = load_prices(prices_path, cfg.exchange_calendar)
    last = pd.Timestamp(prices.date.iloc[-1])
    prices = prices.loc[pd.to_datetime(prices.date) >= last-pd.Timedelta(days=cfg.history_days-1)].reset_index(drop=True)
    if len(prices)<cfg.min_bars:
        raise ValueError(f"Only {len(prices)} bars inside pinned {cfg.history_days}-calendar-day window; need {cfg.min_bars}")
    posts = load_posts(posts_path)
    daily, audit = build_daily_sentiment(prices, posts, cfg)
    matrix = build_features(prices, daily)
    pred = walkforward(matrix,cfg,audit["influence_model_eligible"])
    latest = forecast_latest(matrix,cfg,audit["influence_model_eligible"])
    metrics = summarize(pred)
    diagnostic = research_pnl(pred,prices,cfg)
    matrix.to_csv(out/"feature_matrix.csv",index=False)
    pred.to_csv(out/"walkforward_predictions.csv",index=False)
    latest.to_csv(out/"latest_forecasts.csv",index=False)
    pd.DataFrame(metrics).to_csv(out/"forecast_metrics.csv",index=False)
    sentiment_price_figure(matrix,out/"sentiment_vs_price.png",cfg.ticker,False)
    manifest={
        "classification":"WITHHELD_REAL_DATA_PROVENANCE",
        "synthetic":False,"ticker":cfg.ticker,"exchange_calendar":cfg.exchange_calendar,
        "window_calendar_days_requested":cfg.history_days,
        "price_start_date":str(prices.date.iloc[0]),"price_end_date":str(prices.date.iloc[-1]),
        "last_available_close_utc":str(prices.market_close_utc.iloc[-1]),
        "daily_bars":len(prices),"raw_input_post_rows":len(posts),
        "price_sha256":sha256(prices_path),"posts_sha256":sha256(posts_path),
        "baseline":"naive unchanged close; price-only Ridge; price+sentiment Ridge; influence only with snapshot eligibility",
        "n0_semantics":"Observed close, not prediction",
        "model_spec":{"ridge_alpha":cfg.ridge_alpha,"min_train_rows":cfg.min_train_rows,
                      "horizons":list(cfg.horizons),"first_test_fraction":cfg.first_test_fraction},
        "data_audit":audit,"trading_diagnostic":diagnostic,
        "limitations":["180 calendar days gives roughly 125 sessions; weak statistical power",
                       "Unverified source provider, license, and historical X collection coverage",
                       "Post created_at is not proof against historical edits/deletions",
                       "Any externally supplied sentiment must have documented model/version and calibration",
                       "Influence thresholds 1M/10k and weight coefficients are pre-registered heuristics, not evidence of causal effect",
                       "Only fixed hardcoded model settings tested; external tuning invalidates clean OOS results",
                       "Ticker filter uses cashtags and sacrifices recall for precision",
                       "Adjusted/raw price consistency, corporate actions, and real trading fills must be independently audited",
                       "Tavily/Exa news is context-only and MUST NOT enter forecasting features"],
    }
    (out/"audit_manifest.json").write_text(json.dumps(manifest,indent=2,allow_nan=False,default=str),encoding="utf-8")
    last20 = matrix.tail(20)
    mean = float(last20.sentiment_mean.mean())
    (out/"one_page_outlook.md").write_text(f"""# {cfg.ticker} | Research sentiment outlook

**Evidence classification:** {manifest['classification']}.

**Last observable session:** {manifest['price_end_date']} (as-of close {manifest['last_available_close_utc']}).

**n+0:** {prices.close.iloc[-1]:.4f}, **observed**, not predicted. Direct n+1..n+5 forecast comparisons: `latest_forecasts.csv`.

**Recent X sentiment:** 20-session unweighted mean {mean:+.3f} on a -1 to +1 scale; {audit['relevant_mapped_posts']} relevant mapped posts in analysis window. A zero-post session is recorded as zero sentiment and separately flagged.

**Influence availability:** {'PIT snapshot complete and influence variant estimated' if audit['influence_model_eligible'] else 'NOT ELIGIBLE; historical engagement snapshots missing or incomplete, influence model withheld'}.

**Walk-forward testing:** Compare no-change, price-only and price+sentiment for each horizon, with label-release purging and train-only scaling. See `forecast_metrics.csv`; no performance claims are made without independent real-data provenance review.

**Interpretation:** This is a research pipeline. Correlation, forecast skill, and tradeability are distinct claims. The lexical baseline misreads sarcasm, negation, news quotations, and ambiguity; optional externally pre-scored sentiment requires separate validation. News retrieved after an origin must not be used to explain a past prediction as though known then.
""",encoding="utf-8")
    return manifest


def main():
    import argparse
    p=argparse.ArgumentParser(description='CWT research evaluator: requires REAL post and price CSVs')
    for name in ['prices','posts','ticker']:p.add_argument('--'+name,required=True)
    p.add_argument('--out',default='results')
    a=p.parse_args()
    manifest=run(a.prices,a.posts,a.out,Config(ticker=a.ticker.upper()),False)
    print(json.dumps({'status':manifest['classification'],'ticker':manifest['ticker'],'bars':manifest['daily_bars']},indent=2))

if __name__=='__main__': main()

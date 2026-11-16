"""Dated, reproducible US equity research submission replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import replace
from datetime import date, datetime, timezone
from html import escape
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from .calendar import XNYSCalendar
from .config import Config
from .data import _empty_posts_schema
from .exceptions import CWTQuantError, DataError
from .logging_utils import get_logger
from .metrics import forecast_metrics, trading_summary
from .nowcast import open_nowcasts
from .pipeline import run_pipeline
from .replay_prices import capture_prices, evaluation_bounds, load_prices
from .replay_store import store_run
from .research_figure import research_figure
from .x_analysis import chart_sentiment, sentiment_series, summarize_sentiment

log = get_logger(__name__)


def _forecast_rows(result: dict) -> pd.DataFrame:
    panel, forward = result["panel"], result["forward"]
    origin = panel.index[-1]
    close = float(panel["close"].iloc[-1])
    observed = pd.DataFrame([{
        "origin": origin, "model": "observed", "horizon": 0, "y_hat": None,
        "close_t": close, "forecast_close": close,
    }])
    if forward is None or forward.empty:
        raise DataError("No forward forecasts were produced")
    forecasts = pd.DataFrame.from_records([*observed.to_dict("records"), *forward.to_dict("records")])
    cal = XNYSCalendar()
    target_dates = [origin.date()]
    for _ in range(5):
        target_dates.append(cal.next_trading_day(target_dates[-1]))
    forecasts["target_session"] = forecasts["horizon"].map(dict(enumerate(target_dates)))
    forecasts["kind"] = forecasts["horizon"].map(lambda h: "observed" if h == 0 else "forecast")
    forecasts["is_prediction"] = forecasts["horizon"].gt(0)
    return forecasts.sort_values(["horizon", "model"]).reset_index(drop=True)


def _markdown_value(value: object) -> str:
    if value is None or pd.isna(value):
        return "WITHHELD"
    return f"{value:.5f}" if isinstance(value, float) else str(value)


def _chart(path: Path, panel: pd.DataFrame, comparisons: pd.DataFrame, start: date) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(10, 7), layout="constrained")
    FigureCanvasAgg(figure)
    prices, scores = figure.subplots(2, 1, height_ratios=[2, 1])
    window = panel.loc[panel.index.date >= start]
    prices.plot(window.index, window["close"], color="#165283", linewidth=1.6)
    prices.set(ylabel="Close (USD)", title="Observed prices in the evaluation window")
    prices.grid(alpha=0.2)
    for model, values in comparisons.groupby("model"):
        scores.plot(values["horizon"], values["rmse"], label=model, marker="o")
    scores.set(xticks=range(1, 6), xlabel="Trading-session horizon",
               ylabel="RMSE (log return)", title="Walk-forward error at matched origins")
    scores.legend(frameon=False)
    scores.grid(alpha=0.2)
    figure.savefig(path, dpi=145)


def _write_reports(out: Path, manifest: dict, forecasts: pd.DataFrame,
                   comparison: pd.DataFrame, risk: dict, nowcasts: pd.DataFrame) -> None:
    ticker = manifest["ticker"]
    start, end = manifest["evaluation_start"], manifest["evaluation_end"]
    observed = forecasts.iloc[0]
    source = manifest["prices"]
    x_status = manifest["historical_x_status"]
    outlook = [
        f"# {ticker} one-page outlook", "",
        f"**{end} observed close: USD {observed.forecast_close:.2f}.**",
        "", f"**Historical X signal: {x_status}.** {manifest['historical_x_note']}",
    ]
    summary = manifest["sentiment_outlook"]
    outlook.extend(["", f"**X sentiment window: {summary['start']} to {summary['end']} (New York).**"])
    for label, name in (("strict", "Time-eligible text"), ("retrospective", "Retrospective text")):
        sample = summary[label]
        if sample["posts"]:
            outlook.append(
                f"- {name}: {sample['lexical_direction']}, mean {sample['mean']:.3f} over {sample['posts']} posts."
            )
        else:
            outlook.append(f"- {name}: WITHHELD. No eligible observations.")
    outlook.append("Retrospective text scores describe the captured sample and are excluded from forecasting.")
    latest_nowcasts = nowcasts.loc[nowcasts["target_session"].eq(date.fromisoformat(end))]
    if not latest_nowcasts.empty:
        nowcast = latest_nowcasts.set_index("model").loc["price_only"]
        outlook.extend([
            "", f"**n+0 opening nowcast (09:30 New York): USD {nowcast.forecast_close:.2f}.** "
            "Price-only Ridge estimates the same-day close from the opening print and earlier prices.",
        ])
    news = manifest["current_news"]
    if news.get("headlines"):
        outlook.extend(["", f"**Current news context from Tavily.** Retrieved {news['collected_at_utc']}."])
        for item in news.get("articles") or news["headlines"]:
            title = escape(item["title"]).replace("[", "\\[").replace("]", "\\]")
            date_text = item.get("published_at_utc") or item.get("published_date") or "date unavailable"
            outlook.append(f"- [{title}](<{item['url']}>) ({date_text})")
    else:
        outlook.extend(["", "**Recent news: WITHHELD.** " + news["note"]])
    outlook.extend([
        "", "Forecasts are experimental scenarios derived from the observed close.", "",
        "| Horizon | Target session | No change (USD) | Price Ridge (USD) |",
        "| --- | --- | ---: | ---: |",
    ])
    for horizon in range(1, 6):
        rows = forecasts.loc[forecasts.horizon == horizon].set_index("model")
        outlook.append(
            f"| n+{horizon} | {rows.iloc[0].target_session} | "
            f"{rows.loc['no_change', 'forecast_close']:.2f} | {rows.loc['price_only', 'forecast_close']:.2f} |"
        )
    if x_status == "AVAILABLE":
        outlook.extend(["", "See forecasts.csv for the X variant. The charts show all matched models."])
    outlook.extend(["", "No trading or predictive-performance claim is made."])
    (out / "outlook.md").write_text("\n".join(outlook) + "\n", encoding="utf-8")

    report = [
        f"# {ticker} evaluation report", "", "**EXPERIMENTAL research replay**", "",
        f"Replay generated {manifest['generated_at_utc']} using CWT Quant {manifest['model_version']}.",
        "", f"Evaluation covered {start} through {end} inclusive "
        f"({manifest['evaluation_sessions']} regular US exchange sessions).",
        f"A separate {manifest['warmup_sessions']}-session warm-up began {manifest['warmup_start']}.",
        f"Matched walk-forward origins ran {manifest['first_oos_origin']} through {manifest['last_oos_origin']}.",
        "", "## Evidence and model policy", "",
        f"- Prices came from {source['provider']} ({source['exchange']}, {source['currency']}).",
        f"- Snapshot retrieval time was {source['retrieved_at_utc']}. SHA-256: `{source['sha256']}`.",
        f"- {source['policy']}. Dividends and split fields were retained for review.",
        "- Provider data is a retrospective snapshot. Original per-session feed release times and data revisions were not independently verified.",
        f"- Historical X status is **{x_status}**. {manifest['historical_x_note']}",
        f"- X coverage counted {manifest['x_export_rows_for_ticker']} symbol-matched export rows "
        f"and {manifest['x_eligible_rows']} rows eligible for historical model input across the replay.",
        "- Retrospective lexical text is described separately from the strict historical feature series.",
        "- No news observations were joined to historical features.",
        "- Post-close forecasts use direct n+1…n+5 price log returns. The separate n+0 nowcast "
        "uses the opening print and prior-session features to forecast the same-day close.",
        "- Expanding Ridge uses fixed alpha 10, a train-only scaler, and only labels observable by each forecast origin.",
        "", "## Matched walk-forward metrics", "",
        "MAE and RMSE use log returns. Direction is evaluated only where a model issues a nonzero call.",
        "", "| Model | Horizon | Matched n | MAE | RMSE | Direction |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in comparison.itertuples(index=False):
        report.append(
            f"| {row.model} | {row.horizon} | {row.n} | {row.mae:.5f} | "
            f"{row.rmse:.5f} | {_markdown_value(row.direction_accuracy)} |"
        )
    report.extend([
        "", "## Opening nowcast", "",
        "These rows use an opening-time origin and open-to-close log returns. "
        "They are evaluated separately from post-close predictions and excluded from the trading ledger.",
        "", "| Model | Origins | MAE | RMSE |", "| --- | ---: | ---: | ---: |",
    ])
    for model, metrics in manifest["open_nowcast_metrics"].items():
        report.append(f"| {model} | {metrics['n']} | {metrics['mae']:.5f} | {metrics['rmse']:.5f} |")
    report.extend([
        "", "## Hypothetical execution and risk", "",
        "Each positive n+1 signal places a next-session open-to-close long position. "
        "The signal targets a close-to-close log return, so the forecast and the strategy "
        "have different return intervals. "
        "The ledger charges 10 basis points per round trip, includes cash sessions, and uses no overlapping holdings. "
        "Observed quotes approximate fills. The calculation excludes market impact, capacity and taxes.",
        "", "| Model | Sessions | Trades | Cash | Sharpe | Sortino | Max drawdown |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for model, item in risk.items():
        report.append("| " + " | ".join([model] + [
            _markdown_value(item.get(key)) for key in
            ("n_sessions", "n_trades", "n_cash_sessions", "approx_sharpe", "approx_sortino", "max_drawdown")
        ]) + " |")
    for model, item in risk.items():
        if item.get("withheld_reason"):
            report.extend(["", f"`{model}` risk was withheld. {item['withheld_reason']}."])
        for issue in item.get("fill_issues", []):
            report.append(f"- {issue['session_date']}: {issue['reason']} ({issue['detail']}).")
    report.extend([
        "", "## Limits", "",
        "These results cover one retrospective price window. They do not establish live fills, "
        "replicable forecasting skill, or an X sentiment edge.", "",
        "The replay database, input snapshots, model ledgers and CSVs are local research artifacts.",
    ])
    (out / "evaluation.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def evaluate(ticker: str, end: date, price_path: Path, out: Path,
             x_path: Path | None = None, x_manifest: Path | None = None,
             current_news: dict | None = None) -> dict:
    from . import __version__
    from .backtest import TradingFillError, trading_diagnostic
    from .metrics import matched_predictions
    from .x_export import coverage_audit

    prices, price_source = load_prices(price_path, ticker, end)
    warmup, start = evaluation_bounds(end)
    if current_news and current_news.get("source") == "Tavily":
        from .connectors.tavily import validate_news_context
        current_news = validate_news_context(current_news, ticker)
        current_news["note"] = "No usable headlines were returned."
    posts, x_source = _empty_posts_schema(), {}
    if x_path is not None and x_manifest is not None:
        from .x_export import load_x_export
        posts, x_source = load_x_export(x_path, x_manifest, ticker)
    usable_posts = posts if x_source.get("historical_eligible") else _empty_posts_schema()
    meta = {
        "mode": "historical_replay", "real_data_present": True, "warnings": [],
        "price_hash": price_source["sha256"], "adjustment_policy": price_source["policy"],
        "n_sessions": len(prices), "n_posts": len(posts),
    }
    cfg = Config(ticker=ticker, real_data_present=True, fail_on_missing_sessions=True,
                 max_allowed_missing_sessions=0, report_trading_diagnostic=False)
    with TemporaryDirectory(prefix="cwt-replay-") as scratch:
        result = run_pipeline(cfg, force_synthetic=False, out_dir=Path(scratch),
                              inputs=(prices, usable_posts, meta), evaluation_start=start)
    strict_posts = result["post_features"]
    if not strict_posts.empty:
        strict_posts = strict_posts.loc[strict_posts["session_date"].isin(prices["session_date"])]
        result["post_features"] = strict_posts
    forecasts = _forecast_rows(result)
    nowcasts = open_nowcasts(prices, cfg, start)
    nowcast_metrics = {
        model: {k: v for k, v in forecast_metrics(group).items() if k in {"n", "mae", "rmse"}}
        for model, group in nowcasts.groupby("model")
    }
    series = sentiment_series(result["panel"], posts, strict_posts, start, end)
    coverage = coverage_audit(posts, start, end, x_source)
    coverage["strict_eligible_by_session"] = [
        {"date": str(row.session_date), "posts": int(row.strict_posts)}
        for row in series.itertuples()
    ]
    active = {k: v for k, v in result["predictions"].items() if not v.empty}
    comparisons = matched_predictions(active)
    if not {"no_change", "price_only"} <= comparisons.keys() or any(
        frame.empty for frame in comparisons.values()
    ):
        raise DataError("No matched walk-forward price baseline comparison could be produced")
    metric_rows = []
    for model, frame in comparisons.items():
        for horizon, group in frame.groupby("horizon"):
            metric_rows.append({"model": model, "horizon": horizon, **forecast_metrics(group)})
    comparison = pd.DataFrame(metric_rows)

    risk, trades = {}, {}
    trade_cfg = replace(cfg, report_trading_diagnostic=True)
    for model, frame in comparisons.items():
        try:
            trades[model] = trading_diagnostic(frame, result["panel"], trade_cfg)
        except DataError as exc:
            trades[model] = pd.DataFrame()
            trades[model].attrs["withheld_reason"] = str(exc)
            if isinstance(exc, TradingFillError):
                trades[model].attrs["fill_issues"] = exc.issues
        risk[model] = trading_summary(trades[model],
                                      roundtrip_cost_bps=trade_cfg.diagnostic_roundtrip_cost_bps)
        if risk[model].get("withheld_reason"):
            log.warning("%s trading risk withheld: %s", model, risk[model]["withheld_reason"])

    x_available = "price_sentiment" in comparisons
    if x_available:
        note = "Source-attested X observations met the cutoff and matched walk-forward sample gates."
    elif x_source:
        note = "The supplied X export lacked verified historical availability or enough eligible coverage."
    else:
        note = "No authorized target-window X export was available for this replay."
    origins = comparisons["price_only"]["origin"]
    manifest = {
        "ticker": ticker, "model_version": __version__,
        "runtime_versions": {"python": sys.version.split()[0], "pandas": pd.__version__,
                             "numpy": version("numpy"), "matplotlib": version("matplotlib")},
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_start": str(start), "evaluation_end": str(end), "warmup_start": str(warmup),
        "evaluation_sessions": int((prices.index.date >= start).sum()),
        "warmup_sessions": int((prices.index.date < start).sum()),
        "first_oos_origin": origins.min().isoformat(), "last_oos_origin": origins.max().isoformat(),
        "prices": price_source, "historical_x_status": "AVAILABLE" if x_available else "WITHHELD",
        "historical_x_note": note, "x_export_rows_for_ticker": len(posts),
        "x_eligible_rows": len(strict_posts),
        "x_evaluation_eligible_rows": int(series["strict_posts"].sum()),
        "x_in_window_posts": coverage["in_window_posts"],
        "observed_close": float(prices.iloc[-1]["close"]),
        "sentiment_outlook": summarize_sentiment(series, end),
        "open_nowcast_metrics": nowcast_metrics,
        "comparison_sample": {
            model: {"candidate_rows": len(active[model]), "matched_rows": len(frame)}
            for model, frame in comparisons.items()
        },
        "current_news": current_news or {"note": "No current news source was enabled."},
        "risk": risk,
    }
    run_inputs = json.dumps(
        [ticker, str(end), price_source["sha256"], x_source, __version__],
        sort_keys=True, default=str,
    ).encode()
    run_id = hashlib.sha256(run_inputs).hexdigest()
    manifest["run_id"] = run_id
    manifest["x_source"] = x_source
    out.mkdir(parents=True, exist_ok=True)
    store_run(out / "replay.sqlite3", run_id, manifest, prices, posts, result,
              forecasts, comparisons, trades, nowcasts=nowcasts)
    forecasts.to_csv(out / "forecasts.csv", index=False)
    forecasts.loc[forecasts["is_prediction"]].to_csv(out / "post-close-forecasts.csv", index=False)
    nowcasts.to_csv(out / "open-nowcast.csv", index=False)
    series.to_csv(out / "x-sentiment-series.csv")
    (out / "x-coverage.json").write_text(json.dumps(coverage, indent=2, allow_nan=False) + "\n")
    news_snapshot = out / "tavily-news.json"
    if current_news and current_news.get("source") == "Tavily":
        news_snapshot.write_text(json.dumps(current_news, indent=2, allow_nan=False) + "\n")
    else:
        news_snapshot.unlink(missing_ok=True)
    comparison.to_csv(out / "model_comparison.csv", index=False)
    trade_rows = [frame.assign(model=model) for model, frame in trades.items() if not frame.empty]
    ledger = pd.concat(trade_rows, ignore_index=True) if trade_rows else pd.DataFrame(columns=["model"])
    ledger.to_csv(out / "trade_ledger.csv", index=False)
    _chart(out / "price-and-models.png", result["panel"], comparison, start)
    chart_sentiment(out / "x-versus-price.png", result["panel"], series)
    research = research_figure(ticker, result["panel"], series, comparisons, forecasts, nowcasts)
    research.savefig(out / "research-figure.png", dpi=145)
    _write_reports(out, manifest, forecasts, comparison, risk, nowcasts)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--ticker")
    choice.add_argument("--tickers", nargs="+")
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--prices-dir", type=Path, default=Path("private_data/prices"))
    parser.add_argument("--out", type=Path, default=Path("outputs_submission"))
    parser.add_argument("--x-export", type=Path)
    parser.add_argument("--x-manifest", type=Path)
    parser.add_argument("--fetch-prices", action="store_true")
    news_selection = parser.add_mutually_exclusive_group()
    news_selection.add_argument("--tavily-news", action="store_true",
                                help="Fetch current context outside the historical replay")
    news_selection.add_argument("--news-snapshot", type=Path, help="Replay a saved local Tavily capture")
    args = parser.parse_args(argv)
    tickers = [ticker.strip().upper() for ticker in (args.tickers or [args.ticker or "AAPL"])]
    if len(set(tickers)) != len(tickers) or any(not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,14}", t) for t in tickers):
        parser.error("Provide unique provider symbols for supported USD exchange-listed equities or ETFs")
    if bool(args.x_export) != bool(args.x_manifest) or (args.x_export and len(tickers) != 1):
        parser.error("Provide both X files for a single ticker")
    if args.news_snapshot and len(tickers) != 1:
        parser.error("A saved Tavily capture must match one ticker")
    failed = False
    for ticker in tickers:
        try:
            # Validate forward calendar coverage before provider I/O.
            day = args.end
            for _ in range(5):
                day = XNYSCalendar().next_trading_day(day)
            path = args.prices_dir / f"{ticker}.json"
            if args.fetch_prices and not path.exists():
                capture_prices(path, ticker, args.end)
            news = None
            if args.news_snapshot:
                from .connectors.tavily import validate_news_context
                news = validate_news_context(json.loads(args.news_snapshot.read_bytes()), ticker)
            elif args.tavily_news:
                from .connectors.tavily import fetch_news_context
                try:
                    news = fetch_news_context(ticker)
                    news["note"] = "No usable headlines were returned."
                except DataError as exc:
                    news = {"note": str(exc) + "."}
            result = evaluate(ticker, args.end, path, args.out / ticker,
                              args.x_export, args.x_manifest, news)
            print(f"{ticker}: {result['evaluation_sessions']} evaluation sessions, X {result['historical_x_status']}")
        except (CWTQuantError, ValueError, OSError, ImportError) as exc:
            print(f"{ticker}: evaluation failed: {exc}")
            failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())

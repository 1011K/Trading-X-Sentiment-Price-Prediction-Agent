"""
End-to-end research pipeline with full error handling.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from .backtest import trading_diagnostic, walk_forward
from .calendar import XNYSCalendar
from .config import Config
from .data import load_or_generate, write_manifest
from .exceptions import CWTQuantError, ConfigError, DataError, CoverageError
from .features import assemble_panel, build_post_features, aggregate_daily_sentiment
from .logging_utils import setup_logging, get_logger
from .report import write_report
from .forward import fit_latest_models, forecast_forward
from .validation import validate_prices, validate_posts, validate_panel


def _first_eligible_session(
    posts: pd.DataFrame, min_posts: int, min_sessions: int
) -> date | None:
    if posts.empty:
        return None
    posts_by_session = posts.groupby("session_date", sort=True).size()
    for session_count, (session, post_count) in enumerate(
        posts_by_session.cumsum().items(), start=1
    ):
        if session_count >= min_sessions and post_count >= min_posts:
            return session
    return None


def run_pipeline(
    cfg: Optional[Config] = None,
    force_synthetic: bool = True,
    out_dir: Optional[Path] = None,
    *,
    inputs: tuple[pd.DataFrame, pd.DataFrame, dict] | None = None,
    evaluation_start: date | None = None,
) -> Dict[str, Any]:
    cfg = cfg or Config()
    try:
        cfg.validate()
    except ConfigError:
        raise

    logger = setup_logging(cfg.log_level)
    log = get_logger("cwt_quant.pipeline")
    out_dir = Path(out_dir or cfg.outputs_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("=== CWT Quant pipeline start (status=EXPERIMENTAL) ===")
    log.info("ticker=%s seed=%s influence=%s", cfg.ticker, cfg.seed, cfg.enable_influence)

    cal = XNYSCalendar()
    warnings: list = []

    try:
        prices, posts, meta = (
            load_or_generate(cfg, force_synthetic=force_synthetic) if inputs is None else inputs
        )
        meta = dict(meta)
    except NotImplementedError:
        raise
    except Exception as exc:
        raise DataError(f"Data load failed: {exc}") from exc

    # Preserve source warnings already recorded by ingestion.
    warnings = list(meta.get("warnings", []))
    # Validate inputs
    try:
        warnings.extend(validate_prices(prices, cfg, cal))
        warnings.extend(validate_posts(posts, cfg))
    except DataError as exc:
        log.error("Data validation failed: %s", exc)
        raise

    meta["warnings"] = warnings
    for w in warnings:
        log.warning(w)

    # Features
    try:
        post_feat = build_post_features(posts, prices, cfg, cal)
        daily_sent = aggregate_daily_sentiment(post_feat, cfg)
        panel = assemble_panel(prices, daily_sent, cfg)
        validate_panel(panel, cfg)
    except Exception as exc:
        raise DataError(f"Feature construction failed: {exc}") from exc

    # Coverage gate for *any* sentiment model. Zero-filled unavailable external
    # history is not evidence of historical sentiment forecasting capability.
    covered_posts = post_feat
    if not post_feat.empty:
        covered_posts = post_feat.loc[post_feat["session_date"].isin(panel["session_date"])]
    sent_n = len(covered_posts)
    sent_sessions = covered_posts["session_date"].nunique() if sent_n else 0
    sentiment_start = _first_eligible_session(
        covered_posts, cfg.min_posts_for_sentiment, cfg.min_sessions_with_sentiment
    )
    sentiment_ok = sentiment_start is not None
    model_start_dates = {}
    if sentiment_start is not None:
        model_start_dates["price_sentiment"] = sentiment_start
    meta["sentiment_gate_passed"] = bool(sentiment_ok)
    meta["sentiment_posts_eligible"] = int(sent_n)
    meta["sentiment_sessions_eligible"] = int(sent_sessions)
    if not sentiment_ok:
        warnings.append(f"Sentiment model WITHHELD: only {sent_n} eligible posts "
                        f"across {sent_sessions} sessions, needs "
                        f"{cfg.min_posts_for_sentiment}/{cfg.min_sessions_with_sentiment}")
        log.warning(warnings[-1])
    meta["warnings"] = warnings

    # Coverage gate for influence
    influence_ok = False
    if sentiment_start is not None and cfg.enable_influence:
        valid = covered_posts.loc[covered_posts["influence_valid"]]
        total_posts = len(valid)
        sessions_with = valid["session_date"].nunique()
        influence_start = _first_eligible_session(
            valid, cfg.min_posts_for_influence, cfg.min_sessions_with_posts
        )
        influence_ok = influence_start is not None
        if influence_start is not None:
            model_start_dates["price_influence"] = max(sentiment_start, influence_start)
        meta["influence_gate_passed"] = influence_ok
        meta["influence_total_posts"] = total_posts
        meta["influence_sessions"] = sessions_with
        if not influence_ok:
            log.warning(
                "Influence coverage gate FAILED (posts=%d, sessions=%d). "
                "Required: posts>=%d, sessions>=%d. Influence model disabled.",
                total_posts,
                sessions_with,
                cfg.min_posts_for_influence,
                cfg.min_sessions_with_posts,
            )
        else:
            log.info("Influence coverage gate PASSED")

    # Walk-forward
    try:
        pred_tables = walk_forward(
            panel, cfg, enable_influence=influence_ok, enable_sentiment=sentiment_ok,
            model_start_dates=model_start_dates,
        )
        if evaluation_start is not None:
            pred_tables = {
                name: frame.loc[frame["origin"].dt.date >= evaluation_start].reset_index(drop=True)
                if not frame.empty else frame
                for name, frame in pred_tables.items()
            }
    except Exception as exc:
        raise CWTQuantError(f"Walk-forward failed: {exc}") from exc

    # Trading diagnostic
    trade_tables = {}
    for name, preds in pred_tables.items():
        try:
            trade_tables[name] = trading_diagnostic(preds, panel, cfg)
        except Exception as exc:
            log.warning("Trading diagnostic for %s failed: %s", name, exc)
            trade_tables[name] = pd.DataFrame()
            trade_tables[name].attrs["withheld_reason"] = str(exc)

    # Forward n+1..n+5 forecasts from latest origin
    try:
        fitted = fit_latest_models(panel, cfg, enable_influence=influence_ok, enable_sentiment=sentiment_ok)
        forward = forecast_forward(panel, fitted, cfg)
        if not forward.empty:
            forward.to_csv(out_dir / "forward_forecasts.csv", index=False)
            meta["forward_origin"] = str(forward["origin"].iloc[0])
    except Exception as exc:
        log.warning("Forward forecast failed: %s", exc)
        forward = pd.DataFrame()

    # Persist
    try:
        panel.to_csv(out_dir / "panel.csv")
        if daily_sent is not None and not daily_sent.empty:
            daily_sent.to_csv(out_dir / "daily_sentiment.csv", index=False)
        for name, df in pred_tables.items():
            if not df.empty:
                df.to_csv(out_dir / f"preds_{name}.csv", index=False)
        write_manifest(meta, cfg, out_dir)
    except Exception as exc:
        log.error("Failed to write outputs: %s", exc)
        raise

    report_path = write_report(cfg, meta, pred_tables, trade_tables, out_dir)

    log.info("Report written: %s", report_path)
    log.info("=== Pipeline complete ===")

    return {
        "config": cfg,
        "meta": meta,
        "panel": panel,
        "post_features": post_feat,
        "daily_sentiment": daily_sent,
        "predictions": pred_tables,
        "trades": trade_tables,
        "report_path": report_path,
        "influence_enabled": influence_ok,
        "sentiment_enabled": sentiment_ok,
        "forward": forward if "forward" in dir() else None,
        "warnings": warnings,
    }

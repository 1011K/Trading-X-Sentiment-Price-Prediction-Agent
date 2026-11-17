"""Research report generator. Forces honest language."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import pandas as pd

from .config import Config
from .metrics import summarize_by_horizon, trading_summary, forecast_metrics


def write_report(
    cfg: Config,
    meta: dict,
    pred_tables: Dict[str, pd.DataFrame],
    trade_tables: Dict[str, pd.DataFrame],
    out_dir: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = out_dir / f"CWT_Quant_Report_{ts}.md"

    lines = []
    lines.append("# CWT Quant — Research Report (Experimental)")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("Status: **EXPERIMENTAL / NOT VALIDATED FOR LIVE TRADING**")
    lines.append("")
    lines.append("## 0. Evidence boundaries")
    lines.append(f"- Mode: `{meta.get('mode')}`")
    lines.append(f"- Real data present: `{cfg.real_data_present}`")
    lines.append(f"- Price source hash: `{meta.get('price_hash')}`")
    lines.append(f"- Posts source hash: `{meta.get('posts_hash')}`")
    lines.append(f"- Sessions: {meta.get('n_sessions')}, Posts: {meta.get('n_posts')}")
    lines.append(f"- Adjustment policy: `{meta.get('adjustment_policy')}`")
    lines.append(f"- Influence gate passed: `{meta.get('influence_gate_passed')}`")
    lines.append(f"- Sentiment gate passed: `{meta.get('sentiment_gate_passed')}`")
    if meta.get("warnings"):
        lines.append(f"- Warnings ({len(meta['warnings'])}):")
        for w in meta["warnings"][:10]:
            lines.append(f"  - {w}")
    lines.append("- **WITHHELD**: genuine forecasting skill, commercial FinBERT rights, live X coverage, adjusted-price corporate-action audit.")
    lines.append("")
    lines.append("## 1. Configuration (locked)")
    lines.append(f"- Ticker: {cfg.ticker} / {cfg.exchange}")
    lines.append(f"- Horizons: {cfg.forecast_horizons}")
    lines.append(f"- Ridge alpha: {cfg.ridge_alpha} (fixed, no search on eval period)")
    lines.append(f"- Influence experiment enabled: {cfg.enable_influence}")
    lines.append("")
    lines.append("## 2. Forecast metrics by model and horizon")
    lines.append("")

    for name, df in pred_tables.items():
        lines.append(f"### Model: `{name}`")
        if df.empty:
            lines.append("_No predictions produced._")
            continue
        summ = summarize_by_horizon(df)
        if not summ.empty:
            lines.append("| " + " | ".join(summ.columns.astype(str)) + " |")
            lines.append("| " + " | ".join(["---"] * len(summ.columns)) + " |")
            for _, r in summ.iterrows():
                lines.append("| " + " | ".join(f"{v:.6g}" if isinstance(v, float) else str(v) for v in r) + " |")
        else:
            lines.append("_empty_")
        lines.append("")
        overall = forecast_metrics(df)
        lines.append(
            f"Overall (all horizons): MAE={overall.get('mae', float('nan')):.6f}, "
            f"RMSE={overall.get('rmse', float('nan')):.6f}, "
            f"Skill vs naïve={overall.get('skill_vs_naive', float('nan')):.4f}, "
            f"N={overall.get('n', 0)}"
        )
        lines.append("")

    lines.append("## 3. Trading diagnostic (idealized, not advice)")
    lines.append("Next-open long-or-cash, declared round-trip costs. Overnight gaps unresolved.")
    lines.append("")
    for name, trades in trade_tables.items():
        lines.append(f"### `{name}`")
        s = trading_summary(trades)
        for k, v in s.items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    lines.append("## 4. Red-team & leakage status")
    lines.append("- Session mapping (exact close → next, early close): enforced in calendar.")
    lines.append("- Engagement after origin close: influence weight forced neutral / excluded.")
    lines.append("- Train label rule `i + h <= t`: enforced in walk-forward.")
    lines.append("- Scaler fit on train fold only: enforced.")
    lines.append("- Sentiment model eligibility uses coverage through each forecast origin. Compare models on matching origins and horizons.")
    lines.append("- Cashtag gate + post_id dedup: enforced.")
    lines.append("")
    lines.append("## 5. Conclusion (honest)")
    if not cfg.real_data_present:
        lines.append("Synthetic validation only. **No claim of predictive skill or alpha.**")
        lines.append("Next required steps (P0): lawful 180-day X corpus with availability timestamps,")
        lines.append("verified adjusted/raw OHLC policy, external score provenance if used,")
        lines.append("genuine OOS run, and full adversarial audit on real data.")
    else:
        lines.append("Real-price data is present. Historical X sentiment coverage is not validated; "
                     "external post observations obtained after prior closes are excluded. "
                     "No evidence of an X-driven forecasting edge is claimed.")
    lines.append("")
    lines.append("---")
    lines.append("This report is research documentation, not investment advice.")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path

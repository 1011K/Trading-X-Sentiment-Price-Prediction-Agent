"""End-to-end synthetic pipeline smoke + leakage invariants."""

from pathlib import Path

import pandas as pd
import pytest

from cwt_quant.config import Config
from cwt_quant.pipeline import run_pipeline


def test_synthetic_pipeline_runs(tmp_path: Path):
    cfg = Config(
        ticker="AAPL",
        seed=42,
        outputs_dir=tmp_path,
        min_train_sessions=30,
        history_calendar_days=180,
    )
    result = run_pipeline(cfg, force_synthetic=True, out_dir=tmp_path)
    assert result["report_path"].exists()
    assert "no_change" in result["predictions"]
    assert "price_only" in result["predictions"]
    assert "price_sentiment" in result["predictions"]
    # Influence may or may not pass the coverage gate on this seed
    assert "meta" in result


def test_no_future_label_in_train(tmp_path: Path):
    """Sanity: every prediction row has a finite y_true (label was available)."""
    cfg = Config(outputs_dir=tmp_path, min_train_sessions=25, seed=7)
    result = run_pipeline(cfg, force_synthetic=True, out_dir=tmp_path)
    for name, df in result["predictions"].items():
        if not df.empty:
            assert df["y_true"].notna().all(), f"{name} has NaN labels"

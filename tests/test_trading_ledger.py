from datetime import date, time

import numpy as np
import pandas as pd
import pytest

from cwt_quant import metrics
from cwt_quant.backtest import trading_diagnostic
from cwt_quant.calendar import XNYSCalendar
from cwt_quant.config import Config
from cwt_quant.exceptions import DataError


@pytest.fixture
def sessions():
    index = XNYSCalendar().session_index(date(2025, 7, 2), date(2025, 7, 8))
    panel = pd.DataFrame(
        {"open": [120, 100, 150, 100], "close": [124, 90, 225, 120]},
        index=index,
    )
    preds = pd.DataFrame(
        {
            "origin": [index[2], index[0], index[1], index[0]],
            "horizon": [1, 1, 1, 5],
            "y_true": [0.2, -0.1, 0.5, 0.3],
            "y_hat": [0.1, 0.1, -0.1, 1.0],
        },
    )
    return panel, preds


def test_ledger_uses_true_next_session_cash_and_roundtrip_cost(sessions):
    panel, preds = sessions
    trades = trading_diagnostic(preds, panel, Config(ticker="TSLA"))

    assert trades["fill_date"].tolist() == [
        date(2025, 7, 3), date(2025, 7, 7), date(2025, 7, 8),
    ]
    assert trades["position"].tolist() == [1, 0, 1]
    assert trades.loc[0, "entry_at"].time() == time(9, 30)
    assert trades.loc[0, "exit_at"].time() == time(13)
    assert trades.loc[0, "entry_at"] > trades.loc[0, "origin"]
    assert trades.loc[0, "entry_price"] == 100
    assert trades.loc[0, "exit_price"] == 90
    assert pd.isna(trades.loc[1, "entry_price"])
    assert trades["cost"].tolist() == [0.001, 0.0, 0.001]
    assert trades["net_ret"].tolist() == pytest.approx([-0.101, 0, 0.199])
    assert trades["equity"].tolist() == pytest.approx([0.899, 0.899, 1.077901])

    summary = metrics.trading_summary(trades)
    assert summary["n_sessions"] == 3
    assert summary["n_trades"] == 2
    assert summary["hit_rate"] == 0.5
    assert summary["max_drawdown"] == pytest.approx(-0.101)
    assert summary["cumulative_net_ret"] == pytest.approx(0.077901)
    assert summary["approx_sharpe"] == pytest.approx(3.39722275)
    assert summary["approx_sortino"] == pytest.approx(8.89291917)


def test_cash_ledger_withholds_undefined_risk(sessions):
    panel, preds = sessions
    preds["y_hat"] = 0
    summary = metrics.trading_summary(trading_diagnostic(preds, panel, Config(ticker="TSLA")))
    assert summary["n_trades"] == 0
    assert summary["cumulative_net_ret"] == 0
    assert summary["max_drawdown"] == 0
    assert summary["approx_sharpe"] == "WITHHELD"
    assert summary["approx_sortino"] == "WITHHELD"
    assert metrics.trading_summary(pd.DataFrame())["max_drawdown"] == "WITHHELD"


@pytest.mark.parametrize("problem", ["price", "missing", "duplicate_fill", "duplicate_signal", "gap"])
def test_ledger_rejects_bad_series(sessions, problem):
    panel, preds = sessions
    if problem == "price":
        panel.loc[panel.index[1], "close"] = np.nan
    if problem == "missing":
        panel = panel.drop(panel.index[-1])
    if problem == "duplicate_fill":
        panel = pd.concat([panel, panel.iloc[[1]]])
    if problem == "duplicate_signal":
        preds = pd.concat([preds, preds.iloc[[0]]])
    if problem == "gap":
        preds = preds.drop(index=2)
    with pytest.raises(DataError):
        trading_diagnostic(preds, panel, Config(ticker="TSLA"))


def test_matched_predictions_uses_exact_common_finite_origin_horizon_pairs(sessions):
    _, preds = sessions
    second = preds.drop(index=1).copy()
    second.loc[0, "y_hat"] = np.inf
    matched = metrics.matched_predictions({"base": preds, "candidate": second})
    expected = list(preds.loc[[3, 2], ["origin", "horizon"]].itertuples(index=False, name=None))
    assert set(matched) == {"base", "candidate"}
    for values in matched.values():
        assert list(values[["origin", "horizon"]].itertuples(index=False, name=None)) == expected

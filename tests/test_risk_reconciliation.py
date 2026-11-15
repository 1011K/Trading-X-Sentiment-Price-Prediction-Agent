from datetime import date
from io import StringIO
from math import sqrt
from statistics import mean, stdev

import pandas as pd
import pytest

from cwt_quant.backtest import trading_diagnostic
from cwt_quant.calendar import XNYSCalendar
from cwt_quant.config import Config
from cwt_quant.metrics import trading_summary


@pytest.fixture
def ledger():
    index = XNYSCalendar().session_index(date(2026, 10, 29), date(2026, 11, 3))
    prices = pd.DataFrame({"open": [100] * 4, "close": [100, 99, 140, 103]}, index=index)
    signals = pd.DataFrame({"origin": index[:-1], "horizon": 1, "y_hat": [1, -1, 1]})
    return trading_diagnostic(signals, prices, Config(diagnostic_roundtrip_cost_bps=20))


@pytest.mark.parametrize("defect", [
    "reverse", "duplicate", "skip_session", "inconsistent_equity", "cash_profit",
    "waived_cost", "wrong_position", "wrong_price", "cash_fill", "naive_origin",
    "premature_fill", "bad_number",
])
def test_summary_withholds_inconsistent_daily_ledger(ledger, defect):
    if defect == "reverse":
        ledger = ledger.iloc[::-1]
    elif defect == "duplicate":
        ledger = pd.concat([ledger.iloc[[0]], ledger])
    elif defect == "skip_session":
        ledger = ledger.drop(index=1)
    elif defect == "inconsistent_equity":
        ledger.loc[0, "equity"] = 1.01
    elif defect == "cash_profit":
        ledger.loc[1, ["cash_ret", "net_ret"]] = 0.1
    elif defect == "waived_cost":
        ledger.loc[0, "cost"] = 0.0
    elif defect == "wrong_position":
        ledger.loc[0, "position"] = 0
    elif defect == "wrong_price":
        ledger.loc[0, "open_price"] = 55
    elif defect == "cash_fill":
        ledger.loc[1, "entry_at"] = ledger.loc[1, "session_open"]
    elif defect == "naive_origin":
        ledger["origin"] = ledger["origin"].dt.tz_localize(None)
    elif defect == "premature_fill":
        ledger.loc[0, "session_close"] = ledger.loc[0, "origin"]
    else:
        ledger["net_ret"] = ledger["net_ret"].astype(object)
        ledger.loc[0, "net_ret"] = "unavailable"

    summary = trading_summary(ledger)
    for key in ("max_drawdown", "approx_sharpe", "approx_sortino", "cumulative_net_ret"):
        assert summary[key] == "WITHHELD"
    assert summary["withheld_reason"]


def test_persisted_ledger_reconciles_across_dst_and_charges_configured_cost(ledger):
    saved = pd.read_csv(StringIO(ledger.to_csv(index=False)))
    summary = trading_summary(saved, roundtrip_cost_bps=20)
    returns = [-0.012, 0.0, 0.028]
    assert trading_summary(ledger) == summary
    assert summary["n_sessions"] == 3
    assert summary["n_trades"] == 2
    assert summary["approx_sharpe"] == pytest.approx(sqrt(252) * mean(returns) / stdev(returns))
    assert summary["approx_sortino"] == pytest.approx(sqrt(252) * mean(returns) / sqrt(0.012**2 / 3))
    assert summary["max_drawdown"] == pytest.approx(-0.012)
    assert summary["cumulative_net_ret"] == pytest.approx(0.988 * 1.028 - 1)
    assert trading_summary(saved, roundtrip_cost_bps=10)["max_drawdown"] == "WITHHELD"

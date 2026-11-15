from datetime import date

import pandas as pd
import pytest

from cwt_quant import backtest
from cwt_quant.calendar import XNYSCalendar
from cwt_quant.config import Config
from cwt_quant.exceptions import DataError
from cwt_quant.metrics import trading_summary


def _inputs():
    calendar = XNYSCalendar()
    index = calendar.session_index(date(2025, 7, 2), date(2025, 7, 8))
    panel = pd.DataFrame(
        {"open": [100.0, 110.0, 91.0, 120.0], "close": [95.0, 100.0, 100.0, 126.0]},
        index=index,
    )
    forecasts = pd.DataFrame({"origin": index[:-1], "horizon": 1, "y_hat": [0.0, -0.02, 0.01]})
    return panel, forecasts


@pytest.mark.parametrize(
    ("problem", "reason"),
    [("missing", "missing_fill_bar"), ("bad_price", "invalid_fill_prices")],
)
def test_missing_fill_reason_reaches_withheld_summary(problem, reason):
    panel, forecasts = _inputs()
    if problem == "missing":
        panel = panel.drop(panel.index[-1])
    else:
        panel.loc[panel.index[-1], "open"] = float("nan")
    with pytest.raises(DataError) as error:
        backtest.trading_diagnostic(forecasts, panel, Config())
    issue = error.value.issues[0]
    assert issue["session_date"] == "2025-07-08"
    assert issue["reason"] == reason

    discarded = pd.DataFrame()
    discarded.attrs.update(withheld_reason=str(error.value), fill_issues=error.value.issues)
    summary = trading_summary(discarded)
    assert summary["fill_issues"] == [issue]
    assert summary["n_cash_sessions"] == "WITHHELD"
    assert summary["n_sessions"] == 0


def test_cash_rows_are_not_counted_as_missing_fills_and_show_reconciled_interval():
    panel, forecasts = _inputs()
    ledger = backtest.trading_diagnostic(forecasts, panel, Config())
    summary = trading_summary(ledger)
    assert ledger.loc[ledger.position.eq(0), "entry_at"].isna().all()
    assert summary["n_cash_sessions"] == 2
    assert summary["n_trades"] == 1
    assert summary["first_fill_session"] == "2025-07-03"
    assert summary["last_fill_session"] == "2025-07-08"
    assert not summary.get("fill_issues")
    assert ledger.loc[0, "raw_oc_ret"] < 0 and ledger.loc[0, "net_ret"] == 0


def test_duplicate_price_columns_fail_with_diagnostic_instead_of_unpacking_error():
    panel, forecasts = _inputs()
    bad = pd.concat([panel, panel[["open"]]], axis=1)
    with pytest.raises(DataError, match="unique.*open.*close"):
        backtest.trading_diagnostic(forecasts, bad, Config())


def test_duplicate_forecast_columns_fail_with_diagnostic():
    panel, forecasts = _inputs()
    bad = pd.concat([forecasts, forecasts[["horizon"]]], axis=1)
    with pytest.raises(DataError, match="unique.*horizon"):
        backtest.trading_diagnostic(bad, panel, Config())


def test_positive_close_to_close_signal_can_lose_during_intraday_holding():
    panel, forecasts = _inputs()
    forecasts.loc[0, "y_hat"] = 0.02
    first = backtest.trading_diagnostic(forecasts, panel, Config()).iloc[0]
    assert panel.iloc[1]["close"] / panel.iloc[0]["close"] - 1 > 0
    assert first.position == 1
    assert first.raw_oc_ret == pytest.approx(100 / 110 - 1)
    assert first.net_ret == pytest.approx(100 / 110 - 1 - 0.001)


def test_walk_forward_refuses_unordered_origins_before_horizon_purge():
    index = XNYSCalendar().session_index(date(2025, 1, 2), date(2025, 4, 1))
    panel = pd.DataFrame({"close": 100.0, "ret_1": range(len(index)), "y_5": 0.01}, index=index)
    order = list(range(len(index)))
    # Row 43's h=5 label matures after origin 44. Moving it into the raw training
    # prefix previously bypassed the label cutoff while still preceding origin 44.
    order[20], order[43] = order[43], order[20]
    with pytest.raises(DataError, match="unique, chronological"):
        backtest.walk_forward(panel.iloc[order], Config(forecast_horizons=[5]))

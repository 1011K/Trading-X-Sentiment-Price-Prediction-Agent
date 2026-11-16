from datetime import date

import numpy as np
import pandas as pd

from cwt_quant.research_figure import research_figure


def test_research_figure_plots_observed_data_and_explicit_missing_x():
    sessions = pd.DatetimeIndex(["2026-11-12 16:00", "2026-11-13 16:00"], tz="America/New_York")
    prices = pd.DataFrame({"close": [100.0, 110.0]}, index=sessions)
    series = pd.DataFrame({
        "retrospective_posts": [0, 0], "strict_posts": [0, 0],
        "retrospective_mean": [np.nan, np.nan], "strict_mean": [np.nan, np.nan],
    }, index=sessions)
    predictions = pd.DataFrame({
        "origin": [sessions[0]], "horizon": [1], "close_t": [100.],
        "y_true": [np.log(1.1)], "y_hat": [np.log(1.08)],
    })
    forecasts = pd.DataFrame({
        "origin": [sessions[1], sessions[1]], "model": ["observed", "price_only"],
        "horizon": [0, 1], "forecast_close": [110., 112.], "is_prediction": [False, True],
    })
    nowcasts = pd.DataFrame({
        "target_session": [date(2026, 11, 13)], "model": ["price_only"], "forecast_close": [109.],
    })
    figure = research_figure("AAPL", prices, series, {"price_only": predictions}, forecasts, nowcasts)
    assert len(figure.axes) == 4
    assert any("X sentiment withheld" in text.get_text() for text in figure.axes[0].texts)
    assert not figure.axes[1].containers
    assert any("X activity withheld" in text.get_text() for text in figure.axes[1].texts)
    np.testing.assert_allclose(figure.axes[2].lines[0].get_ydata(), [110.])
    np.testing.assert_allclose(figure.axes[2].lines[1].get_ydata(), [108.])
    for artist, close in zip(figure.axes[3].collections, [109., 110.]):
        np.testing.assert_allclose(artist.get_offsets(), [[0, close]])
    np.testing.assert_allclose(figure.axes[3].lines[0].get_ydata(), [112.])

    series.loc[sessions[0], ["retrospective_posts", "retrospective_mean"]] = [2, 0.5]
    present = research_figure("AAPL", prices, series, {"price_only": predictions}, forecasts, nowcasts)
    assert len(present.axes) == 5  # secondary scale only when sentiment exists
    np.testing.assert_allclose(present.axes[-1].lines[0].get_ydata(), [0.5, np.nan])
    assert sum(bar.get_height() for bar in present.axes[1].patches) == 2

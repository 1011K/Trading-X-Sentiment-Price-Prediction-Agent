"""Build a four-panel research graphic from the saved replay records."""

from __future__ import annotations

import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from .calendar import XNYSCalendar

BLUE = "#1d5787"
GREEN = "#33785f"
PUMPKIN = "#af5b20"
INK = "#20344a"
LABELS = {
    "price_only": "Price Ridge",
    "no_change": "No change",
    "price_sentiment": "Price + X Ridge",
    "price_influence": "Influence Ridge",
}


def research_figure(ticker: str, panel: pd.DataFrame, sentiment: pd.DataFrame,
                    comparisons: dict[str, pd.DataFrame], forecasts: pd.DataFrame,
                    nowcasts: pd.DataFrame) -> Figure:
    figure = Figure(figsize=(12, 8), layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 2)
    price, activity, actual, forward = axes.ravel()
    window = panel.loc[sentiment.index]
    figure.suptitle(f"{ticker} research replay", color=INK, fontsize=19, fontweight="bold")

    price.plot(window.index, window["close"], color=BLUE, label="Observed close")
    price.set(title="Price and X sentiment", ylabel="Close (USD)")
    activity.set(title="X activity by aligned session", ylabel="Posts")
    x_series = [
        ("retrospective", "Retrospective X", GREEN),
        ("strict", "Cutoff-eligible X", PUMPKIN),
    ]
    if any(sentiment[f"{key}_mean"].notna().any() for key, _, _ in x_series):
        scores = price.twinx()
        scores.set(ylabel="Mean lexical score", ylim=(-1.1, 1.1))
        for key, label, color in x_series:
            sample = sentiment[f"{key}_mean"]
            if sample.notna().any():
                scores.plot(sample.index, sample, color=color, label=label, marker=".", linewidth=1)
        scores.legend(loc="lower right", frameon=False, fontsize=8)
    else:
        price.text(0.03, 0.96, "X sentiment withheld • no eligible observations",
                   transform=price.transAxes, color=INK, fontsize=9, va="top",
                   bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.9, "pad": 2})
    for key, label, color in x_series:
        counts = sentiment[f"{key}_posts"]
        nonzero = counts.gt(0)
        if nonzero.any():
            activity.bar(counts.index[nonzero], counts.loc[nonzero], label=label, color=color, alpha=0.8)
    if activity.containers:
        activity.legend(frameon=False, fontsize=8)
    else:
        activity.set_xticks([])
        activity.set_yticks([])
        activity.text(0.5, 0.52, "X activity withheld\nNo verified posts in this replay",
                      transform=activity.transAxes, ha="center", va="center", color=INK)

    actual.set(title="Next close • matched walk-forward", ylabel="Close (USD)")
    calendar = XNYSCalendar()
    plotted_observed = False
    for model, records in comparisons.items():
        subset = records.loc[records["horizon"].eq(1)].sort_values("origin")
        if subset.empty:
            continue
        settled = subset["origin"].map(
            lambda stamp: calendar.next_trading_day(pd.Timestamp(stamp).tz_convert(calendar.tz).date())
        )
        if not plotted_observed:
            actual.plot(settled, subset["close_t"] * np.exp(subset["y_true"]), color=INK, label="Observed")
            plotted_observed = True
        actual.plot(settled, subset["close_t"] * np.exp(subset["y_hat"]),
                    linewidth=1, linestyle="--", label=LABELS.get(model, model))
    if plotted_observed:
        actual.legend(frameon=False, fontsize=8)

    forward.set(title="Latest forecast by horizon", ylabel="Forecast close (USD)",
                xticks=range(6), xticklabels=[f"n+{i}" for i in range(6)])
    predicted = forecasts.loc[forecasts["is_prediction"]]
    for model, group in predicted.groupby("model", sort=False):
        group = group.sort_values("horizon")
        forward.plot(group["horizon"], group["forecast_close"], marker="o", markersize=4,
                     label=LABELS.get(model, model))
    observed = forecasts.loc[~forecasts["is_prediction"]].iloc[0]
    latest_open = nowcasts.loc[nowcasts["target_session"].eq(pd.Timestamp(observed.origin).date())]
    for model, group in latest_open.groupby("model", sort=False):
        forward.scatter([0], group["forecast_close"], marker="D", s=25,
                        label=f"Opening {LABELS.get(model, model)}")
    forward.scatter([0], [observed.forecast_close], marker="x", s=40, color=INK, label="Observed n+0")
    forward.legend(frameon=False, fontsize=8)

    for axis in axes.ravel():
        axis.grid(alpha=0.16)
        axis.spines[["top", "right"]].set_visible(False)
        axis.tick_params(labelsize=8)
    return figure

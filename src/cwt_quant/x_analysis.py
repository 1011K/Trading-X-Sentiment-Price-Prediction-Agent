"""Descriptive archived-text reporting, separate from model-ready X features."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .calendar import XNYSCalendar
from .features import lexical_sentiment


def sentiment_series(panel: pd.DataFrame, posts: pd.DataFrame, strict_posts: pd.DataFrame,
                     start: date, end: date) -> pd.DataFrame:
    window = panel.loc[panel["session_date"].between(start, end)]
    result = pd.DataFrame({"session_date": window["session_date"]}, index=window.index)
    for label in ("retrospective", "strict"):
        result[f"{label}_mean"] = float("nan")
        result[f"{label}_posts"] = 0
    if not posts.empty:
        calendar = XNYSCalendar()
        earliest = pd.Timestamp(start, tz=calendar.tz)
        latest = pd.Timestamp(end + timedelta(days=1), tz=calendar.tz)
        window_posts = posts.loc[posts["created_at"].ge(earliest) & posts["created_at"].lt(latest)]
        retrospective = pd.DataFrame({
            "session_date": window_posts["created_at"].map(calendar.map_timestamp_to_session),
            "score": window_posts["text"].map(lexical_sentiment),
        })
        by_day = retrospective.groupby("session_date")["score"].agg(["mean", "count"])
        result["retrospective_mean"] = result["session_date"].map(by_day["mean"])
        result["retrospective_posts"] = result["session_date"].map(by_day["count"]).fillna(0).astype(int)
    if not strict_posts.empty:
        by_day = strict_posts.groupby("session_date")["s_conversation"].agg(["mean", "count"])
        result["strict_mean"] = result["session_date"].map(by_day["mean"])
        result["strict_posts"] = result["session_date"].map(by_day["count"]).fillna(0).astype(int)
    return result


def summarize_sentiment(series: pd.DataFrame, end: date) -> dict:
    recent = series.loc[series["session_date"] >= end - timedelta(days=6)]
    summary = {"start": str(end - timedelta(days=6)), "end": str(end)}
    for label in ("retrospective", "strict"):
        n = int(recent[f"{label}_posts"].sum())
        valid = recent[f"{label}_posts"].gt(0)
        mean = (float((recent.loc[valid, f"{label}_mean"]
                       * recent.loc[valid, f"{label}_posts"]).sum()) / n) if n else None
        signal = "WITHHELD"
        if mean is not None:
            signal = "positive" if mean > 0 else "negative" if mean < 0 else "neutral"
        summary[label] = {"posts": n, "mean": mean, "lexical_direction": signal}
    return summary


def chart_sentiment(path: Path, panel: pd.DataFrame, series: pd.DataFrame) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(10, 8), layout="constrained")
    FigureCanvasAgg(figure)
    price, retro, strict = figure.subplots(3, 1, sharex=True)
    price.plot(series.index, panel.loc[series.index, "close"], color="#165283")
    price.set(ylabel="Close (USD)", title="Price versus X sentiment")
    for axis, label, title in (
        (retro, "retrospective", "Retrospective text scored by post creation time"),
        (strict, "strict", "Historically time-eligible text scored by market session"),
    ):
        axis.set(ylabel="Mean lexical score", title=title, ylim=(-1.1, 1.1))
        samples = series[f"{label}_mean"]
        if samples.notna().any():
            axis.plot(series.index, samples, color="#356e50", marker=".", linewidth=1)
            axis.axhline(0, color="grey", linewidth=0.7)
        else:
            axis.text(0.5, 0.5, "WITHHELD — no eligible observations",
                      transform=axis.transAxes, ha="center", va="center")
        axis.grid(alpha=0.18)
    figure.savefig(path, dpi=145)

"""Real-data connectors. X is optional and paid; prefer news + StockTwits + Reddit for cost."""

from .prices import fetch_daily_ohlc
from .news import fetch_news_headlines

__all__ = ["fetch_daily_ohlc", "fetch_news_headlines"]

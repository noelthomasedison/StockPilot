from __future__ import annotations

from typing import Dict

from langchain_core.tools import tool

from services.market_data import YFinanceProvider
from services.news_service import RSSNewsService
from services.analytics import compute_metrics

md = YFinanceProvider()
news = RSSNewsService()


@tool
def get_stock_price(ticker: str) -> Dict:
    """Get the latest close price and daily change for a ticker."""
    q = md.get_quote(ticker)
    return {
        "ticker": q.ticker,
        "price": q.price,
        "change": q.change,
        "change_pct": q.change_pct,
        "currency": q.currency,
    }


@tool
def get_stock_summary(ticker: str, period: str = "1mo") -> Dict:
    """
    One-call summary for period performance questions (free-tier optimized).
    Returns: price range + avg + start/end + return/volatility/drawdown.
    """
    df = md.get_history(ticker, period=period)
    close = df["Close"].astype(float)

    high = float(df["High"].max())
    low = float(df["Low"].min())
    avg_close = float(close.mean())
    start_close = float(close.iloc[0])
    end_close = float(close.iloc[-1])

    m = compute_metrics(df, period=period)

    return {
        "ticker": ticker.upper(),
        "period": period,
        "high": high,
        "low": low,
        "avg_close": avg_close,
        "start_close": start_close,
        "end_close": end_close,
        "return_pct": m.return_pct,
        "volatility_pct": m.volatility_pct,
        "max_drawdown_pct": m.max_drawdown_pct,
        "rows": int(len(df)),
    }


@tool
def get_stock_history(ticker: str, period: str = "1mo") -> Dict:
    """
    (Pro mode) Get historical OHLCV summary for a ticker over a period.
    period examples: '5d', '1mo', '3mo', '6mo', '1y'
    """
    df = md.get_history(ticker, period=period)
    close = df["Close"].astype(float)
    return {
        "ticker": ticker.upper(),
        "period": period,
        "high": float(df["High"].max()),
        "low": float(df["Low"].min()),
        "avg_close": float(close.mean()),
        "start_close": float(close.iloc[0]),
        "end_close": float(close.iloc[-1]),
        "rows": int(len(df)),
    }


@tool
def compute_stock_metrics(ticker: str, period: str = "1mo") -> Dict:
    """(Pro mode) Compute return %, volatility (annualized), and max drawdown over a period."""
    df = md.get_history(ticker, period=period)
    m = compute_metrics(df, period=period)
    return {
        "ticker": ticker.upper(),
        "period": period,
        "start_price": m.start_price,
        "end_price": m.end_price,
        "return_pct": m.return_pct,
        "volatility_pct": m.volatility_pct,
        "max_drawdown_pct": m.max_drawdown_pct,
    }


@tool
def compare_stocks(ticker_a: str, ticker_b: str, period: str = "1mo") -> Dict:
    """Compare two tickers on price, returns, and risk metrics over a period."""
    a_q = md.get_quote(ticker_a)
    b_q = md.get_quote(ticker_b)

    a_df = md.get_history(ticker_a, period=period)
    b_df = md.get_history(ticker_b, period=period)

    a_m = compute_metrics(a_df, period=period)
    b_m = compute_metrics(b_df, period=period)

    return {
        "period": period,
        "a": {
            "ticker": a_q.ticker,
            "price": a_q.price,
            "change_pct": a_q.change_pct,
            "return_pct": a_m.return_pct,
            "volatility_pct": a_m.volatility_pct,
            "max_drawdown_pct": a_m.max_drawdown_pct,
        },
        "b": {
            "ticker": b_q.ticker,
            "price": b_q.price,
            "change_pct": b_q.change_pct,
            "return_pct": b_m.return_pct,
            "volatility_pct": b_m.volatility_pct,
            "max_drawdown_pct": b_m.max_drawdown_pct,
        },
    }


@tool
def get_stock_news(ticker_or_query: str) -> Dict:
    """Get latest news headlines via RSS for a ticker or query string."""
    items = news.fetch(ticker_or_query, limit=5)
    return {
        "query": ticker_or_query,
        "items": [
            {"title": i.title, "link": i.link, "published": i.published, "source": i.source}
            for i in items
        ],
    }


# PHASE 3 PLUG-IN POINT:
# - Wrap tool bodies with retry/backoff
# - Add provider fallback (Alpha Vantage)
# - Add caching (avoid repeated yfinance calls)
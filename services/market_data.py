from __future__ import annotations

from dataclasses import dataclass
import pandas as pd
import yfinance as yf

from services.cache import cache


@dataclass
class Quote:
    ticker: str
    price: float
    change: float
    change_pct: float
    currency: str | None = None


class MarketDataProvider:
    """Abstract provider interface (Phase 3 plug-in point)."""

    def get_quote(self, ticker: str) -> Quote:
        raise NotImplementedError

    def get_history(self, ticker: str, period: str = "1mo") -> pd.DataFrame:
        raise NotImplementedError


class YFinanceProvider(MarketDataProvider):
    def get_quote(self, ticker: str) -> Quote:
        ticker = ticker.upper().strip()
        cache_key = f"quote:{ticker}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        t = yf.Ticker(ticker)

        # Fast path: try live-ish fields (may be missing)
        info = {}
        try:
            info = t.fast_info or {}
        except Exception:
            info = {}

        # Fallback to history for price/change
        hist = t.history(period="5d", interval="1d")
        if hist.empty or "Close" not in hist.columns:
            raise ValueError(f"No price data returned for ticker '{ticker}'.")

        last_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else last_close

        change = last_close - prev_close
        change_pct = (change / prev_close * 100.0) if prev_close != 0 else 0.0

        currency = None
        try:
            currency = info.get("currency")
        except Exception:
            currency = None

        q = Quote(
            ticker=ticker,
            price=last_close,
            change=change,
            change_pct=change_pct,
            currency=currency,
        )

        # Free-plan optimization: keep quotes cached briefly
        cache.set(cache_key, q, expire=60)  # 60 seconds
        return q

    def get_history(self, ticker: str, period: str = "1mo") -> pd.DataFrame:
        ticker = ticker.upper().strip()
        period = period.strip()
        cache_key = f"hist:{ticker}:{period}"

        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        t = yf.Ticker(ticker)
        df = t.history(period=period, interval="1d")

        if df.empty:
            raise ValueError(f"No historical data returned for ticker '{ticker}' with period '{period}'.")

        df = df.reset_index()

        # Cache history for longer (it doesn’t change often for past dates)
        cache.set(cache_key, df, expire=60 * 20)  # 20 minutes
        return df


# PHASE 3 PLUG-IN POINT:
# - Add AlphaVantageProvider(MarketDataProvider)
# - Add fallback logic: try yfinance -> if fails -> try Alpha Vantage
# - Add caching backends (redis) or smarter expiry policy
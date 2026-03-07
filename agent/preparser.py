from __future__ import annotations

import re
from typing import Optional, Dict, List


def map_period(text: str) -> Optional[str]:
    t = text.lower()

    # common phrases
    if "this month" in t or "past month" in t or "last month" in t:
        return "1mo"
    if "this week" in t or "past week" in t or "last week" in t:
        return "5d"
    if "last 3 months" in t or "past 3 months" in t or "3 months" in t:
        return "3mo"
    if "6 months" in t or "last 6 months" in t or "past 6 months" in t:
        return "6mo"
    if "this year" in t or "past year" in t or "last year" in t or "1 year" in t:
        return "1y"
    if "ytd" in t:
        return "ytd"

    # explicit tokens: 1mo, 3mo, etc.
    m = re.search(r"\b(5d|1mo|3mo|6mo|1y|2y|5y|ytd)\b", t)
    if m:
        return m.group(1)

    return None


def extract_tickers(text: str) -> List[str]:
    candidates = re.findall(r"\b[A-Za-z]{1,5}\b", text)
    tickers: List[str] = []
    for c in candidates:
        u = c.upper()
        if u in {"A", "I", "THE", "AND", "OR", "FOR", "IS", "ARE", "THIS", "MONTH", "NEWS"}:
            continue
        if re.fullmatch(r"[A-Z]{1,5}", u):
            tickers.append(u)

    out: List[str] = []
    for t in tickers:
        if t not in out:
            out.append(t)
    return out


def detect_intent(user_text: str) -> Optional[Dict]:
    """
    Returns a plan dict or None.
    Example:
      {"intent": "price", "ticker": "AAPL"}
      {"intent": "summary", "ticker": "AAPL", "period": "1mo"}
      {"intent": "compare", "a": "AAPL", "b": "TSLA", "period": "1mo"}
      {"intent": "news", "query": "AAPL"}
    """
    t = user_text.lower()
    tickers = extract_tickers(user_text)
    period = map_period(user_text) or "1mo"

    wants_news = any(k in t for k in ["news", "headline", "headlines", "latest updates", "what happened"])
    wants_compare = (" vs " in t) or ("versus" in t) or ("compare" in t)
    wants_price = any(k in t for k in ["price", "current price", "trading at", "quote"])
    wants_perf = any(k in t for k in ["performance", "return", "how did", "how has", "this month", "ytd", "3mo", "6mo", "1y"])

    if wants_compare and len(tickers) >= 2:
        return {"intent": "compare", "a": tickers[0], "b": tickers[1], "period": period}

    if wants_news:
        if len(tickers) >= 1:
            return {"intent": "news", "query": tickers[0]}
        return {"intent": "news", "query": user_text.strip()}

    if wants_perf and len(tickers) >= 1:
        return {"intent": "summary", "ticker": tickers[0], "period": period}

    if wants_price and len(tickers) >= 1:
        return {"intent": "price", "ticker": tickers[0]}

    if len(tickers) == 1 and user_text.strip().upper() == tickers[0]:
        return {"intent": "price", "ticker": tickers[0]}

    return None
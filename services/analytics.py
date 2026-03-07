from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class Metrics:
    period: str
    start_price: float
    end_price: float
    return_pct: float
    volatility_pct: float
    max_drawdown_pct: float


def compute_metrics(history_df: pd.DataFrame, period: str) -> Metrics:
    """
    history_df expected columns: ['Date', 'Close', ...] (from yfinance history reset_index()).
    """
    if history_df.empty or "Close" not in history_df.columns:
        raise ValueError("Invalid history data for metrics computation.")

    close = history_df["Close"].astype(float).to_numpy()
    if close.size < 2:
        raise ValueError("Not enough data points to compute metrics.")

    start_price = float(close[0])
    end_price = float(close[-1])

    ret_pct = ((end_price - start_price) / start_price * 100.0) if start_price != 0 else 0.0

    # daily log returns volatility
    rets = np.diff(np.log(close))
    vol = float(np.std(rets) * np.sqrt(252) * 100.0) if rets.size > 1 else 0.0

    # max drawdown
    running_max = np.maximum.accumulate(close)
    drawdowns = (close - running_max) / running_max
    max_dd = float(np.min(drawdowns) * 100.0)

    return Metrics(
        period=period,
        start_price=start_price,
        end_price=end_price,
        return_pct=ret_pct,
        volatility_pct=vol,
        max_drawdown_pct=max_dd,
    )
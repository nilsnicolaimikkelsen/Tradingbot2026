"""Pure technical indicator functions shared by strategies."""

import pandas as pd

from data.models import Candle


def rolling_mean(values: list[float], window: int) -> list[float | None]:
    series = pd.Series(values, dtype="float64").rolling(window=window).mean()
    return [None if pd.isna(v) else float(v) for v in series]


def average_true_range(candles: list[Candle], window: int = 14) -> list[float | None]:
    highs = pd.Series([c.high for c in candles], dtype="float64")
    lows = pd.Series([c.low for c in candles], dtype="float64")
    closes = pd.Series([c.close for c in candles], dtype="float64")
    prev_close = closes.shift(1)

    true_range = pd.concat(
        [
            highs - lows,
            (highs - prev_close).abs(),
            (lows - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr = true_range.rolling(window=window).mean()
    return [None if pd.isna(v) else float(v) for v in atr]

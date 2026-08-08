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


def relative_strength_index(candles: list[Candle], window: int = 14) -> list[float | None]:
    """Wilder's RSI: 100 when there have been no losses in the lookback, 0 when no gains."""
    closes = pd.Series([c.close for c in candles], dtype="float64")
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(avg_loss != 0, 100.0)
    rsi = rsi.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)
    return [None if pd.isna(v) else float(v) for v in rsi]


def bollinger_bands(
    values: list[float], window: int = 20, num_std: float = 2.0
) -> tuple[list[float | None], list[float | None], list[float | None]]:
    """Returns (lower, mid, upper) bands: mid is the rolling mean, bands are +/- num_std."""
    series = pd.Series(values, dtype="float64")
    mid = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    lower = mid - num_std * std
    upper = mid + num_std * std
    return (
        [None if pd.isna(v) else float(v) for v in lower],
        [None if pd.isna(v) else float(v) for v in mid],
        [None if pd.isna(v) else float(v) for v in upper],
    )

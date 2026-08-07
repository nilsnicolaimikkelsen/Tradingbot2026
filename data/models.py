"""Data models for market data used across the trading bot."""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Candle:
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def parse_ohlcv_row(symbol: str, timeframe: str, row: list) -> Candle:
    """Convert a raw ccxt OHLCV row ([ts_ms, o, h, l, c, v]) into a Candle."""
    ts_ms, open_, high, low, close, volume = row
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )

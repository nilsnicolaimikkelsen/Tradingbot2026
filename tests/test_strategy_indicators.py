from datetime import datetime, timezone

from data.models import Candle
from strategy.indicators import average_true_range, rolling_mean


def _candle(o, h, l, c):
    return Candle(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=datetime.now(timezone.utc),
        open=o,
        high=h,
        low=l,
        close=c,
        volume=1.0,
    )


def test_rolling_mean_basic():
    result = rolling_mean([1, 2, 3, 4, 5], window=3)

    assert result == [None, None, 2.0, 3.0, 4.0]


def test_average_true_range_basic():
    candles = [
        _candle(10, 12, 9, 11),
        _candle(11, 13, 10, 12),
        _candle(12, 14, 11, 13),
    ]

    result = average_true_range(candles, window=2)

    assert result[0] is None
    assert result[1] is not None and result[1] > 0
    assert result[2] is not None and result[2] > 0

from datetime import datetime, timezone

from data.models import Candle
from strategy.indicators import (
    average_true_range,
    bollinger_bands,
    relative_strength_index,
    rolling_mean,
)


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


def test_rsi_is_high_after_only_gains():
    candles = [_candle(p, p, p, p) for p in range(1, 20)]  # steadily rising closes

    result = relative_strength_index(candles, window=14)

    assert result[-1] is not None
    assert result[-1] == 100.0


def test_rsi_is_low_after_only_losses():
    candles = [_candle(p, p, p, p) for p in range(20, 1, -1)]  # steadily falling closes

    result = relative_strength_index(candles, window=14)

    assert result[-1] == 0.0


def test_rsi_is_mid_range_for_flat_prices():
    candles = [_candle(10, 10, 10, 10) for _ in range(20)]

    result = relative_strength_index(candles, window=14)

    assert result[-1] == 50.0


def test_bollinger_bands_bracket_the_mean():
    values = [10, 11, 9, 10, 12, 8, 10, 11, 9, 10]

    lower, mid, upper = bollinger_bands(values, window=5, num_std=2.0)

    assert lower[4] is not None
    assert lower[4] < mid[4] < upper[4]

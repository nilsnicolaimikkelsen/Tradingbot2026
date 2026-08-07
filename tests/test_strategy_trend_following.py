from datetime import datetime, timedelta, timezone

import pytest

from data.models import Candle
from strategy.trend_following import TrendFollowingStrategy


def _candles(prices):
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=base + timedelta(hours=i),
            open=p,
            high=p,
            low=p,
            close=p,
            volume=1.0,
        )
        for i, p in enumerate(prices)
    ]


def test_generates_entry_on_upward_crossover():
    prices = [10] * 5 + [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
    strategy = TrendFollowingStrategy(fast_window=2, slow_window=4)

    signals = strategy.generate_signals(_candles(prices))

    assert any(signals.entries)
    assert len(signals.entries) == len(prices)
    assert len(signals.exits) == len(prices)


def test_generates_exit_on_downward_crossover():
    prices = list(range(10, 30)) + list(range(30, 10, -1))
    strategy = TrendFollowingStrategy(fast_window=2, slow_window=4)

    signals = strategy.generate_signals(_candles(prices))

    assert any(signals.exits)


def test_rejects_invalid_windows():
    with pytest.raises(ValueError):
        TrendFollowingStrategy(fast_window=10, slow_window=5)

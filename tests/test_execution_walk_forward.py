from datetime import datetime, timedelta, timezone

import pytest

from data.models import Candle
from execution.walk_forward import walk_forward_windows


def _candles(n):
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=base + timedelta(hours=i),
            open=1.0,
            high=1.0,
            low=1.0,
            close=1.0,
            volume=1.0,
        )
        for i in range(n)
    ]


def test_test_windows_are_contiguous_and_non_overlapping_by_default():
    candles = _candles(20)

    windows = walk_forward_windows(candles, train_size=10, test_size=5)

    assert len(windows) == 2
    assert len(windows[0].train) == 10
    assert len(windows[0].test) == 5
    assert windows[0].train[0].timestamp == candles[0].timestamp
    # Default step == test_size, so train windows roll forward and overlap
    # (carrying prior history), but the out-of-sample test windows are
    # contiguous and never overlap each other.
    assert windows[0].test[-1].timestamp < windows[1].test[0].timestamp
    assert windows[0].test[-1].timestamp + timedelta(hours=1) == windows[1].test[0].timestamp


def test_rejects_non_positive_sizes():
    with pytest.raises(ValueError):
        walk_forward_windows(_candles(5), train_size=0, test_size=5)

import random
from datetime import datetime, timedelta, timezone

from data.models import Candle
from strategy.mean_reversion import MeanReversionStrategy


def _candles(prices):
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            symbol="EUR_USD",
            timeframe="daily",
            timestamp=base + timedelta(days=i),
            open=p,
            high=p,
            low=p,
            close=p,
            volume=0.0,
        )
        for i, p in enumerate(prices)
    ]


def test_enters_on_oversold_dip_within_a_range():
    random.seed(42)
    prices = [1.10 + random.uniform(-0.003, 0.003) for _ in range(60)]
    prices += [1.098, 1.093, 1.088, 1.085]  # ~2.3% pullback, typical for a ranging pair
    strategy = MeanReversionStrategy()

    signals = strategy.generate_signals(_candles(prices))

    assert any(signals.entries)


def test_does_not_enter_during_a_sustained_downtrend():
    random.seed(7)
    prices = []
    p = 1.15
    for _ in range(70):
        p *= 1 - 0.0015 + random.uniform(-0.001, 0.001)
        prices.append(p)
    strategy = MeanReversionStrategy()

    signals = strategy.generate_signals(_candles(prices))

    assert not any(signals.entries)


def test_exits_when_price_reverts_to_the_midline():
    random.seed(42)
    prices = [1.10 + random.uniform(-0.003, 0.003) for _ in range(60)]
    prices += [1.098, 1.093, 1.088, 1.085, 1.092, 1.098, 1.101]  # dip, then reverts
    strategy = MeanReversionStrategy()

    signals = strategy.generate_signals(_candles(prices))

    assert any(signals.exits)

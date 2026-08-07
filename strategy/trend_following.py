"""Simple moving-average crossover trend-following strategy."""

from data.models import Candle
from strategy.base import SignalSeries, Strategy
from strategy.indicators import rolling_mean


class TrendFollowingStrategy(Strategy):
    name = "trend_following"

    def __init__(self, fast_window: int = 20, slow_window: int = 50):
        if fast_window >= slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        self.fast_window = fast_window
        self.slow_window = slow_window

    def generate_signals(self, candles: list[Candle]) -> SignalSeries:
        closes = [c.close for c in candles]
        fast_ma = rolling_mean(closes, self.fast_window)
        slow_ma = rolling_mean(closes, self.slow_window)

        entries: list[bool] = []
        exits: list[bool] = []
        was_above: bool | None = None
        for fast, slow in zip(fast_ma, slow_ma):
            if fast is None or slow is None:
                entries.append(False)
                exits.append(False)
                continue
            is_above = fast > slow
            entries.append(is_above and was_above is False)
            exits.append((not is_above) and was_above is True)
            was_above = is_above

        return SignalSeries(entries=entries, exits=exits)

"""Mean-reversion delstrategi: buy oversold dips, but only when the longer trend
isn't clearly declining (avoids repeatedly buying into a real downtrend).

Fires far more often than trend-following by design -- it reacts to every stretch
away from the recent average, not just regime changes -- which is the point: it's
meant to be the higher-frequency half of the two uncorrelated delstrategier.
"""

from data.models import Candle
from strategy.base import SignalSeries, Strategy
from strategy.indicators import bollinger_bands, relative_strength_index, rolling_mean


class MeanReversionStrategy(Strategy):
    name = "mean_reversion"

    def __init__(
        self,
        bb_window: int = 20,
        bb_std: float = 2.0,
        rsi_window: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 55.0,
        trend_window: int = 50,
        trend_lookback: int = 10,
        trend_decline_threshold_pct: float = 0.01,
    ):
        self.bb_window = bb_window
        self.bb_std = bb_std
        self.rsi_window = rsi_window
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.trend_window = trend_window
        self.trend_lookback = trend_lookback
        self.trend_decline_threshold_pct = trend_decline_threshold_pct

    def generate_signals(self, candles: list[Candle]) -> SignalSeries:
        closes = [c.close for c in candles]
        lower, mid, _upper = bollinger_bands(closes, self.bb_window, self.bb_std)
        rsi = relative_strength_index(candles, self.rsi_window)
        trend = rolling_mean(closes, self.trend_window)

        entries: list[bool] = []
        exits: list[bool] = []
        for i in range(len(closes)):
            prior_trend = trend[i - self.trend_lookback] if i >= self.trend_lookback else None
            if lower[i] is None or rsi[i] is None or trend[i] is None or prior_trend is None:
                entries.append(False)
                exits.append(False)
                continue

            oversold = closes[i] <= lower[i] and rsi[i] <= self.rsi_oversold
            # The trend MA itself falling meaningfully over the lookback means the
            # longer-term trend is genuinely down, not just today's price dipping.
            trend_declining = trend[i] < prior_trend * (1 - self.trend_decline_threshold_pct)
            entries.append(oversold and not trend_declining)

            reverted = closes[i] >= mid[i] or rsi[i] >= self.rsi_overbought
            exits.append(reverted)

        return SignalSeries(entries=entries, exits=exits)

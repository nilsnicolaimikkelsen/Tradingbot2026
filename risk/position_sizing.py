"""Volatility-adjusted position sizing: risk a fixed fraction of capital per trade."""


def volatility_adjusted_size(capital: float, risk_pct: float, stop_distance: float) -> float:
    """Size (in units of the asset) so that a move of `stop_distance` risks `risk_pct` of capital.

    `stop_distance` is a price-denominated volatility measure (e.g. ATR) used as the
    assumed distance to a stop-loss.
    """
    if stop_distance <= 0 or capital <= 0 or risk_pct <= 0:
        return 0.0
    risk_amount = capital * risk_pct
    return risk_amount / stop_distance

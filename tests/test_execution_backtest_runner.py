import asyncio
from datetime import datetime, timedelta, timezone

from data.models import Candle
from execution.backtest_runner import run_backtest
from risk.gatekeeper import RiskGatekeeper, RiskLimits
from risk.kill_switch import KillSwitch
from strategy.trend_following import TrendFollowingStrategy


def _candles(prices):
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            symbol="BTC/USDT",
            timeframe="1h",
            timestamp=base + timedelta(hours=i),
            open=p,
            high=p * 1.01,
            low=p * 0.99,
            close=p,
            volume=1.0,
        )
        for i, p in enumerate(prices)
    ]


def test_run_backtest_on_rise_and_fall_completes_a_trade():
    prices = [100] * 20 + list(range(100, 150)) + list(range(150, 99, -1))
    strategy = TrendFollowingStrategy(fast_window=5, slow_window=15)
    gatekeeper = RiskGatekeeper(RiskLimits(max_position_risk_pct=0.02), KillSwitch())

    metrics = asyncio.run(run_backtest(strategy, gatekeeper, _candles(prices), starting_cash=10_000))

    assert metrics.num_trades >= 1
    assert isinstance(metrics.total_return_pct, float)
    assert 0.0 <= metrics.max_drawdown_pct <= 1.0
    assert 0.0 <= metrics.win_rate <= 1.0


def test_run_backtest_on_flat_prices_makes_no_trades():
    prices = [100] * 40
    strategy = TrendFollowingStrategy(fast_window=5, slow_window=15)
    gatekeeper = RiskGatekeeper(RiskLimits(), KillSwitch())

    metrics = asyncio.run(run_backtest(strategy, gatekeeper, _candles(prices), starting_cash=10_000))

    assert metrics.num_trades == 0
    assert metrics.total_return_pct == 0.0

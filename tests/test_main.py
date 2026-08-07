import asyncio
from datetime import datetime, timedelta, timezone

from data.models import Candle
from execution.backtest import BacktestExecutor
from execution.portfolio import Portfolio
from main import DailyRiskWindow, run_once
from risk.gatekeeper import RiskGatekeeper, RiskLimits
from risk.kill_switch import KillSwitch
from strategy.trend_following import TrendFollowingStrategy


def _candles(prices):
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            symbol="EUR_USD",
            timeframe="daily",
            timestamp=base + timedelta(days=i),
            open=p,
            high=p * 1.01,
            low=p * 0.99,
            close=p,
            volume=0.0,
        )
        for i, p in enumerate(prices)
    ]


class _FakeClient:
    def __init__(self, candles):
        self._candles = candles

    async def fetch_candles(self, instrument, granularity="daily", count=500):
        return self._candles


class _FakeStore:
    def __init__(self, candles):
        self._candles = candles

    async def upsert_candles(self, candles):
        pass

    async def get_candles(self, instrument, timeframe, start, end):
        return self._candles


def _setup(candles):
    client = _FakeClient(candles)
    store = _FakeStore(candles)
    strategy = TrendFollowingStrategy(fast_window=5, slow_window=15)
    gatekeeper = RiskGatekeeper(RiskLimits(max_position_risk_pct=0.02), KillSwitch())
    risk_window = DailyRiskWindow(gatekeeper)
    executor = BacktestExecutor()
    portfolio = Portfolio(starting_cash=10_000.0)
    return client, store, strategy, gatekeeper, risk_window, executor, portfolio


def test_run_once_enters_position_on_fresh_entry_signal():
    # Crossover lands exactly on the last candle (verified empirically).
    prices = ([100] * 20 + list(range(100, 140)))[:22]
    args = _setup(_candles(prices))

    in_position = asyncio.run(run_once(*args, "EUR_USD", False))

    assert in_position is True
    assert args[6].position > 0


def test_run_once_returns_false_when_not_enough_history():
    args = _setup(_candles([100] * 5))

    in_position = asyncio.run(run_once(*args, "EUR_USD", False))

    assert in_position is False
    assert args[6].position == 0


def test_run_once_stays_flat_without_a_signal():
    args = _setup(_candles([100] * 30))

    in_position = asyncio.run(run_once(*args, "EUR_USD", False))

    assert in_position is False
    assert args[6].position == 0

import asyncio
from datetime import datetime, timedelta, timezone

from data.alpha_vantage import AlphaVantageError
from data.models import Candle
from execution.backtest import BacktestExecutor
from execution.portfolio import Portfolio
from main import DailyRiskWindow, TradingLine, check_all, evaluate_line
from risk.gatekeeper import RiskGatekeeper, RiskLimits
from risk.kill_switch import KillSwitch
from strategy.trend_following import TrendFollowingStrategy


def _candles(instrument, prices):
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return [
        Candle(
            symbol=instrument,
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


def _line(instrument="EUR_USD", fast_window=5, slow_window=15):
    strategy = TrendFollowingStrategy(fast_window=fast_window, slow_window=slow_window)
    gatekeeper = RiskGatekeeper(RiskLimits(max_position_risk_pct=0.02), KillSwitch())
    return TradingLine(
        instrument=instrument,
        strategy=strategy,
        gatekeeper=gatekeeper,
        risk_window=DailyRiskWindow(gatekeeper),
        portfolio=Portfolio(starting_cash=10_000.0),
    )


def test_evaluate_line_enters_position_on_fresh_entry_signal():
    # Crossover lands exactly on the last candle (verified empirically); the long
    # flat lead-in is needed to clear MIN_HISTORY_WARMUP.
    prices = ([100] * 60 + list(range(100, 140)))[:62]
    line = _line()
    executor = BacktestExecutor()

    result = asyncio.run(evaluate_line(executor, line, _candles("EUR_USD", prices)))

    assert result.in_position is True
    assert result.last_action == "bought"
    assert line.portfolio.position > 0


def test_evaluate_line_returns_not_enough_history():
    line = _line()
    executor = BacktestExecutor()

    result = asyncio.run(evaluate_line(executor, line, _candles("EUR_USD", [100] * 5)))

    assert result.in_position is False
    assert result.last_action == "not_enough_history"
    assert line.portfolio.position == 0


def test_evaluate_line_stays_flat_without_a_signal():
    line = _line()
    executor = BacktestExecutor()

    result = asyncio.run(evaluate_line(executor, line, _candles("EUR_USD", [100] * 60)))

    assert result.in_position is False
    assert result.last_action == "no_signal"
    assert line.portfolio.position == 0


class _FakeClient:
    def __init__(self, candles_by_instrument):
        self._candles_by_instrument = candles_by_instrument
        self.fetch_calls = []

    async def fetch_candles(self, instrument, granularity="daily", count=500):
        self.fetch_calls.append(instrument)
        return self._candles_by_instrument[instrument]


class _FakeStore:
    def __init__(self, candles_by_instrument):
        self._candles_by_instrument = candles_by_instrument

    async def upsert_candles(self, candles):
        pass

    async def get_candles(self, instrument, timeframe, start, end):
        return self._candles_by_instrument[instrument]


def test_check_all_fetches_each_instrument_once_regardless_of_strategy_count():
    prices = [100] * 30
    candles_by_instrument = {
        "EUR_USD": _candles("EUR_USD", prices),
        "GBP_USD": _candles("GBP_USD", prices),
    }
    client = _FakeClient(candles_by_instrument)
    store = _FakeStore(candles_by_instrument)
    executor = BacktestExecutor()
    lines = [
        _line("EUR_USD"),
        _line("EUR_USD", fast_window=3, slow_window=8),  # a 2nd strategy on the same pair
        _line("GBP_USD"),
    ]

    results, errors = asyncio.run(check_all(client, store, executor, lines))

    assert len(results) == 3
    assert errors == []
    assert sorted(client.fetch_calls) == ["EUR_USD", "GBP_USD"]


class _FailingClient:
    def __init__(self, failing_instrument, candles_by_instrument):
        self._failing_instrument = failing_instrument
        self._candles_by_instrument = candles_by_instrument

    async def fetch_candles(self, instrument, granularity="daily", count=500):
        if instrument == self._failing_instrument:
            raise AlphaVantageError("rate limited")
        return self._candles_by_instrument[instrument]


def test_check_all_isolates_a_fetch_failure_to_one_instrument():
    prices = [100] * 30
    candles_by_instrument = {
        "EUR_USD": _candles("EUR_USD", prices),
        "GBP_USD": _candles("GBP_USD", prices),
    }
    client = _FailingClient("EUR_USD", candles_by_instrument)
    store = _FakeStore(candles_by_instrument)
    executor = BacktestExecutor()
    lines = [_line("EUR_USD"), _line("GBP_USD")]

    results, errors = asyncio.run(check_all(client, store, executor, lines))

    assert len(results) == 1
    assert results[0].line_id == "GBP_USD:trend_following"
    assert len(errors) == 1
    assert "EUR_USD" in errors[0]

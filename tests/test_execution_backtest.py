import asyncio

import pytest

from execution.backtest import BacktestExecutor
from risk.gatekeeper import ApprovedOrder


def test_buy_fill_applies_positive_slippage_and_fee():
    executor = BacktestExecutor(fee_pct=0.001, slippage_pct=0.0005)
    order = ApprovedOrder(symbol="BTC/USDT", side="buy", size=1.0)

    fill = asyncio.run(executor.execute(order, market_price=100.0))

    assert fill.price == pytest.approx(100.05)
    assert fill.fee == pytest.approx(100.05 * 0.001)


def test_sell_fill_applies_negative_slippage():
    executor = BacktestExecutor(fee_pct=0.001, slippage_pct=0.0005)
    order = ApprovedOrder(symbol="BTC/USDT", side="sell", size=1.0)

    fill = asyncio.run(executor.execute(order, market_price=100.0))

    assert fill.price == pytest.approx(99.95)

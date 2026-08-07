"""Simulated execution against historical prices, with fee and slippage modeling."""

from execution.base import Executor, Fill
from risk.gatekeeper import ApprovedOrder


class BacktestExecutor(Executor):
    def __init__(self, fee_pct: float = 0.001, slippage_pct: float = 0.0005):
        self.fee_pct = fee_pct
        self.slippage_pct = slippage_pct

    async def execute(self, order: ApprovedOrder, market_price: float) -> Fill:
        direction = 1 if order.side == "buy" else -1
        fill_price = market_price * (1 + direction * self.slippage_pct)
        fee = fill_price * order.size * self.fee_pct
        return Fill(symbol=order.symbol, side=order.side, size=order.size, price=fill_price, fee=fee)

"""Execution layer interface: the only place that talks to a broker/exchange API.

Swapped per mode (backtest/paper/live) — strategy and risk layers are unaware of the mode.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from risk.gatekeeper import ApprovedOrder


@dataclass(frozen=True)
class Fill:
    symbol: str
    side: str
    size: float
    price: float
    fee: float


class Executor(ABC):
    @abstractmethod
    async def execute(self, order: ApprovedOrder, market_price: float) -> Fill:
        raise NotImplementedError

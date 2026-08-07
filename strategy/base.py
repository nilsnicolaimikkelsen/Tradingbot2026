"""Base interface for delstrategier: candles in, entry/exit signals out. No order calls here."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from data.models import Candle


@dataclass(frozen=True)
class SignalSeries:
    entries: list[bool]
    exits: list[bool]


class Strategy(ABC):
    name: str

    @abstractmethod
    def generate_signals(self, candles: list[Candle]) -> SignalSeries:
        raise NotImplementedError

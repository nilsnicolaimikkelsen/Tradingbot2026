import asyncio

import data.exchange as exchange_module
from data.exchange import ExchangeClient


class _FakeCcxtExchange:
    def __init__(self, config):
        self.config = config
        self.sandbox_mode = False
        self.fetch_calls = []

    def set_sandbox_mode(self, enabled):
        self.sandbox_mode = enabled

    async def fetch_ohlcv(self, symbol, timeframe="1h", since=None, limit=500):
        self.fetch_calls.append((symbol, timeframe, since, limit))
        return [[1700000000000, 1.0, 2.0, 0.5, 1.5, 10.0]]

    async def close(self):
        pass


def test_fetch_ohlcv_returns_parsed_candles(monkeypatch):
    monkeypatch.setattr(exchange_module.ccxt, "binance", _FakeCcxtExchange)
    client = ExchangeClient("binance", sandbox=True)

    candles = asyncio.run(client.fetch_ohlcv("BTC/USDT", timeframe="1h"))

    assert len(candles) == 1
    assert candles[0].symbol == "BTC/USDT"
    assert candles[0].timeframe == "1h"
    assert candles[0].close == 1.5
    assert client._exchange.sandbox_mode is True
    assert client._exchange.fetch_calls == [("BTC/USDT", "1h", None, 500)]

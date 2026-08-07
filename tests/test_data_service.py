import asyncio

from data.service import sync_candles


class _FakeExchange:
    def __init__(self, candles):
        self._candles = candles
        self.calls = []

    async def fetch_ohlcv(self, symbol, timeframe="1h", since=None, limit=500):
        self.calls.append((symbol, timeframe, since, limit))
        return self._candles


class _FakeStore:
    def __init__(self):
        self.saved = []

    async def upsert_candles(self, candles):
        self.saved.extend(candles)


def test_sync_candles_fetches_and_persists():
    fake_candles = ["candle-1", "candle-2"]
    exchange = _FakeExchange(fake_candles)
    store = _FakeStore()

    count = asyncio.run(sync_candles(exchange, store, "BTC/USDT", timeframe="1h"))

    assert count == 2
    assert store.saved == fake_candles
    assert exchange.calls == [("BTC/USDT", "1h", None, 500)]

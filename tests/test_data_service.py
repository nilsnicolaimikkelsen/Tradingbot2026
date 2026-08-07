import asyncio

from data.service import sync_candles


class _FakeClient:
    def __init__(self, candles):
        self._candles = candles
        self.calls = []

    async def fetch_candles(self, instrument, granularity="H1", count=500):
        self.calls.append((instrument, granularity, count))
        return self._candles


class _FakeStore:
    def __init__(self):
        self.saved = []

    async def upsert_candles(self, candles):
        self.saved.extend(candles)


def test_sync_candles_fetches_and_persists():
    fake_candles = ["candle-1", "candle-2"]
    client = _FakeClient(fake_candles)
    store = _FakeStore()

    count = asyncio.run(sync_candles(client, store, "EUR_USD", granularity="H1"))

    assert count == 2
    assert store.saved == fake_candles
    assert client.calls == [("EUR_USD", "H1", 500)]

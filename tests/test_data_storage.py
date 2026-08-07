import asyncio
from datetime import datetime, timezone

from data.models import Candle
from data.storage import CandleStore


class _FakeConnection:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, sql, *args):
        pass

    async def executemany(self, sql, rows):
        for symbol, timeframe, ts, open_, high, low, close, volume in rows:
            self._rows[(symbol, timeframe, ts)] = {
                "symbol": symbol,
                "timeframe": timeframe,
                "ts": ts,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }

    async def fetch(self, sql, symbol, timeframe, start, end):
        return [
            row
            for (s, tf, ts), row in self._rows.items()
            if s == symbol and tf == timeframe and start <= ts <= end
        ]


class _FakeAcquireCtx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class _FakePool:
    def __init__(self):
        self.rows = {}

    def acquire(self):
        return _FakeAcquireCtx(_FakeConnection(self.rows))


def test_upsert_and_get_candles_roundtrip():
    store = CandleStore("postgresql://fake")
    store._pool = _FakePool()
    candle = Candle(
        symbol="BTC/USDT",
        timeframe="1h",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        open=1.0,
        high=2.0,
        low=0.5,
        close=1.5,
        volume=10.0,
    )

    async def run():
        await store.upsert_candles([candle])
        return await store.get_candles(
            "BTC/USDT",
            "1h",
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            datetime(2025, 1, 1, tzinfo=timezone.utc),
        )

    result = asyncio.run(run())

    assert result == [candle]


def test_upsert_candles_noop_on_empty_list():
    store = CandleStore("postgresql://fake")
    store._pool = _FakePool()

    asyncio.run(store.upsert_candles([]))

    assert store._pool.rows == {}

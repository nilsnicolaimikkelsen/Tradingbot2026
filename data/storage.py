"""TimescaleDB-backed storage for OHLCV candles."""

from datetime import datetime

import asyncpg

from data.models import Candle

CREATE_EXTENSION_SQL = "CREATE EXTENSION IF NOT EXISTS timescaledb;"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (symbol, timeframe, ts)
);
"""

CREATE_HYPERTABLE_SQL = "SELECT create_hypertable('candles', 'ts', if_not_exists => TRUE);"

UPSERT_SQL = """
INSERT INTO candles (symbol, timeframe, ts, open, high, low, close, volume)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (symbol, timeframe, ts) DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    volume = EXCLUDED.volume
"""

SELECT_SQL = """
SELECT symbol, timeframe, ts, open, high, low, close, volume
FROM candles
WHERE symbol = $1 AND timeframe = $2 AND ts >= $3 AND ts <= $4
ORDER BY ts ASC
"""


class CandleStore:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn)
        async with self._pool.acquire() as conn:
            await conn.execute(CREATE_EXTENSION_SQL)
            await conn.execute(CREATE_TABLE_SQL)
            await conn.execute(CREATE_HYPERTABLE_SQL)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()

    async def upsert_candles(self, candles: list[Candle]) -> None:
        if not candles:
            return
        rows = [(c.symbol, c.timeframe, c.timestamp, c.open, c.high, c.low, c.close, c.volume) for c in candles]
        async with self._pool.acquire() as conn:
            await conn.executemany(UPSERT_SQL, rows)

    async def get_candles(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> list[Candle]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(SELECT_SQL, symbol, timeframe, start, end)
        return [
            Candle(
                symbol=row["symbol"],
                timeframe=row["timeframe"],
                timestamp=row["ts"],
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            for row in rows
        ]

"""Orchestration: fetch candles from OANDA and persist them."""

from data.oanda import OandaClient
from data.storage import CandleStore


async def sync_candles(
    client: OandaClient,
    store: CandleStore,
    instrument: str,
    granularity: str = "H1",
    count: int = 500,
) -> int:
    """Fetch OHLCV candles from OANDA and upsert them into storage. Returns the number fetched."""
    candles = await client.fetch_candles(instrument, granularity=granularity, count=count)
    await store.upsert_candles(candles)
    return len(candles)

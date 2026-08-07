"""Orchestration: fetch candles from Alpha Vantage and persist them."""

from data.alpha_vantage import AlphaVantageClient
from data.storage import CandleStore


async def sync_candles(
    client: AlphaVantageClient,
    store: CandleStore,
    instrument: str,
    granularity: str = "60min",
    count: int = 500,
) -> int:
    """Fetch OHLCV candles from Alpha Vantage and upsert them into storage. Returns the number fetched."""
    candles = await client.fetch_candles(instrument, granularity=granularity, count=count)
    await store.upsert_candles(candles)
    return len(candles)

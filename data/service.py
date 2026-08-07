"""Orchestration: fetch candles from an exchange and persist them."""

from data.exchange import ExchangeClient
from data.storage import CandleStore


async def sync_candles(
    exchange: ExchangeClient,
    store: CandleStore,
    symbol: str,
    timeframe: str = "1h",
    since: int | None = None,
    limit: int = 500,
) -> int:
    """Fetch OHLCV candles from the exchange and upsert them into storage. Returns the number fetched."""
    candles = await exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
    await store.upsert_candles(candles)
    return len(candles)

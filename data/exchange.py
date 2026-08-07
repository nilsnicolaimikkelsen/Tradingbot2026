"""Thin async wrapper around ccxt for fetching OHLCV market data."""

import ccxt.async_support as ccxt

from data.models import Candle, parse_ohlcv_row


class ExchangeClient:
    def __init__(
        self,
        exchange_id: str,
        api_key: str | None = None,
        api_secret: str | None = None,
        sandbox: bool = True,
    ):
        exchange_class = getattr(ccxt, exchange_id)
        self._exchange = exchange_class(
            {
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
            }
        )
        if sandbox:
            self._exchange.set_sandbox_mode(True)

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: int | None = None,
        limit: int = 500,
    ) -> list[Candle]:
        raw_rows = await self._exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
        return [parse_ohlcv_row(symbol, timeframe, row) for row in raw_rows]

    async def close(self) -> None:
        await self._exchange.close()

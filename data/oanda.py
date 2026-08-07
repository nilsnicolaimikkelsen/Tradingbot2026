"""Async client for OANDA's v20 REST API (candles for forex/CFD instruments)."""

from datetime import datetime

import aiohttp

from data.models import Candle

PRACTICE_BASE_URL = "https://api-fxpractice.oanda.com"
LIVE_BASE_URL = "https://api-fxtrade.oanda.com"


class OandaClient:
    def __init__(self, api_token: str, practice: bool = True):
        self._api_token = api_token
        self._base_url = PRACTICE_BASE_URL if practice else LIVE_BASE_URL
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(headers={"Authorization": f"Bearer {self._api_token}"})
        return self._session

    async def fetch_candles(self, instrument: str, granularity: str = "H1", count: int = 500) -> list[Candle]:
        session = await self._get_session()
        url = f"{self._base_url}/v3/instruments/{instrument}/candles"
        params = {"granularity": granularity, "count": str(count), "price": "M"}

        async with session.get(url, params=params) as response:
            response.raise_for_status()
            payload = await response.json()

        return [
            _parse_candle(instrument, granularity, raw)
            for raw in payload["candles"]
            if raw["complete"]
        ]

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()


def _parse_candle(instrument: str, granularity: str, raw: dict) -> Candle:
    mid = raw["mid"]
    return Candle(
        symbol=instrument,
        timeframe=granularity,
        timestamp=datetime.fromisoformat(raw["time"]),
        open=float(mid["o"]),
        high=float(mid["h"]),
        low=float(mid["l"]),
        close=float(mid["c"]),
        volume=float(raw["volume"]),
    )

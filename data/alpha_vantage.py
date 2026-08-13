"""Async client for Alpha Vantage's FX endpoints: free, instant-signup forex OHLC data.

No broker account needed — this only fetches prices. Paper trading is done locally by
execution.backtest.BacktestExecutor + execution.portfolio.Portfolio, fed by these candles.
"""

import asyncio
import time
from datetime import datetime, timezone

import aiohttp

from data.models import Candle

BASE_URL = "https://www.alphavantage.co/query"

# FX_INTRADAY requires an Alpha Vantage premium plan (confirmed empirically:
# a free-tier key gets an "Information": "This is a premium endpoint" response).
# FX_DAILY works on the free tier, so that's the default granularity.
_INTRADAY_INTERVALS = {"1min", "5min", "15min", "30min", "60min"}


class AlphaVantageError(RuntimeError):
    pass


class AlphaVantageClient:
    def __init__(self, api_key: str, min_request_interval: float = 2.0):
        self._api_key = api_key
        self._session: aiohttp.ClientSession | None = None
        # Alpha Vantage enforces a 1-request/second burst limit even on the free
        # tier (separate from the ~25/day cap). Confirmed empirically: calling it
        # in a tight loop across several instruments triggers "Please consider
        # spreading out your free API requests more sparingly". Throttling here,
        # inside the client, means every caller (main.py, the analysis script,
        # the smoke test) is protected without having to remember to space calls.
        self._min_request_interval = min_request_interval
        self._last_request_time: float | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _throttle(self) -> None:
        now = time.monotonic()
        if self._last_request_time is not None:
            wait = self._min_request_interval - (now - self._last_request_time)
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
        self._last_request_time = now

    async def fetch_candles(self, instrument: str, granularity: str = "daily", count: int = 500) -> list[Candle]:
        await self._throttle()
        from_symbol, to_symbol = instrument.split("_")
        outputsize = "full" if count > 100 else "compact"

        if granularity in _INTRADAY_INTERVALS:
            params = {
                "function": "FX_INTRADAY",
                "from_symbol": from_symbol,
                "to_symbol": to_symbol,
                "interval": granularity,
                "outputsize": outputsize,
                "apikey": self._api_key,
            }
        else:
            params = {
                "function": "FX_DAILY",
                "from_symbol": from_symbol,
                "to_symbol": to_symbol,
                "outputsize": outputsize,
                "apikey": self._api_key,
            }

        session = await self._get_session()
        async with session.get(BASE_URL, params=params) as response:
            response.raise_for_status()
            payload = await response.json()

        # Alpha Vantage returns HTTP 200 even on rate limits/errors, just with a
        # "Note"/"Information"/"Error Message" key instead of the time series.
        series_key = next((key for key in payload if key.startswith("Time Series FX")), None)
        if series_key is None:
            message = payload.get("Note") or payload.get("Information") or payload.get("Error Message") or payload
            raise AlphaVantageError(f"Alpha Vantage did not return time series data: {message}")

        rows = sorted(payload[series_key].items())[-count:]
        return [_parse_candle(instrument, granularity, timestamp, values) for timestamp, values in rows]

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()


def _parse_candle(instrument: str, granularity: str, timestamp: str, values: dict) -> Candle:
    return Candle(
        symbol=instrument,
        timeframe=granularity,
        timestamp=datetime.fromisoformat(timestamp).replace(tzinfo=timezone.utc),
        open=float(values["1. open"]),
        high=float(values["2. high"]),
        low=float(values["3. low"]),
        close=float(values["4. close"]),
        # Alpha Vantage doesn't report volume for FX pairs (spot forex has no
        # central volume source); strategies relying on volume won't work here.
        volume=0.0,
    )

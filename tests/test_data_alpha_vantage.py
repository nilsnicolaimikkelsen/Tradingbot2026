import asyncio

import pytest

from data.alpha_vantage import AlphaVantageClient, AlphaVantageError


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    async def json(self):
        return self._payload


class _FakeGetCtx:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        return _FakeGetCtx(_FakeResponse(self._payload))

    async def close(self):
        pass


_INTRADAY_PAYLOAD = {
    "Meta Data": {"1. Information": "FX Intraday (60min) Time Series"},
    "Time Series FX (60min)": {
        "2024-01-01 00:00:00": {
            "1. open": "1.10000",
            "2. high": "1.10500",
            "3. low": "1.09500",
            "4. close": "1.10200",
        },
        "2024-01-01 01:00:00": {
            "1. open": "1.10200",
            "2. high": "1.10600",
            "3. low": "1.10100",
            "4. close": "1.10400",
        },
    },
}


def test_fetch_candles_parses_intraday_response():
    fake_session = _FakeSession(_INTRADAY_PAYLOAD)
    client = AlphaVantageClient(api_key="fake-key")
    client._session = fake_session

    candles = asyncio.run(client.fetch_candles("EUR_USD", granularity="60min", count=500))

    assert len(candles) == 2
    first = candles[0]
    assert first.symbol == "EUR_USD"
    assert first.timeframe == "60min"
    assert first.open == 1.1
    assert first.close == 1.102
    assert first.volume == 0.0

    url, params = fake_session.calls[0]
    assert params["function"] == "FX_INTRADAY"
    assert params["from_symbol"] == "EUR"
    assert params["to_symbol"] == "USD"
    assert params["interval"] == "60min"


def test_fetch_candles_uses_daily_endpoint_for_non_intraday_granularity():
    fake_session = _FakeSession(
        {"Time Series FX (Daily)": {"2024-01-01": {"1. open": "1.1", "2. high": "1.1", "3. low": "1.1", "4. close": "1.1"}}}
    )
    client = AlphaVantageClient(api_key="fake-key")
    client._session = fake_session

    asyncio.run(client.fetch_candles("EUR_USD", granularity="daily"))

    _, params = fake_session.calls[0]
    assert params["function"] == "FX_DAILY"
    assert "interval" not in params


def test_raises_alpha_vantage_error_on_rate_limit_response():
    fake_session = _FakeSession({"Note": "Thank you for using Alpha Vantage! Our standard API rate limit is..."})
    client = AlphaVantageClient(api_key="fake-key")
    client._session = fake_session

    with pytest.raises(AlphaVantageError):
        asyncio.run(client.fetch_candles("EUR_USD"))

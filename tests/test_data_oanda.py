import asyncio
from datetime import datetime, timezone

from data.oanda import LIVE_BASE_URL, PRACTICE_BASE_URL, OandaClient


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


_PAYLOAD = {
    "candles": [
        {
            "complete": True,
            "volume": 120,
            "time": "2024-01-01T00:00:00.000000000Z",
            "mid": {"o": "1.10000", "h": "1.10500", "l": "1.09500", "c": "1.10200"},
        },
        {
            "complete": False,
            "volume": 5,
            "time": "2024-01-01T01:00:00.000000000Z",
            "mid": {"o": "1.10200", "h": "1.10300", "l": "1.10100", "c": "1.10250"},
        },
    ]
}


def test_fetch_candles_parses_response_and_filters_incomplete():
    fake_session = _FakeSession(_PAYLOAD)
    client = OandaClient(api_token="fake-token", practice=True)
    client._session = fake_session

    candles = asyncio.run(client.fetch_candles("EUR_USD", granularity="H1", count=500))

    assert len(candles) == 1
    candle = candles[0]
    assert candle.symbol == "EUR_USD"
    assert candle.timeframe == "H1"
    assert candle.timestamp == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert candle.open == 1.1
    assert candle.high == 1.105
    assert candle.low == 1.095
    assert candle.close == 1.102
    assert candle.volume == 120.0
    assert fake_session.calls == [
        (f"{PRACTICE_BASE_URL}/v3/instruments/EUR_USD/candles", {"granularity": "H1", "count": "500", "price": "M"})
    ]


def test_uses_live_base_url_when_not_practice():
    client = OandaClient(api_token="fake-token", practice=False)

    assert client._base_url == LIVE_BASE_URL


def test_uses_practice_base_url_by_default():
    client = OandaClient(api_token="fake-token")

    assert client._base_url == PRACTICE_BASE_URL

import asyncio

import pytest

import data.alpha_vantage as av_module
from data.alpha_vantage import AlphaVantageClient


def test_throttle_waits_when_called_too_soon(monkeypatch):
    fake_now = [100.0]
    sleep_calls = []

    def fake_monotonic():
        return fake_now[0]

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)
        fake_now[0] += seconds

    monkeypatch.setattr(av_module.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(av_module.asyncio, "sleep", fake_sleep)

    client = AlphaVantageClient(api_key="fake", min_request_interval=1.2)

    asyncio.run(client._throttle())  # first call: nothing to wait for
    assert sleep_calls == []

    fake_now[0] += 0.3  # only 0.3s passed before the next call
    asyncio.run(client._throttle())

    assert len(sleep_calls) == 1
    assert sleep_calls[0] == pytest.approx(0.9, abs=0.01)


def test_throttle_does_not_wait_when_enough_time_has_passed(monkeypatch):
    fake_now = [100.0]
    sleep_calls = []

    def fake_monotonic():
        return fake_now[0]

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(av_module.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(av_module.asyncio, "sleep", fake_sleep)

    client = AlphaVantageClient(api_key="fake", min_request_interval=1.2)
    asyncio.run(client._throttle())

    fake_now[0] += 2.0  # plenty of time passed
    asyncio.run(client._throttle())

    assert sleep_calls == []

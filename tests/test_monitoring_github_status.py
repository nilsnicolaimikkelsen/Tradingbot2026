import asyncio
import base64
import json

from monitoring.github_status import GithubStatusPublisher


class _FakeResponse:
    def __init__(self, status, payload=None):
        self.status = status
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    async def json(self):
        return self._payload


class _FakeCtx:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    def __init__(self, get_response, put_response):
        self._get_response = get_response
        self._put_response = put_response
        self.get_calls = []
        self.put_calls = []

    def get(self, url, params=None):
        self.get_calls.append((url, params))
        return _FakeCtx(self._get_response)

    def put(self, url, json=None):
        self.put_calls.append((url, json))
        return _FakeCtx(self._put_response)

    async def close(self):
        pass


def test_publish_creates_file_when_it_does_not_exist_yet():
    publisher = GithubStatusPublisher(token="fake", owner="o", repo="r")
    fake_session = _FakeSession(get_response=_FakeResponse(404), put_response=_FakeResponse(200))
    publisher._session = fake_session

    asyncio.run(publisher.publish({"a": 1}))

    assert len(fake_session.put_calls) == 1
    _, body = fake_session.put_calls[0]
    assert "sha" not in body
    assert body["branch"] == "bot-status"
    decoded = json.loads(base64.b64decode(body["content"]))
    assert decoded == {"a": 1}


def test_publish_updates_existing_file_with_its_sha():
    publisher = GithubStatusPublisher(token="fake", owner="o", repo="r")
    fake_session = _FakeSession(
        get_response=_FakeResponse(200, {"sha": "abc123"}),
        put_response=_FakeResponse(200),
    )
    publisher._session = fake_session

    asyncio.run(publisher.publish({"a": 2}))

    _, body = fake_session.put_calls[0]
    assert body["sha"] == "abc123"


def test_publish_raises_on_unexpected_get_status():
    import pytest

    publisher = GithubStatusPublisher(token="fake", owner="o", repo="r")
    fake_session = _FakeSession(get_response=_FakeResponse(500), put_response=_FakeResponse(200))
    publisher._session = fake_session

    with pytest.raises(RuntimeError):
        asyncio.run(publisher.publish({"a": 3}))

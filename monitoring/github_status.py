"""Publishes a status snapshot to a file in a GitHub branch via the Contents API.

Lets the bot's status be checked without direct network access to wherever it
runs. Useful when the operator's tooling sits behind a network policy that
blocks direct access to the host (e.g. a sandboxed Claude Code session), while
GitHub itself is reachable from both sides.
"""

import base64
import json

import aiohttp

API_BASE = "https://api.github.com"


class GithubStatusPublisher:
    def __init__(self, token: str, owner: str, repo: str, branch: str = "bot-status", path: str = "status.json"):
        self._token = token
        self._owner = owner
        self._repo = repo
        self._branch = branch
        self._path = path
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/vnd.github+json",
                }
            )
        return self._session

    async def publish(self, status: dict) -> None:
        session = await self._get_session()
        url = f"{API_BASE}/repos/{self._owner}/{self._repo}/contents/{self._path}"

        sha = None
        async with session.get(url, params={"ref": self._branch}) as resp:
            if resp.status == 200:
                existing = await resp.json()
                sha = existing["sha"]
            elif resp.status != 404:
                resp.raise_for_status()

        content = base64.b64encode(json.dumps(status, indent=2).encode()).decode()
        body = {"message": "Update bot status", "content": content, "branch": self._branch}
        if sha:
            body["sha"] = sha

        async with session.put(url, json=body) as resp:
            resp.raise_for_status()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()

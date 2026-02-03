from __future__ import annotations

import asyncio
import json
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

import httpx

from secfetch.exceptions import MissingUserAgentError, RateLimitedError
from secfetch.network.rate_limit import RateLimiter


def _user_agent_from_email_json(data_dir: Optional[Path] = None) -> str:
    """Load emails from data_dir/config/email.json if it exists, else package default. Never creates config folder."""
    base = (data_dir if data_dir is not None else Path.cwd() / "data").resolve()
    path = base / "config" / "email.json"
    raw: Optional[str] = None
    if path.is_file():
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            pass
    if raw is None:
        try:
            from importlib.resources import files
            raw = (files("secfetch.resources") / "email.json").read_text(encoding="utf-8")
        except Exception:
            return ""
    if not raw:
        return ""
    try:
        data = json.loads(raw)
        emails: List[str] = data.get("emails") if isinstance(data, dict) else []
        if isinstance(emails, list) and emails:
            valid = [e for e in emails if isinstance(e, str) and "@" in e]
            if valid:
                return f"sec-fetcher {random.choice(valid)}"
    except json.JSONDecodeError:
        pass
    return ""


@dataclass(frozen=True)
class SecClientConfig:
    user_agent: str
    max_requests_per_second: float = 8.0
    timeout_seconds: float = 30.0
    max_retries: int = 6


class SecClient:
    """
    Minimal SEC-safe HTTP client:
    - required User-Agent
    - global rate limiting
    - retry/backoff on 429/5xx
    """

    def __init__(self, config: SecClientConfig):
        if not config.user_agent or "@" not in config.user_agent:
            raise MissingUserAgentError(
                'SEC user-agent is required (include contact info), e.g. "My Org contact@example.com".'
            )

        self._config = config
        self._rate_limiter = RateLimiter(config.max_requests_per_second)
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(config.timeout_seconds),
            headers={
                "User-Agent": config.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
            },
        )

    @classmethod
    def from_env(
        cls,
        *,
        user_agent: Optional[str] = None,
        data_dir: Optional[Path] = None,
    ) -> "SecClient":
        ua = (
            user_agent
            or os.getenv("SEC_USER_AGENT")
            or _user_agent_from_email_json(data_dir=data_dir)
        )
        return cls(SecClientConfig(user_agent=ua))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_bytes(self, url: str) -> bytes:
        resp = await self._request("GET", url)
        return resp.content

    async def get_text(self, url: str) -> str:
        resp = await self._request("GET", url)
        return resp.text

    async def get_json(self, url: str) -> Any:
        resp = await self._request("GET", url)
        return resp.json()

    async def _request(self, method: str, url: str) -> httpx.Response:
        last_exc: Optional[Exception] = None

        for attempt in range(1, self._config.max_retries + 1):
            await self._rate_limiter.wait()
            try:
                resp = await self._client.request(method, url)

                if resp.status_code == 429:
                    # SEC rate limit: obey Retry-After when present, else backoff.
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        sleep_s = float(retry_after)
                    else:
                        sleep_s = min(60.0, (2**attempt) + random.random())
                    await asyncio.sleep(sleep_s)
                    last_exc = RateLimitedError(f"429 rate limited for {url}")
                    continue

                if 500 <= resp.status_code < 600:
                    sleep_s = min(30.0, (2**attempt) * 0.5 + random.random())
                    await asyncio.sleep(sleep_s)
                    last_exc = httpx.HTTPStatusError(
                        f"Server error {resp.status_code} for {url}",
                        request=resp.request,
                        response=resp,
                    )
                    continue

                resp.raise_for_status()
                return resp

            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as e:
                last_exc = e
                sleep_s = min(10.0, attempt * 0.5 + random.random())
                await asyncio.sleep(sleep_s)
                continue

        if last_exc:
            raise last_exc
        raise RuntimeError(f"Request failed without exception: {method} {url}")


"""Shared requests session with browser UA, timeout, and simple retries."""
from __future__ import annotations

import time

import requests

from .. import config

_session: requests.Session | None = None


def get_session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({"User-Agent": config.USER_AGENT})
        _session = s
    return _session


def get(url: str, retries: int = 2) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = get_session().get(url, timeout=config.REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(2**attempt)
    raise last_exc  # type: ignore[misc]

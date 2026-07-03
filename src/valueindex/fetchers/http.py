"""Shared requests session with browser UA, timeout, and simple retries.

The session is thread-local so the parallel loader (loader.load_all) can
fetch sources concurrently without sharing a non-thread-safe Session.
"""
from __future__ import annotations

import threading
import time

import requests

from .. import config

_local = threading.local()


def get_session() -> requests.Session:
    s = getattr(_local, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"User-Agent": config.USER_AGENT})
        _local.session = s
    return s


def get(url: str, retries: int = 1) -> requests.Response:
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

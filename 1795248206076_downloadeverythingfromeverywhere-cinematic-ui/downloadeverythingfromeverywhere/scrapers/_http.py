"""Shared HTTP for scrapers.

Prefer curl_cffi for HTTP requests, with cloudscraper as a fallback.
"""

from __future__ import annotations

import threading

import cloudscraper

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

DEFAULT_TIMEOUT = 6
MAX_TIMEOUT = 8
_local = threading.local()

try:
    from curl_cffi import requests as curl_requests

    _HAS_CURL = True
except Exception:
    curl_requests = None
    _HAS_CURL = False


def _cloud_session():
    s = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "desktop": True},
    )
    s.headers.update(UA)
    return s


def _curl_session():
    s = curl_requests.Session(impersonate="chrome")
    s.headers.update(UA)
    return s


def create_scraper():
    if _HAS_CURL:
        try:
            return _curl_session()
        except Exception:
            pass
    return _cloud_session()


def session():
    """Reuse one session per thread (cookies stick across calls)."""
    s = getattr(_local, "session", None)
    if s is None:
        s = create_scraper()
        _local.session = s
    return s


def _clamp_timeout(kw):
    t = kw.get("timeout", DEFAULT_TIMEOUT)
    if t is None:
        kw["timeout"] = DEFAULT_TIMEOUT
        return
    if isinstance(t, (tuple, list)) and t:
        kw["timeout"] = tuple(min(float(x), MAX_TIMEOUT) for x in t[:2])
        return
    try:
        kw["timeout"] = min(float(t), MAX_TIMEOUT)
    except Exception:
        kw["timeout"] = DEFAULT_TIMEOUT


def _call(session_obj, method, url, **kw):
    _clamp_timeout(kw)
    return getattr(session_obj, method)(url, **kw)


def get(url, **kw):
    return _call(session(), "get", url, **kw)


def post(url, **kw):
    return _call(session(), "post", url, **kw)


class Session:
    """Drop-in for requests.Session()."""

    def __init__(self):
        self._s = create_scraper()

    def _call(self, method, url, **kw):
        return _call(self._s, method, url, **kw)

    def get(self, url, **kw):
        return self._call("get", url, **kw)

    def post(self, url, **kw):
        return self._call("post", url, **kw)

    def head(self, url, **kw):
        return self._call("head", url, **kw)

    def request(self, method, url, **kw):
        _clamp_timeout(kw)
        return self._s.request(method, url, **kw)

    def __getattr__(self, name):
        return getattr(self._s, name)

"""Drop expired file-host links. Fail open on timeouts/network errors."""
from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

FLAKY = re.compile(
    r"mega\.nz|gofile\.io|pixeldrain\.(?:net|com|dev)|firefiles\.|clicknupload|"
    r"rapidrar\.|vikingfile\.|krakenfiles\.|mediafire\.com|"
    r"downloadwella\.|xubster\.",
    re.I,
)
DEAD_TXT = re.compile(
    r"file not found|no such file|content not found|has been removed|"
    r"invalid or deleted file|this file (?:is|has been) (?:deleted|expired)|"
    r"no longer available|error-notFound|\"value\"\s*:\s*\"not_found\"",
    re.I,
)
PIXEL_ID = re.compile(r"pixeldrain\.[^/]+/(?:u|api/file)/([A-Za-z0-9]+)", re.I)
MEGA_ID = re.compile(r"mega\.nz/(?:file/|#!)([A-Za-z0-9_-]+)", re.I)
GOFILE_BOT = "Googlebot/2.1 (+http://www.google.com/bot.html)"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
CTX = ssl.create_default_context()
TIMEOUT = 5


def _url(item) -> str:
    if isinstance(item, str):
        return item
    return (item or {}).get("url") or ""


def _xid(url: str) -> str:
    parts = [p for p in urlparse(url).path.split("/") if p]
    if not parts:
        return ""
    return parts[0].split(".")[0].lower()


def _fetch(url: str, ua: str) -> tuple[int, str, str]:
    try:
        from scrapers._http import create_scraper

        r = create_scraper().get(url, timeout=TIMEOUT, headers={"User-Agent": ua}, allow_redirects=True)
        return int(r.status_code or 0), (r.text or "")[:32768], getattr(r, "url", url) or url
    except Exception:
        pass
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as r:
            return int(r.status), r.read(32768).decode("utf-8", "replace"), r.geturl()
    except urllib.error.HTTPError as e:
        body = e.read(32768).decode("utf-8", "replace") if e.fp else ""
        return int(e.code), body, url


def _mega_dead(url: str) -> bool:
    m = MEGA_ID.search(url or "")
    if not m:
        return False
    fid = m.group(1).split("!")[0]
    req = urllib.request.Request(
        "https://g.api.mega.co.nz/cs?id=0",
        data=json.dumps([{"a": "g", "p": fid}]).encode(),
        headers={"Content-Type": "application/json", "User-Agent": UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as r:
            body = r.read(4096).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read(4096).decode("utf-8", "replace") if e.fp else ""
    compact = body.replace(" ", "")
    return compact in ("[-9]", "[-2]", "[-16]")


def _dead(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
        if "mega.nz" in host:
            return _mega_dead(url)
        if "pixeldrain." in host:
            m = PIXEL_ID.search(url)
            if not m:
                return False
            code, body, _ = _fetch(f"https://{host}/api/file/{m.group(1)}/info", UA)
            if code in (404, 410):
                return True
            compact = body.replace(" ", "")
            return '"success":false' in compact or bool(DEAD_TXT.search(body))
        ua = GOFILE_BOT if "gofile.io" in host else UA
        code, body, final = _fetch(url, ua)
        if code in (404, 410) or bool(DEAD_TXT.search(body)):
            return True
        # firefiles/clicknupload 302 to a new file-code; that is not a dead link
        if "firefiles." in host or "clicknupload" in host:
            return False
        a, b = _xid(url), _xid(final)
        return bool(a and b and a != b)
    except Exception:
        return False


def drop_dead(items: list) -> list:
    idxs = [i for i, it in enumerate(items or []) if FLAKY.search(_url(it) or "")]
    if not idxs:
        return items or []
    dead = set()
    with ThreadPoolExecutor(max_workers=min(8, len(idxs))) as pool:
        futs = {pool.submit(_dead, _url(items[i])): i for i in idxs}
        for f in as_completed(futs):
            try:
                if f.result():
                    dead.add(futs[f])
            except Exception:
                pass
    return [it for i, it in enumerate(items) if i not in dead]

"""FastAPI scrape stream — NDJSON over POST /."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import os
import pkgutil
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import unquote, urlencode, urlparse

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
SCRAPERS_DIR = ROOT / "scrapers"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scrapers._alive import drop_dead

# Lower = start sooner. Direct/API first; CF/ad-wall/captcha last.
CONCURRENCY = 8
LANES = 8
SITE_DEADLINE_S = 10.0
HUNT_DEADLINE_S = 40.0
DROP_DEAD_S = 3.0
CACHE_TTL_HIT = 1800.0
CACHE_TTL_MISS = 600.0
CACHE_MAX = 1500
SKIP_FAILS = 2
SKIP_FOR_S = 60.0

SITE_RANK = {
    "phonofilm": 10,
    "111477": 11,
    "moviebox": 12,
    "hindmoviez": 14,
    "nkiri": 16,
    "4khdhub": 18,
    "moviesdrive": 19,
    "filmgo": 20,
    "filmvault": 21,
    "cinefy": 22,
    "hdmoviez": 24,
    "tvsboy": 26,
    "vadapav": 28,
    "todaytvseries": 34,
    "fzmovies": 36,
    "katmoviehd": 38,
    "uhdmovies": 40,
    "tattooin": 42,
    "rapidmoviez": 44,
    "subsl": 46,
    "moviesmod": 48,
    "hdmovieshub": 50,
    "lightdl": 52,
    "pahe": 54,
    "animeout": 60,
    "anime7": 62,
    "animetosho": 70,
    "kayoanime": 72,
    "kusonime": 74,
    "animerss": 76,
    "animesalt": 78,
    "tsukihime": 84,
    "mynimeku": 86,
    "rlsxtvt": 200,
    "multishows": 210,
}

ANIME_SITES = frozenset({
    "animetosho",
    "kayoanime",
    "kusonime",
    "animerss",
    "animesalt",
    "anime7",
    "animeout",
    "tsukihime",
    "mynimeku",
})

ANIME_KEEP = ANIME_SITES | {"111477", "vadapav", "moviesmod"}


def hunt_key(name: str, mal: bool = False) -> tuple:
    rank = SITE_RANK.get(name, 900)
    if mal:
        return (0 if name in ANIME_KEEP else 1, rank, name)
    return (rank, name)


TAG_RULES = [
    (re.compile(r"\b(2160p+|4k|uhd)\b|\b\d{3,4}\s*[x×]\s*2160\b", re.I), "2160p"),
    (re.compile(r"\b1080p+\b|\b\d{3,4}\s*[x×]\s*1080\b", re.I), "1080p"),
    (re.compile(r"\b720p+\b|\b720\s*hc\b|\b720hc\b|\b\d{3,4}\s*[x×]\s*720\b", re.I), "720p"),
    (re.compile(r"\b540p+\b|\b\d{3,4}\s*[x×]\s*540\b", re.I), "540p"),
    (re.compile(r"\b480p+\b|\b480\s*hc\b|\b480hc\b|\b\d{3,4}\s*[x×]\s*480\b", re.I), "480p"),
    (re.compile(r"\b400p+\b|\b\d{3,4}\s*[x×]\s*400\b", re.I), "400p"),
    (re.compile(r"\b360p+\b|\b\d{3,4}\s*[x×]\s*360\b", re.I), "360p"),
    (re.compile(r"\bremux\b", re.I), "REMUX"),
    (re.compile(r"\bbluray|blu[-\s]?ray|bdrip|brrip\b", re.I), "BluRay"),
    (re.compile(r"\bweb[-\s]?dl\b", re.I), "WEB-DL"),
    (re.compile(r"\bwebrip\b", re.I), "WEBRip"),
    (re.compile(r"\bhdtv\b", re.I), "HDTV"),
    (re.compile(r"\bhdrip\b", re.I), "HDRip"),
    (re.compile(r"\b(x265|h\.?265|hevc)\b", re.I), "x265"),
    (re.compile(r"\b(x264|h\.?264|avc)\b", re.I), "x264"),
    (re.compile(r"\b10\s*-?\s*bit\b", re.I), "10bit"),
    (re.compile(r"\bhdr10?\+?\b", re.I), "HDR"),
    (re.compile(r"\batmos\b", re.I), "Atmos"),
    (re.compile(r"\bddp?5\.?1|truehd|dts\b", re.I), "5.1"),
    (re.compile(r"\bdual(?:[_\s-]*audio)?\b", re.I), "Dual"),
    (re.compile(r"\bmulti(?:[_\s-]*audio)?\b", re.I), "Multi"),
    (re.compile(r"\bhindi\b", re.I), "Hindi"),
    (re.compile(r"\benglish\b", re.I), "English"),
    (re.compile(r"\bindonesian\b|\bsubtitle\s+indonesia\b|\bsub(?:title)?\s*indo(?:nesia)?\b", re.I), "Indonesian"),
    (re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(KB|MB|GB|TB|KiB|MiB|GiB|TiB)\b", re.I), None),
]

HOSTER_LABEL = [
    (re.compile(r"t\.me|telegram\.(?:me|dog)", re.I), "Telegram"),
    (re.compile(r"googleusercontent", re.I), "G-Drive"),
    (re.compile(r"hubdrive", re.I), "HubDrive"),
    (re.compile(r"hubcloud", re.I), "HubCloud"),
    (re.compile(r"gdflix|gdlink", re.I), "GDFlix"),
    (re.compile(r"gofile", re.I), "Gofile"),
    (re.compile(r"mega\.nz", re.I), "Mega"),
    (re.compile(r"acefile", re.I), "Acefile"),
    (re.compile(r"hxfile", re.I), "Hxfile"),
    (re.compile(r"mydriveku", re.I), "MyNimeku"),
    (re.compile(r"pixeldrain", re.I), "Pixeldrain"),
    (re.compile(r"vikingfile", re.I), "Viking"),
    (re.compile(r"fileditch", re.I), "FileDitch"),
    (re.compile(r"public\.animeout|nimbus\.animeout", re.I), "AnimeOut"),
    (re.compile(r"clicknupload|clickndownload", re.I), "Clicknupload"),
    (re.compile(r"rapidrar", re.I), "RapidRAR"),
    (re.compile(r"firefiles", re.I), "Firefiles"),
    (re.compile(r"downloadwella", re.I), "Wella"),
    (re.compile(r"xubster", re.I), "Xubster"),
    (re.compile(r"highxhd", re.I), "HDMoviez"),
    (re.compile(r"driveseed|driveleech", re.I), "DriveSeed"),
]


def _bare_return_only(fn) -> bool:
    try:
        src = inspect.getsource(fn)
    except OSError:
        return False
    body = re.sub(r'""".*?"""|\'\'\'.*?\'\'\'', "", src, flags=re.S)
    body = re.sub(r"#.*", "", body)
    return bool(re.search(r"def\s+\w+\([^)]*\):\s*(?:return(?:\s+None)?\s*)?$", body.strip(), re.S))


def load_scrapers() -> list[dict[str, Any]]:
    out = []
    for info in pkgutil.iter_modules([str(SCRAPERS_DIR)]):
        if info.name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"scrapers.{info.name}")
        except Exception:
            continue
        caps = {}
        for fn in ("dlmovie", "dlseries", "dlseriesepisode"):
            f = getattr(mod, fn, None)
            caps[fn] = callable(f) and not _bare_return_only(f)
        if not any(caps.values()):
            continue
        out.append({"name": info.name, "mod": mod, "caps": caps})
    out.sort(key=lambda s: hunt_key(s["name"]))
    return out


SCRAPERS = load_scrapers()
_executor = ThreadPoolExecutor(max_workers=CONCURRENCY)
_site_slots = asyncio.Semaphore(CONCURRENCY)
_lane_lock = asyncio.Lock()


class _Lane:
    __slots__ = ("waiters",)

    def __init__(self):
        self.waiters: list[asyncio.Future] = []


_lanes = [_Lane() for _ in range(LANES)]
_cache: dict[tuple, tuple[float, list]] = {}
_fail_n: dict[str, int] = {}
_fail_until: dict[str, float] = {}


def _ckey(name: str, mode: str, kw: dict) -> tuple:
    return (name, mode, kw.get("title"), kw.get("year"), kw.get("tmdb_id"), kw.get("season"), kw.get("episode"))


def _cache_get(key: tuple):
    rec = _cache.get(key)
    if not rec:
        return None
    exp, val = rec
    if exp < time.monotonic():
        _cache.pop(key, None)
        return None
    return val


def _cache_put(key: tuple, val: list, ttl: float):
    if len(_cache) >= CACHE_MAX:
        now = time.monotonic()
        for k, (exp, _) in list(_cache.items()):
            if exp < now:
                _cache.pop(k, None)
        while len(_cache) >= CACHE_MAX and _cache:
            _cache.pop(next(iter(_cache)))
    _cache[key] = (time.monotonic() + ttl, val)


def _skip_site(name: str) -> bool:
    return _fail_until.get(name, 0) > time.monotonic()


def _note_timeout(name: str):
    n = _fail_n.get(name, 0) + 1
    _fail_n[name] = n
    if n >= SKIP_FAILS:
        _fail_until[name] = time.monotonic() + SKIP_FOR_S


def _note_ok(name: str):
    _fail_n.pop(name, None)
    _fail_until.pop(name, None)


def _queue_lanes() -> list[int]:
    return [len(L.waiters) for L in _lanes]


def _siteverify(secret: str, token: str) -> bool:
    if not token:
        return False
    data = urlencode({"secret": secret, "response": token}).encode()
    req = urllib.request.Request(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=data,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            out = json.loads(r.read().decode())
        return bool(out.get("success"))
    except Exception:
        return False


app = FastAPI(title="defe-api")
frontend_origin = os.environ.get("FRONTEND_ORIGIN", "").rstrip("/")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin] if frontend_origin else [],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$" if not frontend_origin else None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class Body(BaseModel):
    mode: str
    title: str
    year: int | None = None
    tmdb_id: int | str | None = None
    imdb_id: str | None = None
    season: int | None = None
    episode: int | None = None
    mal_id: int | str | None = None
    anime: bool = False
    turnstile: str | None = None


def scrapers_for(mode: str, mal: bool = False) -> list[dict[str, Any]]:
    key = {"movie": "dlmovie", "series": "dlseries"}.get(mode, "dlseriesepisode")
    sites = [s for s in SCRAPERS if s["caps"].get(key)]
    if mal:
        sites = [s for s in sites if s["name"] in ANIME_KEEP]
    else:
        sites = [s for s in sites if s["name"] not in ANIME_SITES]
    sites.sort(key=lambda s: hunt_key(s["name"], mal))
    return sites


def link_url(item: Any) -> str | None:
    if isinstance(item, str):
        return item.strip() or None
    if isinstance(item, dict):
        u = item.get("url") or item.get("href") or item.get("link")
        return str(u).strip() if u else None
    return None


def link_name(item: Any) -> str:
    return str(item.get("name") or item.get("title") or "") if isinstance(item, dict) else ""


def link_tags(item: Any) -> list[str]:
    if isinstance(item, dict):
        return [str(x) for x in (item.get("tags") or []) if x]
    return []


def _size_tag(num: str, unit: str) -> str:
    n = num.replace(",", ".")
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return f"{n}{unit.upper().replace('IB', 'B')}"


def tags_from_text(*parts: str) -> list[str]:
    blob = " ".join(p for p in parts if p)
    if not blob.strip():
        return []
    tags, seen, quals = [], set(), []
    quality = {"2160p", "1080p", "720p", "540p", "480p", "400p", "360p"}
    for re_pat, tag in TAG_RULES:
        if tag is None:
            for m in re_pat.finditer(blob):
                t = _size_tag(m.group(1), m.group(2))
                if t not in seen:
                    seen.add(t)
                    tags.append(t)
            continue
        if tag in seen or not re_pat.search(blob):
            continue
        seen.add(tag)
        if tag in quality:
            quals.append(tag)
        else:
            tags.append(tag)
    if len(quals) == 1:
        tags.insert(0, quals[0])
    return tags


def tags_from_url(url: str) -> list[str]:
    return tags_from_text(unquote(url))


def is_opaque_name(name: str) -> bool:
    t = (name or "").strip()
    if not t or t.lower() in {"download", "dl", "file", "link", "get", "index", "cloud", "links"}:
        return True
    if re.fullmatch(r"\d{5,}", t):
        return True
    if re.fullmatch(r"[a-f0-9]{20,}", t, re.I):
        return True
    # base64 / token blobs (deinform ids, signed urls, etc.)
    if (
        len(t) >= 24
        and re.fullmatch(r"[A-Za-z0-9+/=_-]+", t)
        and not re.search(r"\d{3,4}p|S\d{1,2}E\d{1,3}|\.(mkv|mp4|zip|rar)$", t, re.I)
    ):
        return True
    if (
        re.fullmatch(r"[A-Za-z0-9_-]{3,48}", t)
        and "." not in t
        and not re.search(r"\d{3,4}p", t, re.I)
        and not re.search(r"\bS\d{1,2}E\d{1,3}\b", t, re.I)
        and not re.search(r"\b(19|20)\d{2}\b", t)
    ):
        return True
    return False


def hoster_label(url: str) -> str:
    for re_pat, label in HOSTER_LABEL:
        if re_pat.search(url):
            return label
    try:
        host = urlparse(url).hostname or ""
        host = re.sub(r"^www\.", "", host)
        part = host.split(".")[0] if host else "Link"
        return part[:1].upper() + part[1:] if part else "Link"
    except Exception:
        return "Link"


def name_from_url(url: str) -> str:
    try:
        u = urlparse(url)
        cands = []
        path = unquote(u.path).rstrip("/")
        base = path.split("/")[-1] or ""
        if base:
            cands.append(base.replace("+", " "))
        from urllib.parse import parse_qs

        qs = parse_qs(u.query)
        for key in ("id", "name", "file", "filename", "title", "fn", "n"):
            for v in qs.get(key) or []:
                cands.append(unquote(v).replace("+", " "))
        for s in cands:
            if s and not is_opaque_name(s):
                return s
    except Exception:
        pass
    return ""


_SIZE_IN_NAME = re.compile(
    r"[\(\[]\s*\d+(?:[.,]\d+)?\s*(?:KB|MB|GB|TB|KiB|MiB|GiB|TiB)\s*[\)\]]",
    re.I,
)
_SIZE_TAG_RE = re.compile(r"^\d+(?:\.\d+)?(?:KB|MB|GB|TB)$", re.I)


def strip_size_from_name(name: str) -> str:
    t = _SIZE_IN_NAME.sub(" ", name or "")
    return re.sub(r"\s+", " ", t).strip(" -–—|")


def size_last(tags: list[str]) -> list[str]:
    rest, sizes = [], []
    for t in tags:
        (sizes if _SIZE_TAG_RE.fullmatch(t) else rest).append(t)
    return rest + sizes


def clean_display_name(name: str) -> str:
    t = re.sub(r"\s+", " ", name or "").strip()
    if re.search(r"\.(mkv|mp4|avi|iso|m4v|m2ts|ts|zip|rar)(?:\s*\[|$)", t, re.I) and len(t) < 400:
        return t
    m = re.search(
        r"([A-Za-z0-9][A-Za-z0-9._()\[\]+'’\s,~&%#@!;–—-]{8,}\.(?:mkv|mp4|avi|iso|zip|rar))",
        t,
        re.I,
    )
    if m:
        t = m.group(1)
    t = re.sub(r"\.html?$", "", t, flags=re.I)
    # CTA fluff: "Click to Download Episode 01 in HD Mp4 Format (123 Downloads)"
    t = re.sub(r"\bdownloads?\b", " ", t, flags=re.I)
    t = re.sub(r"^(?:click\s+(?:here\s+)?(?:to\s+)?)?", "", t, flags=re.I).strip()
    t = re.sub(r"^download\s+", "", t, flags=re.I).strip()
    t = re.sub(r"\s*\(\s*\d+\s*\)\s*$", "", t).strip()
    t = re.sub(
        r"\b(?:hubcloud|hubdrive|gdflix|filebee|v-?cloud|nexdrive)\b",
        " ",
        t,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", t).strip(" -–—|")


_REL_HEAD = re.compile(
    r"^(?:(?:19|20)\d{2}|s\d{1,2}e\d{1,3}|s\d{1,2}|e\d{1,3}|season\d*|"
    r"\d{3,4}p|1080i|complete|repack|proper|extended|theatrical|remux|"
    r"bluray|webrip|webdl|web|hdtv|hybrid|uhd|multi|dual|"
    r"x264|x265|h264|h265|hevc|avc)$",
    re.I,
)


def is_longer_title(name: str, title: str) -> bool:
    """True when name is the requested title plus another show's extra words (spinoff)."""
    t = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
    n = re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()
    n = re.sub(r"\bweb\s+dl\b", "webdl", n)
    t = re.sub(r"\bweb\s+dl\b", "webdl", t)
    if not t or not n.startswith(t + " "):
        return False
    rest = n[len(t) + 1 :]
    # "Title 2026 1080p WEB-DL..." / "Title Season 1 Zip" is a release, not a spinoff.
    if re.match(r"(?:19|20)\d{2}\b", rest):
        return False
    if re.match(r"(?:s\d{1,2}|season)\b", rest):
        return False
    before = re.split(r"\bs\d{1,2}e\d{1,3}\b|\b\d{1,2}x\d{2,3}\b", rest, maxsplit=1)[0]
    extra = [w for w in before.split() if w and not _REL_HEAD.match(w)]
    return len(extra) >= 2


def is_single_episode_ref(name: str, url: str = "") -> bool:
    """True for a single SxxEyy / 1x01 file — not a season pack or episode range."""
    blob = f"{name or ''} {unquote(url or '')}"
    if not blob.strip():
        return False
    if re.search(r"S\d{1,2}E\d{1,3}\s*[-–to]+\s*E?\d{1,3}", blob, re.I):
        return False
    if re.search(r"(?:Episode|Ep)\s*\d{1,3}\s*[-–to]+\s*\d{1,3}", blob, re.I):
        return False
    if re.search(r"\bbatch\b|\bcomplete\b|season\s*pack|\bpack\b", blob, re.I):
        return False
    if re.search(r"\bS\d{1,2}E\d{1,3}\b", blob, re.I):
        return True
    if re.search(r"\b\d{1,2}x\d{2,3}\b", blob, re.I):
        return True
    return False


def normalize_items(items: list[Any], type_tag: str, title: str = "") -> list[dict]:
    out, seen = [], set()
    for it in items or []:
        url = link_url(it)
        if not url or not url.startswith("http") or url in seen:
            continue
        seen.add(url)
        raw_name = clean_display_name(link_name(it))
        tags = list(
            dict.fromkeys(
                [type_tag, *link_tags(it), *tags_from_text(raw_name), *tags_from_url(url)]
            )
        )
        tags = [t for t in tags if t]
        if raw_name and not is_opaque_name(raw_name) and raw_name.lower() not in {"download", "cloud", "links"}:
            name = raw_name
        else:
            from_url = name_from_url(url)
            if from_url:
                name = from_url
            else:
                host = hoster_label(url)
                quals = [t for t in tags if re.fullmatch(r"\d{3,4}p", t)]
                name = f"{host} {quals[0]}" if len(quals) == 1 else host
        name = strip_size_from_name(name)
        tags = size_last(tags)
        if title and is_longer_title(name, title):
            continue
        out.append({"url": url, "tags": tags, "name": name, "release": name})
    if type_tag == "Pack":
        out = [x for x in out if not is_single_episode_ref(x["name"], x.get("url") or "")]
    return out


def call_scraper(s: dict, mode: str, kw: dict) -> list[Any]:
    mod = s["mod"]
    try:
        if mode == "movie":
            r = mod.dlmovie(**kw)
        elif mode == "series":
            r = mod.dlseries(**kw)
        else:
            r = mod.dlseriesepisode(**kw)
        return r if isinstance(r, list) else []
    except Exception:
        return []


async def call_scraper_async(s: dict, mode: str, kw: dict, timeout: float = SITE_DEADLINE_S):
    loop = asyncio.get_running_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(_executor, call_scraper, s, mode, kw),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return None
    except Exception:
        return []


def build_kwargs(body: Body, mode: str) -> dict:
    kw: dict[str, Any] = {
        "title": body.title,
        "year": body.year,
        "tmdb_id": None if body.mal_id is not None else body.tmdb_id,
        "imdb_id": body.imdb_id,
    }
    if mode in ("series", "episode"):
        kw["season"] = int(body.season or 1)
    if mode == "episode":
        kw["episode"] = int(body.episode or 1)
    return kw


async def stream_events(body: Body, request: Request) -> AsyncIterator[bytes]:
    if await request.is_disconnected():
        return
    secret = os.environ.get("TURNSTILE_SECRET")
    if secret:
        token = (body.turnstile or "").strip()
        if not await asyncio.to_thread(_siteverify, secret, token):
            yield (json.dumps({"t": "error", "msg": "verify failed"}) + "\n").encode()
            return
        if await request.is_disconnected():
            return
    fut = asyncio.get_running_loop().create_future()
    async with _lane_lock:
        lane = min(_lanes, key=lambda L: len(L.waiters))
        lane.waiters.append(fut)
        if len(lane.waiters) == 1:
            fut.set_result(None)
    try:
        while not fut.done():
            if await request.is_disconnected():
                return
            yield (json.dumps({"t": "queue", "n": len(lane.waiters)}) + "\n").encode()
            await asyncio.wait({fut}, timeout=0.2)
        if await request.is_disconnected():
            return
        yield (json.dumps({"t": "queue", "n": len(lane.waiters)}) + "\n").encode()
        async for chunk in _hunt_events(body, request):
            yield chunk
    finally:
        async with _lane_lock:
            if fut in lane.waiters:
                lane.waiters.remove(fut)
            if lane.waiters and not lane.waiters[0].done():
                lane.waiters[0].set_result(None)


async def _hunt_events(body: Body, request: Request) -> AsyncIterator[bytes]:
    mode = body.mode
    if mode in ("seriesepisode", "episode"):
        mode = "episode"
    sites = scrapers_for(mode, mal=body.mal_id is not None or body.anime)
    kw = build_kwargs(body, mode)
    type_tag = "Movie" if mode == "movie" else "Pack" if mode == "series" else "Episode"
    total = len(sites)
    yield (json.dumps({"t": "start", "total": total}) + "\n").encode()

    done = 0
    found = 0
    lock = asyncio.Lock()
    q: asyncio.Queue[dict | None] = asyncio.Queue()
    stop = asyncio.Event()

    async def one(s: dict):
        nonlocal done, found
        if stop.is_set():
            return
        async with _site_slots:
            if stop.is_set() or _skip_site(s["name"]):
                async with lock:
                    done += 1
                    d = done
                await q.put({"t": "miss", "site": s["name"], "done": d, "total": total})
                return
            await q.put({"t": "check", "site": s["name"], "done": done, "total": total})
            key = _ckey(s["name"], mode, kw)
            cached = _cache_get(key)
            if cached is not None:
                links = cached
            else:
                links = await call_scraper_async(s, mode, kw, timeout=SITE_DEADLINE_S)
                if links is None:
                    _note_timeout(s["name"])
                    links = []
                else:
                    _note_ok(s["name"])
                    _cache_put(key, links, CACHE_TTL_HIT if links else CACHE_TTL_MISS)
            if links and cached is None:
                loop = asyncio.get_running_loop()
                try:
                    links = await asyncio.wait_for(
                        loop.run_in_executor(_executor, drop_dead, links),
                        timeout=DROP_DEAD_S,
                    )
                except Exception:
                    pass
            final = normalize_items(links, type_tag, kw.get("title") or "") if links else []
            async with lock:
                done += 1
                d = done
                if final:
                    found += 1
                f = found
            if final:
                await q.put(
                    {"t": "hit", "site": s["name"], "links": final, "done": d, "total": total, "found": f}
                )
            else:
                await q.put({"t": "miss", "site": s["name"], "done": d, "total": total})

    async def run_all():
        try:
            await asyncio.wait_for(asyncio.gather(*(one(s) for s in sites)), timeout=HUNT_DEADLINE_S)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        await q.put(None)

    runner = asyncio.create_task(run_all())

    async def watch_client():
        try:
            while not stop.is_set():
                if await request.is_disconnected():
                    stop.set()
                    runner.cancel()
                    await q.put(None)
                    return
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass

    watcher = asyncio.create_task(watch_client())
    try:
        while True:
            ev = await q.get()
            if ev is None:
                break
            yield (json.dumps(ev) + "\n").encode()
    finally:
        stop.set()
        watcher.cancel()
        runner.cancel()
        try:
            await runner
        except asyncio.CancelledError:
            pass
        try:
            await watcher
        except asyncio.CancelledError:
            pass
    if not await request.is_disconnected():
        yield (json.dumps({"t": "done", "found": found, "total": total}) + "\n").encode()


@app.get("/health")
async def health():
    ranked = sorted((s["name"] for s in SCRAPERS), key=hunt_key)
    lanes = _queue_lanes()
    return {
        "ok": True,
        "scrapers": len(SCRAPERS),
        "names": ranked,
        "hunts": sum(lanes),
        "shortest": min(lanes) if lanes else 0,
        "lanes": lanes,
    }


@app.get("/queue")
async def queue():
    lanes = _queue_lanes()
    return {"shortest": min(lanes) if lanes else 0, "lanes": lanes}


@app.get("/")
async def root():
    return {"service": "defe-api", "scrapers": len(SCRAPERS)}


@app.post("/")
async def download_stream(request: Request, body: Body, x_defe_manual: str | None = Header(None)):
    if x_defe_manual != "1":
        raise HTTPException(status_code=403)
    return StreamingResponse(
        stream_events(body, request),
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "X-Accel-Buffering": "no",
        },
    )

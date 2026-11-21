"""Follow one public download hop toward a file URL. No captcha/shortener bypass."""
import re

from bs4 import BeautifulSoup

GOOGLE = re.compile(r"https://video-downloads\.googleusercontent\.com/[^\s\"'<>]+")
GOFILE = re.compile(r"https://gofile\.io/d/[A-Za-z0-9]+")
PIXEL = re.compile(r"https?://pixeldrain\.(?:net|com|dev)/u/[A-Za-z0-9]+")
GAMER = re.compile(r"https?://gamerxyt\.com/hubcloud\.php\?[^\s\"'<>]+")
FASTD = re.compile(r"https?://fastdl\.zip/embed\?download=[A-Za-z0-9]+")
GOFLIX = re.compile(r"https?://goflix\.[a-z]+/[^\s\"'<>]+")
VIKING_F = re.compile(r"https?://(?:[\w-]+\.)?vikingfile\.com/f/[A-Za-z0-9]+")
KMHD_HOST = re.compile(
    r"(acefile\.|anidrive|topddl|drive\.google|gdflix|filepress|gofile|"
    r"hubdrive|hubcloud|pixeldrain|katdrive)",
    re.I,
)
UNWRAP = re.compile(
    r"nexdrive|gdflix|gdlink|hubcloud|vikingfile\.com/f/|kmhd\.eu|fastdl\.zip/embed",
    re.I,
)


def _ok(s, url):
    try:
        r = s.head(url, timeout=8, allow_redirects=True)
        code = int(getattr(r, "status_code", 0) or 0)
        if code in (403, 405, 501):
            r = s.get(url, timeout=8, headers={"Range": "bytes=0-0"}, allow_redirects=True)
            code = int(getattr(r, "status_code", 0) or 0)
        return 200 <= code < 400
    except Exception:
        return False


def _get(s, url, timeout=12, **kw):
    try:
        return s.get(url, timeout=timeout, **kw)
    except Exception:
        return None


def _uniq(urls):
    seen, out = set(), []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _nexdrive(s, url):
    r = _get(s, url)
    if not r or r.status_code != 200:
        return []
    m = FASTD.search(r.text)
    if not m:
        return []
    r2 = _get(s, m.group(0))
    if not r2:
        return []
    g = GOOGLE.search(r2.text)
    return [g.group(0)] if g else []


def _gdflix(s, url):
    r = _get(s, url)
    if not r or r.status_code != 200:
        return []
    html = r.text
    out = GOFILE.findall(html)
    for m in GOFLIX.finditer(html):
        r2 = _get(s, m.group(0))
        if not r2:
            continue
        out.extend(GOFILE.findall(r2.text))
        out.extend(VIKING_F.findall(r2.text))
    return _uniq(out)


def _hubcloud(s, url):
    r = _get(s, url)
    if not r or r.status_code != 200:
        return []
    m = GAMER.search(r.text)
    if not m:
        return []
    r2 = _get(s, m.group(0))
    if not r2:
        return []
    return _uniq(PIXEL.findall(r2.text) + GOFILE.findall(r2.text))


def _viking(s, url):
    r = _get(s, url, allow_redirects=True, headers={"Range": "bytes=0-0"})
    if not r:
        return [url]
    final = r.url or url
    return [final] if "/download/" in final else [url]


def _kmhd(s, url):
    r = _get(s, url)
    if not r or r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("http") and KMHD_HOST.search(href):
            out.append(href)
    return _uniq(out)


def closer(s, url):
    """Closer URLs, or [] to drop a sketchy hop, or [url] to keep the portal."""
    low = (url or "").lower()
    if "nexdrive" in low or "fastdl.zip/embed" in low:
        if "fastdl.zip/embed" in low:
            r = _get(s, url)
            g = GOOGLE.search(r.text) if r else None
            return [g.group(0)] if g else []
        return _nexdrive(s, url)
    if "gdflix" in low or "gdlink" in low:
        return _gdflix(s, url) or [url]
    if "hubcloud" in low:
        extra = [u for u in _hubcloud(s, url) if _ok(s, u)]
        return _uniq(extra + [url]) if extra else [url]
    if "vikingfile.com" in low and "/f/" in low:
        return _viking(s, url)
    if "kmhd.eu" in low:
        return _kmhd(s, url) or [url]
    return [url]


def expand(s, items, limit=12):
    out, seen, hops = [], set(), 0
    for it in items or []:
        url = it["url"] if isinstance(it, dict) else it
        if not url:
            continue
        low = url.lower()
        if UNWRAP.search(url):
            if hops < limit:
                hops += 1
                nxt = closer(s, url)
            elif "nexdrive" in low or "fastdl.zip" in low:
                nxt = []
            else:
                nxt = [url]
        else:
            nxt = [url]
        for u in nxt:
            if u in seen:
                continue
            seen.add(u)
            if isinstance(it, dict):
                out.append({**it, "url": u})
            else:
                out.append(u)
    return out

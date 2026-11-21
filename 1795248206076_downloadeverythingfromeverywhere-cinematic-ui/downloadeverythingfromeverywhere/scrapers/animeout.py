# WARNING: HTML Cloudflare 403; wp-json public
import html as htmlmod
import re
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

from scrapers import _http as requests
from bs4 import BeautifulSoup

BASE = "https://www.animeout.xyz"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 20
DL_RE = re.compile(
    r"nimbus\.animeout|(?:mega\.nz|drive\.google|mediafire|gofile|pixeldrain)",
    re.I,
)
SIDE_RE = re.compile(r"\bova\b|specials|director|henshuu|break[\s-]*time", re.I)
SIZE = re.compile(r"(?<![A-Za-z0-9.])(\d{1,4}(?:\.\d{1,2})?)\s*(KB|MB|GB|TB)\b", re.I)
SKIP_HEAD = re.compile(
    r"mega\.nz|gofile|drive\.google|mediafire|pixeldrain|nimbus\.|ddl\.animeout",
    re.I,
)
_qcache = {}


def _canon(num, unit):
    n = str(num)
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return f"{n}{unit.upper()}"


def _size_tag(text):
    m = SIZE.search(text or "")
    return _canon(m.group(1), m.group(2)) if m else None


def _bytes_tag(n):
    try:
        n = float(n)
    except Exception:
        return None
    if n <= 0:
        return None
    units = ("B", "KB", "MB", "GB", "TB")
    i = 0
    while n >= 1024 and i < 4:
        n /= 1024
        i += 1
    if i < 1:
        return None
    s = f"{n:.2f}".rstrip("0").rstrip(".")
    return f"{s}{units[i]}"


def _file_len(r):
    cr = r.headers.get("Content-Range") or ""
    m = re.search(r"/(\d+)\s*$", cr)
    if m:
        return _bytes_tag(m.group(1))
    if int(getattr(r, "status_code", 0) or 0) == 206:
        return None
    cl = r.headers.get("Content-Length")
    if cl and str(cl).isdigit() and int(cl) > 4096:
        return _bytes_tag(cl)
    return None


def _has_size(tags):
    return any(re.fullmatch(r"\d+(?:\.\d+)?(?:KB|MB|GB|TB)", t or "", re.I) for t in (tags or []))


def _head_size(s, url):
    if not url or SKIP_HEAD.search(url):
        return None
    host = urlsplit(url).netloc.lower()
    path = url.lower().split("?")[0]
    if "public.animeout" not in host and not path.endswith((".mkv", ".mp4")):
        return None
    try:
        r = s.head(url, timeout=TIMEOUT, allow_redirects=True)
        if _is_file(r):
            st = _file_len(r)
            if st:
                return st
        r = s.get(url, timeout=TIMEOUT, allow_redirects=True, headers={"Range": "bytes=0-0"})
        if _is_file(r):
            return _file_len(r)
    except Exception:
        return None
    return None


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _text(raw):
    return _norm(htmlmod.unescape(re.sub(r"<[^>]+>", " ", raw or "")))


def _abs(url):
    p = urlsplit((url or "").strip())
    if not p.scheme:
        return url
    path = quote(unquote(p.path), safe="/[]()'-._~")
    return urlunsplit((p.scheme, p.netloc, path, p.query, p.fragment))


def _is_file(r):
    if not r or int(getattr(r, "status_code", 0) or 0) not in (200, 206):
        return False
    ct = (r.headers.get("Content-Type") or "").lower()
    cd = (r.headers.get("Content-Disposition") or "").lower()
    if "html" in ct:
        return False
    return (
        ct.startswith("video/")
        or "octet-stream" in ct
        or ".mkv" in cd
        or (r.url or "").lower().split("?")[0].endswith(".mkv")
    )


def _file_url(html):
    for m in re.finditer(r"""["'](https?://[^"']+)["']""", html or ""):
        u = m.group(1)
        host = urlsplit(u).netloc.lower()
        if host.endswith("www.animeout.xyz") or host.endswith("ddl.animeout.com"):
            continue
        path = u.lower().split("?")[0]
        if path.endswith((".mkv", ".mp4")) or re.search(
            r"mega\.nz|drive\.google|mediafire|gofile|pixeldrain", u, re.I
        ):
            return _abs(u)
    return None


def _unwrap(s, url):
    try:
        r = s.get(url, timeout=TIMEOUT, allow_redirects=True, headers={"Range": "bytes=0-0"})
        if _is_file(r):
            return r.url or url
        html = r.text or ""
        u = _file_url(html)
        if u:
            return u
        soup = BeautifulSoup(html, "html.parser")
        a = soup.find("a", href=re.compile(r"public\.php", re.I))
        if not a:
            return None
        href = urljoin(str(getattr(r, "url", "") or url), a["href"])
        r2 = s.get(href, timeout=TIMEOUT, allow_redirects=True)
        if _is_file(r2):
            return r2.url or href
        return _file_url(r2.text or "")
    except Exception:
        return None


def _direct(s, rows):
    out = []
    for it in rows:
        u = it.get("url") or ""
        if "nimbus.animeout" in u.lower():
            u = _unwrap(s, u)
            if not u:
                continue
            it = {**it, "url": u}
        tags = list(it.get("tags") or [])
        if not _has_size(tags):
            st = _head_size(s, it.get("url") or "")
            if st:
                tags.append(st)
                it = {**it, "tags": tags}
        out.append(it)
    return out


def _queries(title):
    t = (title or "").strip()
    if not t:
        return []
    out = []
    for q in (f'"{t}"', t, re.split(r"\s*[-–—]\s*", t, maxsplit=1)[0].strip(), " ".join(_norm(t).split()[:2])):
        q = (q or "").strip()
        if q and q not in out:
            out.append(q)
    return out


def _search(s, q):
    if q in _qcache:
        return _qcache[q]
    items = []
    try:
        r = s.get(f"{BASE}/wp-json/wp/v2/posts", params={"search": q, "per_page": 20}, timeout=TIMEOUT)
        if r.ok:
            data = r.json()
            for p in data if isinstance(data, list) else []:
                title = htmlmod.unescape(re.sub(r"<[^>]+>", "", (p.get("title") or {}).get("rendered") or ""))
                html = (p.get("content") or {}).get("rendered") or ""
                items.append({"title": title, "url": p.get("link"), "html": html, "text": _text(html)})
    except Exception:
        items = []
    _qcache[q] = items
    return items


def _posts(s, title):
    seen, items = set(), []
    for q in _queries(title):
        for p in _search(s, q):
            u = p.get("url")
            if not u or u in seen:
                continue
            seen.add(u)
            items.append(p)
    return items


def _title_ok(p, title):
    t = _norm(title)
    if not t:
        return False
    nt = _norm(p.get("title") or "")
    if t in nt:
        return len(t.split()) >= 2 or nt == t or nt.startswith(t + " ")
    prefix = " ".join(t.split()[:2])
    if len(t.split()) >= 2 and len(prefix) >= 7 and prefix in nt:
        return True
    words = [w for w in t.split() if len(w) >= 3]
    if len(words) < 3:
        return False
    head = nt + " " + (p.get("text") or "")[:800]
    return all(re.search(rf"\b{re.escape(w)}\b", head) for w in words)


def _seasons(text):
    found = set()
    found.update(int(x) for x in re.findall(r"season\s*0*(\d+)", text or "", re.I))
    found.update(int(x) for x in re.findall(r"\bs0*(\d+)\b", text or "", re.I))
    found.update(int(x) for x in re.findall(r"(\d+)(?:st|nd|rd|th)\s*season", text or "", re.I))
    return found


def _is_movie(p):
    b = (p.get("title") or "") + " " + (p.get("text") or "")[:400]
    return bool(re.search(r"\bmovie\b|type:\s*movie", b, re.I)) and not re.search(
        r"tv series", p.get("title") or "", re.I
    )


def _season_ok(p, season):
    if SIDE_RE.search(p.get("title") or "") or _is_movie(p):
        return False
    s = int(season)
    found = _seasons((p.get("title") or "") + " " + (p.get("text") or "")[:800])
    if s in found:
        return True
    if found:
        return False
    return s == 1 and bool(re.search(r"complete|batch", p.get("title") or "", re.I))


def _ep_ok(name, season, episode):
    s, e = int(season), int(episode)
    if re.search(rf"s0*{s}\s*e0*{e}\b", name or "", re.I):
        return True
    return bool(re.search(rf"[-–]\s*0*{e}(?:\s*\[|\s+\d{{3,4}}p|\s*$)", name or ""))


def _qmap(text):
    out = {}
    for q, n, u in re.findall(
        r"(\d{3,4})\s*p\s*[:\-–]?\s*(\d{1,4}(?:\.\d{1,2})?)\s*(KB|MB|GB|TB)\b",
        text or "",
        re.I,
    ):
        out[q] = _canon(n, u)
    for n, u, q in re.findall(
        r"(\d{1,4}(?:\.\d{1,2})?)\s*(KB|MB|GB|TB)\s*[:\-–]?\s*(\d{3,4})\s*p\b",
        text or "",
        re.I,
    ):
        out.setdefault(q, _canon(n, u))
    return out


def _links(html, title=""):
    soup = BeautifulSoup(html or "", "html.parser")
    qmap = _qmap(title)
    out, seen = [], set()
    cur = None
    for el in soup.descendants:
        name = getattr(el, "name", None)
        if name in ("h2", "h3", "h4") or (
            name == "strong" and re.search(r"download links|\d{3,4}p", el.get_text(" ", strip=True), re.I)
        ):
            sz = _size_tag(el.get_text(" ", strip=True))
            if sz:
                cur = sz
        if name != "a":
            continue
        href = (el.get("href") or "").strip()
        if not href or "staff/img" in href.lower() or not DL_RE.search(href):
            continue
        if href.lower().split("?")[0].endswith((".jpg", ".png", ".gif", ".webp")):
            continue
        url = _abs(href)
        if url in seen:
            continue
        seen.add(url)
        nm = unquote(url.split("?")[0].rstrip("/").split("/")[-1]) or el.get_text(" ", strip=True)
        sz = _size_tag(nm) or cur
        if not sz:
            qm = re.search(r"(\d{3,4})\s*p", nm, re.I)
            if qm:
                sz = qmap.get(qm.group(1))
        row = {"url": url, "name": nm}
        if sz:
            row["tags"] = [sz]
        out.append(row)
    return out


def _dedup(rows):
    seen, out = set(), []
    for it in rows:
        u = it.get("url") if isinstance(it, dict) else it
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out


def _year_ok(p, year):
    if not year:
        return True
    return str(year) in (p.get("title") or "") or str(year) in (p.get("text") or "")[:800]


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        posts = [p for p in _posts(s, title) if _title_ok(p, title) and _is_movie(p) and _year_ok(p, year)]
        out = []
        for p in posts[:3]:
            out.extend(_links(p.get("html") or "", p.get("title") or ""))
        return _dedup(_direct(s, out))
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        posts = [p for p in _posts(s, title) if _title_ok(p, title) and _season_ok(p, season)]
        out = []
        for p in posts[:3]:
            out.extend(_links(p.get("html") or "", p.get("title") or ""))
        return _dedup(_direct(s, out))
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        posts = [p for p in _posts(s, title) if _title_ok(p, title) and not _is_movie(p)]
        main = [p for p in posts if not SIDE_RE.search(p.get("title") or "")]
        out = []
        for p in (main or posts)[:6]:
            for it in _links(p.get("html") or "", p.get("title") or ""):
                blob = it["name"] + " " + it["url"]
                if _ep_ok(blob, season, episode):
                    out.append(it)
        return _dedup(_direct(s, out))
    except Exception:
        return []


if __name__ == "__main__":
    import json
    from pathlib import Path

    base = Path(__file__).resolve().parent
    avatar = json.loads((base / "avatar.json").read_text())
    bb = json.loads((base / "breaking_bad.json").read_text())
    print("avatar", dlmovie(avatar["title"], year=int(avatar["release_date"][:4]), tmdb_id=avatar["id"], imdb_id=avatar.get("imdb_id")))
    print(
        "breaking_bad_s1",
        dlseries(bb["name"], 1, year=int(bb["first_air_date"][:4]), tmdb_id=bb["id"], imdb_id=(bb.get("external_ids") or {}).get("imdb_id")),
    )
    print(
        "breaking_bad_s1e5",
        dlseriesepisode(bb["name"], 1, 5, year=int(bb["first_air_date"][:4]), tmdb_id=bb["id"], imdb_id=(bb.get("external_ids") or {}).get("imdb_id")),
    )
    rz = "Re:ZERO -Starting Life in Another World-"
    print("rezero_s1", dlseries(rz, 1, year=2016, tmdb_id=65942, imdb_id="tt5607616"))
    print("rezero_s1e78", dlseriesepisode(rz, 1, 78, year=2016, tmdb_id=65942, imdb_id="tt5607616"))
    print("rezero_s1e1", dlseriesepisode(rz, 1, 1, year=2016, tmdb_id=65942, imdb_id="tt5607616"))
    print("rezero_short", dlseriesepisode("Re:Zero", 1, 78, year=2016, tmdb_id=65942, imdb_id="tt5607616"))
    print("rezero_jp", dlseriesepisode("Re:Zero kara Hajimeru Isekai Seikatsu", 1, 1, year=2016, tmdb_id=65942, imdb_id="tt5607616"))
    print("your_name", dlmovie("Your Name", year=2016, tmdb_id=372058))
    print("kimi_no_na_wa", dlmovie("Kimi no Na wa", year=2016, tmdb_id=372058))

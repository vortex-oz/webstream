import re
from urllib.parse import quote_plus, urljoin

from scrapers import _http as requests
from bs4 import BeautifulSoup

BASE = "https://www.mynimeku.com"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}
TIMEOUT = 20
FILE = re.compile(
    r"file\.mydriveku\.my\.id/api/v1/(public|private)/([^/?&]+)",
    re.I,
)
INDO = re.compile(r"\bsubtitle\s+indonesia\b|\bsub(?:title)?\s*indo(?:nesia)?\b", re.I)
QUAL = re.compile(r"(\d{3,4})\s*p", re.I)


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _head(title):
    t = re.split(r"\s+-", (title or "").strip(), 1)[0].strip(" -:").strip()
    return t or (title or "").strip()


def _title_ok(post, title, year=None):
    nt, short = _norm(post), _norm(_head(title))
    words = [w for w in short.split() if len(w) >= 2]
    if not words:
        return False
    hit = all(re.search(rf"\b{re.escape(w)}\b", nt) for w in words)
    if not hit:
        compact = re.sub(r"[^a-z0-9]+", "", short)
        hit = len(compact) >= 8 and compact in re.sub(r"[^a-z0-9]+", "", nt)
    if not hit:
        return False
    if len(words) == 1:
        return year is not None and bool(re.search(rf"\b{int(year)}\b", nt))
    return True


def _season_ok(post, season):
    t = post or ""
    nth = re.search(r"(\d+)(?:st|nd|rd|th)\s+season", t, re.I)
    m = re.search(r"season\s*(\d+)", t, re.I)
    n = int(nth.group(1) if nth else m.group(1)) if (nth or m) else None
    s = int(season)
    if n is None:
        return s == 1
    return n == s


def _search(s, q):
    items = []
    try:
        r = s.get(f"{BASE}/?s={quote_plus(q)}", timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].split("?")[0]
            if "/series/" not in href or href in seen:
                continue
            t = a.get_text(" ", strip=True)
            if not t:
                continue
            seen.add(href)
            items.append({"title": t, "url": href})
    except Exception:
        pass
    return items


def _pick(items, title, season=None, year=None):
    out = []
    for it in items:
        t = it.get("title") or ""
        if not _title_ok(t, title, year=year):
            continue
        if season is not None and not _season_ok(t, season):
            continue
        out.append(it["url"])
    return out


def _size_tag(n):
    if isinstance(n, str):
        m = re.search(r"([\d.]+)\s*(TB|GB|MB|KB)\b", n, re.I)
        if not m:
            return None
        num = m.group(1)
        if "." in num:
            num = num.rstrip("0").rstrip(".")
        return f"{num}{m.group(2).upper()}" if num else None
    try:
        n = float(n)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    units = ("B", "KB", "MB", "GB", "TB")
    i = 0
    while n >= 1024 and i < 4:
        n /= 1024
        i += 1
    if i == 0:
        return None
    s = f"{n:.2f}".rstrip("0").rstrip(".")
    return f"{s}{units[i]}"


def _file_size(s, page, file_url):
    try:
        r = s.get(page, timeout=TIMEOUT)
        if r.status_code == 200:
            m = re.search(r"Ukuran File:\s*([\d.]+)\s*(TB|GB|MB|KB)\b", r.text or "", re.I)
            if m:
                return _size_tag(m.group(0))
        h = s.head(file_url, timeout=TIMEOUT, allow_redirects=True)
        cr = h.headers.get("Content-Range") or ""
        m = re.search(r"/(\d+)\s*$", cr)
        if m:
            return _size_tag(int(m.group(1)))
        cl = h.headers.get("Content-Length")
        if cl and str(cl).isdigit() and int(cl) > 0:
            return _size_tag(int(cl))
    except Exception:
        return None
    return None


def _files(s, html):
    out, seen = [], set()
    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one(".mynimeku-episode-head__title, h1.entry-title, .entry-title")
    title = INDO.sub("", el.get_text(" ", strip=True) if el else "")
    title = re.sub(r"\s+", " ", title).strip(" :-")
    for a in soup.find_all("a", href=True):
        m = FILE.search(a["href"])
        if not m:
            continue
        u = f"https://file.mydriveku.my.id/{m.group(1).lower()}/{m.group(2)}"
        if u in seen:
            continue
        seen.add(u)
        card = a.find_parent(class_="mynimeku-episode-download-card")
        q = ""
        if card:
            res = card.find(class_="mynimeku-episode-download-card__res")
            if res:
                qm = QUAL.search(res.get_text(" ", strip=True))
                if qm:
                    q = f"{qm.group(1)}p"
        name = " ".join(x for x in (title, q) if x) or q or "download"
        tags = ["Indonesian"]
        if q:
            tags.append(q)
        st = _file_size(s, a["href"], u)
        if st:
            tags.append(st)
        out.append({"url": u, "name": name, "tags": tags})
    return out


def _episode_url(html, episode):
    soup = BeautifulSoup(html, "html.parser")
    e = int(episode)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/episode/" not in href:
            continue
        if re.search(rf"episode-0*{e}(?:\D|$)", href, re.I) or re.search(
            rf"episode\s*0*{e}\b", a.get_text(" ", strip=True), re.I
        ):
            return urljoin(BASE + "/", href)
    return None


def _series(s, title, season=None, year=None):
    q = _head(title)
    posts = _pick(_search(s, q), title, season=season, year=year)
    if not posts and q != title:
        posts = _pick(_search(s, title), title, season=season, year=year)
    return posts


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        posts = _series(s, title, season=1, year=year)
        if not posts:
            return []
        r = s.get(posts[0], timeout=TIMEOUT)
        ep = _episode_url(r.text, 1)
        if not ep:
            return _files(s, r.text) or []
        r = s.get(ep, timeout=TIMEOUT)
        return _files(s, r.text) or []
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    return


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        posts = _series(s, title, season=season, year=year)
        if not posts:
            return []
        r = s.get(posts[0], timeout=TIMEOUT)
        ep = _episode_url(r.text, episode)
        if not ep:
            return []
        r = s.get(ep, timeout=TIMEOUT)
        return _files(s, r.text) or []
    except Exception:
        return []


if __name__ == "__main__":
    import json
    from pathlib import Path
    base = Path(__file__).resolve().parent
    avatar = json.loads((base / "avatar.json").read_text())
    bb = json.loads((base / "breaking_bad.json").read_text())
    print("avatar", dlmovie(avatar["title"], year=int(avatar["release_date"][:4]), tmdb_id=avatar["id"], imdb_id=avatar.get("imdb_id")))
    print("breaking_bad_s1", dlseries(bb["name"], 1, year=int(bb["first_air_date"][:4]), tmdb_id=bb["id"], imdb_id=(bb.get("external_ids") or {}).get("imdb_id")))
    print("breaking_bad_s1e5", dlseriesepisode(bb["name"], 1, 5, year=int(bb["first_air_date"][:4]), tmdb_id=bb["id"], imdb_id=(bb.get("external_ids") or {}).get("imdb_id")))

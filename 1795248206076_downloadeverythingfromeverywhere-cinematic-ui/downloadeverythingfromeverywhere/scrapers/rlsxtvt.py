import re
from urllib.parse import quote_plus

from scrapers import _http as requests
from bs4 import BeautifulSoup

BASE = "https://rlsxtvt.icu"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
TIMEOUT = 20
HOST_RE = re.compile(
    r"clicknupload|rapidgator|nitroflare|nitro\.download|turbobit|turb\.cc|"
    r"filefactory|drop\.download|multiup",
    re.I,
)


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _size_tag(n):
    m = re.search(r"([\d.,]+)\s*(TiB|GiB|MiB|KiB|TB|GB|MB|KB)", str(n or ""), re.I)
    if not m:
        return None
    num = m.group(1).replace(",", "")
    if "." in num:
        num = num.rstrip("0").rstrip(".")
    if not num:
        return None
    return f"{num}{m.group(2).upper().replace('IB', 'B')}"


def _search(s, q):
    items = []
    try:
        r = s.get(f"{BASE}/wp-json/wp/v2/posts", params={"search": q, "per_page": 20}, timeout=TIMEOUT)
        if r.ok:
            for p in r.json():
                items.append(
                    {
                        "title": re.sub(r"<[^>]+>", "", (p.get("title") or {}).get("rendered") or ""),
                        "url": p.get("link"),
                    }
                )
            return items
    except Exception:
        pass
    try:
        r = s.get(f"{BASE}/?s={quote_plus(q)}", timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("h1 a, h2 a, h3 a, .entry-title a"):
            href, t = a.get("href"), a.get_text(strip=True)
            if href and t:
                items.append({"title": t, "url": href})
    except Exception:
        pass
    return items


def _pick(items, title, year=None, season=None):
    wt = _norm(title)
    out = []
    for it in items:
        t = it.get("title") or ""
        nt = _norm(t)
        if wt not in nt:
            continue
        if year and str(year) not in t and str(year) not in nt:
            if season is None:
                continue
        if season is not None:
            if not re.search(rf"\bs0*{int(season)}\b", t, re.I) and not re.search(
                rf"season\s*0*{int(season)}\b", t, re.I
            ):
                continue
            if re.search(r"\bs\d{1,2}e\d{1,2}\b", t, re.I):
                continue
        else:
            if re.search(r"\bs\d{1,2}(e\d{1,2})?\b", t, re.I) and "complete" not in nt:
                continue
        out.append(it["url"])
    return out


def _hosts(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    name = ""
    m = re.search(r"Release Name\s*:\s*(.+)", text, re.I)
    if m:
        name = m.group(1).strip().split("\n")[0].strip()
    st = None
    m = re.search(r"Size\s*:\s*([\d.,]+\s*(?:TiB|GiB|MiB|KiB|TB|GB|MB|KB))", text, re.I)
    if m:
        st = _size_tag(m.group(1))
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if HOST_RE.search(href):
            nm = name or a.get_text(" ", strip=True) or href.split("/")[-1]
            urls.append({"url": href, "name": nm, "tags": [st] if st else []})
    seen, out = set(), []
    for u in urls:
        if u["url"] not in seen:
            seen.add(u["url"])
            out.append(u)
    return out


def _collect(s, urls):
    out = []
    for u in urls[:5]:
        try:
            r = s.get(u, timeout=TIMEOUT)
            out.extend(_hosts(r.text))
        except Exception:
            continue
    seen, dedup = set(), []
    for it in out:
        if it["url"] not in seen:
            seen.add(it["url"])
            dedup.append(it)
    return dedup


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = f"{title} {year}" if year else title
        posts = _pick(_search(s, q), title, year=year)
        if not posts:
            posts = _pick(_search(s, title), title, year=year)
        return _collect(s, posts) or []
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = f"{title} S{int(season):02d}"
        posts = _pick(_search(s, q), title, year=year, season=season)
        if not posts:
            posts = _pick(_search(s, title), title, year=year, season=season)
        return _collect(s, posts) or []
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    return


if __name__ == "__main__":
    import json
    from pathlib import Path
    base = Path(__file__).resolve().parent
    avatar = json.loads((base / "avatar.json").read_text())
    bb = json.loads((base / "breaking_bad.json").read_text())
    bb_s1 = json.loads((base / "breaking_bad_s1.json").read_text())
    print("avatar", dlmovie(avatar["title"], year=int(avatar["release_date"][:4]), tmdb_id=avatar["id"], imdb_id=avatar.get("imdb_id")))
    print("breaking_bad_s1", dlseries(bb["name"], 1, year=int(bb["first_air_date"][:4]), tmdb_id=bb["id"], imdb_id=(bb.get("external_ids") or {}).get("imdb_id")))
    print("breaking_bad_s1e5", dlseriesepisode(bb["name"], 1, 5, year=int(bb["first_air_date"][:4]), tmdb_id=bb["id"], imdb_id=(bb.get("external_ids") or {}).get("imdb_id")))

import re
from urllib.parse import quote

from scrapers import _http as requests
from scrapers._tags import tags_from
from bs4 import BeautifulSoup

BASE = "https://multishows.top"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
TIMEOUT = 20
DL_RE = re.compile(r"(gdlink\.dev|gdflix\.dev)/file/", re.I)


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _slug(title):
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _search_links(s, title, kind):
    r = s.get(f"{BASE}/search/{quote(title)}", timeout=TIMEOUT)
    soup = BeautifulSoup(r.text, "html.parser")
    prefix = f"{BASE}/{kind}/"
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0].rstrip("/")
        if not href.startswith(prefix):
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append(href)
    return out


def _pick_path(s, urls, title, year=None):
    want = _slug(title)
    exact = [u for u in urls if u.rstrip("/").endswith("/" + want)]
    if exact:
        if year is None:
            return exact[0]
        for u in exact:
            try:
                r = s.get(u, timeout=TIMEOUT)
                if str(year) in r.text:
                    return u
            except Exception:
                pass
        return exact[0]
    wt = _norm(title)
    for u in urls:
        slug = u.rstrip("/").split("/")[-1]
        if _norm(slug.replace("-", " ")) == wt:
            return u
    return None


def _dl_links(s, html, prefix=""):
    soup = BeautifulSoup(html, "html.parser")
    urls, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not DL_RE.search(href) or href in seen:
            continue
        seen.add(href)
        q = ""
        li = a.find_parent("li")
        if li:
            d = li.find("div")
            if d:
                q = d.get_text(" ", strip=True)
        if not q:
            text = a.get_text(" ", strip=True)
            q = text if text.lower() not in {"download", "gdflix", "gdlink"} else ""
        name = " ".join(x for x in (prefix, q) if x).strip()
        tags = tags_from(name)
        if not any(re.fullmatch(r"\d+(?:\.\d+)?(?:KB|MB|GB|TB)", t, re.I) for t in tags):
            try:
                r = s.get(href, timeout=TIMEOUT)
                m = re.search(r"Size\s*:\s*([\d.]+)\s*(KB|MB|GB|TB)\b", r.text, re.I)
                if m:
                    tags = tags_from(name, f"{m.group(1)}{m.group(2)}")
            except Exception:
                pass
        urls.append({"url": href, "name": name or "download", "tags": tags})
    if not urls:
        for m in re.finditer(r"https?://(?:gdlink\.dev|gdflix\.dev)/file/[A-Za-z0-9_-]+", html):
            if m.group(0) not in seen:
                seen.add(m.group(0))
                urls.append({"url": m.group(0), "name": prefix or "download", "tags": tags_from(prefix)})
    return urls


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        url = _pick_path(s, _search_links(s, title, "movie"), title, year=year)
        if not url:
            return []
        r = s.get(url, timeout=TIMEOUT)
        from scrapers._resolve import expand

        return expand(s, _dl_links(s, r.text, f"{title} ({year})" if year else title) or [])
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        show = _pick_path(s, _search_links(s, title, "tv-show"), title, year=year)
        slug = show.rstrip("/").split("/")[-1] if show else _slug(title)
        url = f"{BASE}/episode/{slug}/{int(season)}-{int(episode)}"
        r = s.get(url, timeout=TIMEOUT)
        if r.status_code != 200:
            return []
        from scrapers._resolve import expand

        return expand(s, _dl_links(s, r.text, f"{title} S{int(season):02d}E{int(episode):02d}") or [])
    except Exception:
        return []


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

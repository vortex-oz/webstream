import re
from urllib.parse import quote_plus, urljoin

from scrapers import _http as requests
from bs4 import BeautifulSoup

BASE = "https://thenkiri.com"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 25


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _get(url):
    try:
        r = _session().get(url, headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        return r
    except Exception:
        return None


def _search(query):
    r = _get(f"{BASE}/?s={quote_plus(query)}")
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    seen = set()
    for a in soup.select("h2 a, h3 a, .entry-title a"):
        href = a.get("href") or ""
        title = a.get_text(" ", strip=True)
        if not href or href in seen:
            continue
        seen.add(href)
        out.append((title, urljoin(BASE, href)))
    return out


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _pick(results, title, year=None, want_tv=False, season=None):
    nt = _norm(title)
    scored = []
    for t, url in results:
        tl = t.lower()
        nn = _norm(t)
        if want_tv:
            if "movie" in tl and "tv series" not in tl and "complete" not in tl:
                continue
            if season is not None:
                s = f"s{int(season):02d}"
                if s not in nn and f"season{int(season)}" not in nn:
                    continue
        else:
            if "tv series" in tl:
                continue
        if nt not in nn:
            continue
        score = 1
        if year is not None and str(year) in t:
            score = 2
        scored.append((score, url, t))
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], len(x[2])))
    return scored[0][1]


def _wella_items(soup, post_title="", keep=None):
    from urllib.parse import unquote
    from scrapers._tags import tags_from, clean_name

    size, out, seen = "", [], set()
    phrase = re.compile(
        r"(?:this video is|these videos are around|download size)\s*:?\s*"
        r"(\d+(?:[.,]\d+)?\s*(?:KB|MB|GB|TB))",
        re.I,
    )
    for el in soup.descendants:
        if isinstance(el, str):
            m = phrase.search(el)
            if m:
                size = m.group(1)
            continue
        if getattr(el, "name", None) != "a":
            continue
        href = el.get("href") or ""
        if "downloadwella.com" not in href or href in seen:
            continue
        if keep is not None and href not in keep:
            continue
        seen.add(href)
        text = el.get_text(" ", strip=True) if hasattr(el, "get_text") else ""
        path = unquote(href.rstrip("/").split("/")[-1])
        fname = re.sub(r"\.html?$", "", path, flags=re.I)
        name = clean_name(fname) or clean_name(text) or clean_name(post_title) or fname or text or "Nkiri"
        tags = tags_from(name, text, post_title, href, size)
        out.append({"url": href, "name": name, "tags": tags})
    return out


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        q = f"{title} {year}" if year else title
        url = _pick(_search(q), title, year=year, want_tv=False)
        if not url:
            url = _pick(_search(title), title, year=year, want_tv=False)
        if not url:
            return []
        r = _get(url)
        if not r:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        h = soup.select_one("h1, .entry-title")
        return _wella_items(soup, h.get_text(" ", strip=True) if h else title)
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    return


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        q = f"{title} S{int(season):02d}"
        url = _pick(_search(q), title, year=year, want_tv=True, season=season)
        if not url:
            url = _pick(_search(title), title, year=year, want_tv=True, season=season)
        if not url:
            return []
        r = _get(url)
        if not r:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        h = soup.select_one("h1, .entry-title")
        post_title = h.get_text(" ", strip=True) if h else title
        ep_pat = re.compile(rf"[Ss]{int(season):02d}[Ee]{int(episode):02d}")
        matched = {
            a["href"]
            for a in soup.find_all("a", href=True)
            if "downloadwella.com" in a["href"]
            and (ep_pat.search(a["href"]) or ep_pat.search(a.get_text(" ", strip=True)))
        }
        return _wella_items(soup, post_title, keep=matched or None)
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

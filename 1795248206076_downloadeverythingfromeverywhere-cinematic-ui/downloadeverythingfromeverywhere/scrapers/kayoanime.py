import re
from urllib.parse import quote_plus

from scrapers import _http as requests
from bs4 import BeautifulSoup

BASE = "https://kayoanime.com"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}
TIMEOUT = 20
HOST_RE = re.compile(r"drive\.google\.com/drive/(?:folders|file)/", re.I)


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _head(title):
    t = re.split(r"\s+-", (title or "").strip(), 1)[0].strip(" -:").strip()
    return t or (title or "").strip()


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
        for a in soup.find_all("a", href=True):
            href, t = a.get("href"), a.get_text(strip=True)
            if href and t and BASE in href and href != BASE + "/":
                items.append({"title": t, "url": href})
    except Exception:
        pass
    return items


def _title_ok(post, title):
    nt, short = _norm(post), _norm(_head(title))
    if short and short in nt:
        return True
    compact = re.sub(r"[^a-z0-9]+", "", short)
    return len(compact) >= 4 and compact in re.sub(r"[^a-z0-9]+", "", nt)


def _pick(items, title, year=None, season=None):
    return [it["url"] for it in items if _title_ok(it.get("title") or "", title)]


def _size_tag(blob):
    m = re.search(r"([\d.]+)\s*(TB|GB|MB|KB)\b", blob or "", re.I)
    if not m:
        return None
    num = m.group(1)
    if "." in num:
        num = num.rstrip("0").rstrip(".")
    return f"{num}{m.group(2).upper()}" if num else None


def _item(url, name):
    row = {"url": url, "name": name or "download"}
    st = _size_tag(name)
    if st:
        row["tags"] = [st]
    return row


def _season_num(t):
    m = re.search(r"(?:season\s*0*|^s0*)(\d+)\b", t or "", re.I)
    return int(m.group(1)) if m else None


def _hosts(html, season=None, episode=None):
    soup = BeautifulSoup(html, "html.parser")
    pairs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if HOST_RE.search(href):
            pairs.append((href, a.get_text(" ", strip=True)))
    picked = []
    if episode is not None:
        e = int(episode)
        picked = [
            (u, t)
            for u, t in pairs
            if re.search(rf"(?:episode|ep)\s*0*{e}\b|(?:^|[\s])e0*{e}\b|\s-\s0*{e}\b", t, re.I)
        ]
        if not picked:
            numbered = [(n, u, t) for u, t in pairs if (n := _season_num(t)) is not None]
            if numbered:
                if e <= 25:
                    want = int(season) if season is not None else 1
                    picked = [(u, t) for n, u, t in numbered if n == want]
                else:
                    mx = max(n for n, _, _ in numbered)
                    picked = [(u, t) for n, u, t in numbered if n == mx]
    elif season is not None:
        s = int(season)
        picked = [(u, t) for u, t in pairs if _season_num(t) == s]
    if not picked:
        picked = pairs
    seen, out = set(), []
    for u, t in picked:
        if u not in seen:
            seen.add(u)
            out.append(_item(u, t))
    return out


def _collect(s, urls, season=None, episode=None):
    out = []
    for u in urls[:4]:
        try:
            r = s.get(u, timeout=TIMEOUT)
            out.extend(_hosts(r.text, season=season, episode=episode))
        except Exception:
            continue
    seen, dedup = set(), []
    for it in out:
        u = it["url"]
        if u not in seen:
            seen.add(u)
            dedup.append(it)
    return dedup


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = _head(title)
        posts = _pick(_search(s, q), title, year=year)
        if not posts and q != title:
            posts = _pick(_search(s, title), title, year=year)
        return _collect(s, posts) or []
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = _head(title)
        posts = _pick(_search(s, q), title, year=year, season=season)
        if not posts and q != title:
            posts = _pick(_search(s, title), title, year=year, season=season)
        return _collect(s, posts, season=season) or []
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = _head(title)
        posts = _pick(_search(s, q), title, year=year, season=season)
        if not posts and q != title:
            posts = _pick(_search(s, title), title, year=year, season=season)
        return _collect(s, posts, season=season, episode=episode) or []
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

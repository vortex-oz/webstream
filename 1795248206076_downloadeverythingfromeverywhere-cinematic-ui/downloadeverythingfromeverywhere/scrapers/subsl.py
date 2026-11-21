import re

from scrapers import _http as requests
from scrapers._tags import format_size, tags_from

SITE = "https://subsl.top"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}
TIMEOUT = 20
_API = None


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _api_base(s):
    global _API
    if _API:
        return _API
    try:
        r = s.get(SITE, timeout=TIMEOUT)
        chunks = list(set(re.findall(r"/_next/static/chunks/[^\"']+\.js", r.text)))
        for ch in chunks:
            t = s.get(SITE + ch, timeout=TIMEOUT).text
            m = re.search(r'let r="(https://[^"]+)",a=\{getTrendingMovies', t)
            if m:
                _API = m.group(1).rstrip("/")
                return _API
            m = re.search(r'(https://[a-z0-9\-]+\.trycloudflare\.com)', t)
            if m:
                _API = m.group(1).rstrip("/")
                return _API
    except Exception:
        pass
    return None


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _item(s, url, name=""):
    tags = tags_from(name)
    try:
        h = s.head(url, timeout=TIMEOUT, allow_redirects=True)
        cl = h.headers.get("Content-Length")
        st = format_size(int(cl)) if cl and str(cl).isdigit() else None
        if st and st not in tags:
            tags.insert(0, st)
    except Exception:
        pass
    return {"url": url, "name": name or "download", "tags": tags}


def _pick_movie(movies, title, year=None, imdb_id=None):
    wt = _norm(title)
    for m in movies or []:
        if imdb_id and (m.get("imdb_code") or "").lower() == imdb_id.lower():
            return m
    for m in movies or []:
        if _norm(m.get("title")) == wt:
            if year is None or m.get("year") == year or str(m.get("year")) == str(year):
                return m
    for m in movies or []:
        if wt in _norm(m.get("title")):
            if year is None or m.get("year") == year or str(m.get("year")) == str(year):
                return m
    return None


def _pick_show(shows, title, year=None, imdb_id=None, tmdb_id=None):
    wt = _norm(title)
    for sh in shows or []:
        code = (sh.get("imdb_code") or "").lower()
        if imdb_id and code == imdb_id.lower():
            return sh
        if tmdb_id and code in (f"tv{tmdb_id}", str(tmdb_id)):
            return sh
    for sh in shows or []:
        if _norm(sh.get("title")) == wt:
            if year is None or sh.get("year") == year or str(sh.get("year")) == str(year):
                return sh
    return None


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        api = _api_base(s)
        if not api:
            return []
        r = s.get(f"{api}/movies/search/", params={"title": title}, timeout=TIMEOUT)
        if not r.ok:
            return []
        movie = _pick_movie(r.json().get("movies"), title, year=year, imdb_id=imdb_id)
        if not movie:
            return []
        urls = []
        for link in movie.get("movie_links") or []:
            u = link.get("url")
            if u:
                q = link.get("quality") or ""
                urls.append(_item(s, u, f"{title} {q}".strip()))
        return urls or []
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    return


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        api = _api_base(s)
        if not api:
            return []
        r = s.get(f"{api}/tvshows/search/", params={"title": title}, timeout=TIMEOUT)
        if not r.ok:
            return []
        show = _pick_show(r.json().get("tv_shows"), title, year=year, imdb_id=imdb_id, tmdb_id=tmdb_id)
        if not show:
            return []
        # search payload already embeds seasons; refresh via id if present
        seasons = show.get("seasons") or []
        if not seasons and show.get("id"):
            r2 = s.get(f"{api}/tvshows/{show['id']}", timeout=TIMEOUT)
            if r2.ok:
                seasons = r2.json().get("seasons") or []
        for sea in seasons:
            if int(sea.get("season_number") or 0) != int(season):
                continue
            for ep in sea.get("episodes") or []:
                if int(ep.get("episode_number") or 0) == int(episode):
                    u = ep.get("video_link")
                    if not u:
                        return []
                    name = f"{title} S{int(season):02d}E{int(episode):02d}"
                    return [_item(s, u, name)]
        return []
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

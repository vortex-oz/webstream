# WARNING: mirrors rotate; some gates CF
import re
from urllib.parse import quote_plus, urljoin

from scrapers import _http as requests
from scrapers._tags import tags_from
from bs4 import BeautifulSoup

BASE = "https://moviesmod.zone"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}
TIMEOUT = 20
MOD_RE = re.compile(
    r"(modrefer\.in|links\.modpro\.blog|posts\.modpro\.blog|episodes\.modpro\.blog)",
    re.I,
)
HOST_RE = re.compile(
    r"(gdrivepro|unblockedgames\.world|hubcloud|hubdrive|gdflix|filepress|"
    r"gofile|pixeldrain|drive\.google|workers\.dev|urlflix)",
    re.I,
)
EP_RANGE = re.compile(r"EP\s*0*(\d+)\s*[-–to]+\s*EP\s*0*(\d+)", re.I)


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _item(url, name=""):
    return {"url": url, "name": name, "tags": tags_from(name, url)}


def _search(s, q):
    items = []
    try:
        r = s.get(f"{BASE}/?s={quote_plus(q)}", timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select(".latestPost a, h2 a, h1 a, .entry-title a"):
            href = a.get("href")
            t = a.get("title") or a.get_text(strip=True)
            if href and t:
                items.append({"title": t, "url": urljoin(BASE, href)})
    except Exception:
        pass
    return items


def _title_ok(t, title, year=None, season=None):
    nt, wt = _norm(t), _norm(title)
    if wt not in nt:
        return False
    if season is None and year and str(year) not in t and str(year) not in nt:
        return False
    if season is None and wt == "avatar" and re.search(r"\b(way|fire|airbender|aang)\b", nt):
        return False
    if season is not None:
        if not (
            re.search(rf"\bs\s*0*{int(season)}\b", t, re.I)
            or re.search(rf"season\s*0*{int(season)}\b", t, re.I)
        ):
            if not re.search(r"season\s*1\s*[-–to]+\s*\d|s01.?s0?\d", t, re.I):
                return False
    return True


def _pick(items, title, year=None, season=None):
    return [it["url"] for it in items if _title_ok(it["title"], title, year=year, season=season)]


def _from_mod(s, url, name=""):
    try:
        r = s.get(url, timeout=TIMEOUT)
        if r.status_code != 200 or "Just a moment" in r.text:
            return [_item(url, name)]
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("http") and HOST_RE.search(href):
                lab = a.get_text(" ", strip=True)
                out.append(_item(href, name or lab))
        return out or [_item(url, name)]
    except Exception:
        return [_item(url, name)]


def _heading_season(blob):
    nums = [int(x) for x in re.findall(r"season\s*0*(\d+)\b", blob or "", re.I)]
    nums += [int(x) for x in re.findall(r"(?:^|[^a-z0-9])s0*(\d+)(?![0-9e])", blob or "", re.I)]
    return nums


def _post_links(s, html, want_batch=None, season=None):
    soup = BeautifulSoup(html, "html.parser")
    cands = []
    want = int(season) if season is not None else None
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("http"):
            continue
        txt = a.get_text(" ", strip=True)
        cls = " ".join(a.get("class") or [])
        prev = a.find_previous(["h3", "h4", "h5"])
        name = (prev.get_text(" ", strip=True) if prev else "") or txt
        if want is not None:
            nums = _heading_season(f"{name} {txt}")
            if nums and want not in nums:
                continue
        is_batch = bool(re.search(r"batch|zip", txt + " " + cls, re.I))
        is_ep = "episode-links" in cls or bool(re.search(r"episode", txt, re.I))
        if want_batch is True and not is_batch:
            continue
        if want_batch is False and is_batch:
            continue
        if MOD_RE.search(href) or HOST_RE.search(href) or is_ep or is_batch:
            cands.append((href, name))
    out, seen, hops = [], set(), 0
    for href, name in cands:
        if MOD_RE.search(href) and hops < 3:
            hops += 1
            items = _from_mod(s, href, name)
        elif HOST_RE.search(href):
            items = [_item(href, name)]
        else:
            items = [_item(href, name)]
        for it in items:
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            out.append(it)
            if len(out) >= 12:
                return out
    return out


def _open(s, title, year=None, season=None):
    q = f"{title} season {int(season)}" if season is not None else (f"{title} {year}" if year else title)
    posts = _pick(_search(s, q), title, year=year, season=season)
    if not posts:
        posts = _pick(_search(s, title), title, year=year, season=season)
    if not posts:
        return None
    r = s.get(posts[0], timeout=TIMEOUT)
    if r.status_code != 200:
        return None
    return r.text


def _ep_archives(html, episode):
    soup = BeautifulSoup(html, "html.parser")
    ep = int(episode)
    lo = hi = None
    cands = []
    seen = set()
    for el in soup.find_all(["h2", "h3", "h4", "h5", "a"]):
        if el.name != "a":
            t = el.get_text(" ", strip=True)
            m = EP_RANGE.search(t)
            if m:
                lo, hi = int(m.group(1)), int(m.group(2))
            continue
        if "episode-links" not in " ".join(el.get("class") or []):
            continue
        href = (el.get("href") or "").strip()
        if not href.startswith("http") or href in seen:
            continue
        if lo is None or not (lo <= ep <= hi):
            continue
        seen.add(href)
        prev = el.find_previous(["h3", "h4", "h5"])
        heading = prev.get_text(" ", strip=True) if prev else ""
        blob = heading.lower()
        score = 0
        if "hindi" in blob:
            score += 4
        if "english" in blob:
            score += 3
        if "japanese" in blob and "english" not in blob and "hindi" not in blob:
            score -= 2
        if "720p" in blob:
            score += 2
        elif "1080p" in blob:
            score += 1
        cands.append((score, href, heading))
    cands.sort(key=lambda x: -x[0])
    return cands


def _ep_from_archive(s, url, episode, heading=""):
    try:
        r = s.get(url, timeout=TIMEOUT)
        if r.status_code != 200 or "Just a moment" in r.text:
            return []
    except Exception:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    want = re.compile(rf"^episode\s*0*{int(episode)}\b", re.I)
    name = f"{heading} Episode {int(episode)}".strip()
    out = []
    for h in soup.find_all(["h2", "h3", "h4"]):
        t = h.get_text(" ", strip=True)
        if not want.search(t):
            continue
        a = h.find_next("a", href=True)
        href = (a.get("href") if a else "") or ""
        if href.startswith("http") and HOST_RE.search(href):
            out.append(_item(href, name or t))
            break
    return out


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        html = _open(s, title, year=year)
        if not html:
            return []
        return _post_links(s, html) or []
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        html = _open(s, title, year=year, season=season)
        if not html:
            return []
        return (
            _post_links(s, html, want_batch=True, season=season)
            or _post_links(s, html, season=season)
            or []
        )
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        html = _open(s, title, year=year, season=season)
        if not html:
            return []
        for _score, url, heading in _ep_archives(html, episode)[:1]:
            hit = _ep_from_archive(s, url, episode, heading)
            if hit:
                return hit
        links = _post_links(s, html, want_batch=False)
        want = re.compile(rf"(?:s0*{int(season)}e0*{int(episode)}\b|episode\s*0*{int(episode)}\b)", re.I)
        hit = [it for it in links if want.search(it.get("name") or "")]
        return hit or []
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

import re
from collections import OrderedDict
from urllib.parse import quote, unquote, urljoin

from bs4 import BeautifulSoup

from scrapers import _http as requests
from scrapers._tags import tags_from

BASE = "https://a.111477.xyz"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
VIDEO_EXT = (".mkv", ".mp4", ".avi", ".m4v", ".ts", ".iso", ".m2ts")
EXTRA_ROOTS = ("/misc/anime/", "/asiandrama/", "/kdrama/")
SKIP_DIR = re.compile(r"^(sample|samples|proof|subs?|subtitles?|screens?|extras?|specials?)$", re.I)
REL_TOK = re.compile(
    r"^(?:(?:19|20)\d{2}|s\d{1,2}|e\d{1,3}|season\d*|\d{3,4}p|1080i|\d{1,4}|"
    r"complete|batch|repack|proper|extended|theatrical|remux|bluray|webrip|webdl|"
    r"hdtv|hybrid|uhd|multi|dual|nf|amzn|dsnp|web|subbed|dubbed|v\d+)$"
)
SERIES_NAME = re.compile(r"\bs\d{1,2}e\d{1,3}\b|\bseason\s*\d|\bs\d{1,2}\b", re.I)
MAX_FOLDERS = 6


_soup_cache = OrderedDict()


def _abs(path):
    return path if str(path).startswith("http") else urljoin(BASE, path)


def _get(path):
    url = _abs(path)
    hit = _soup_cache.get(url)
    if hit is not None:
        _soup_cache.move_to_end(url)
        return hit
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    _soup_cache[url] = soup
    while len(_soup_cache) > 8:
        _soup_cache.popitem(last=False)
    return soup


def _row_size(el):
    tr = el if getattr(el, "name", "") == "tr" else el.find_parent("tr")
    if not tr:
        return ""
    for td in reversed(tr.find_all("td")):
        t = td.get_text(" ", strip=True)
        if re.search(r"[\d.]+\s*(?:Ki?B|Mi?B|Gi?B|Ti?B)", t, re.I):
            return t
    return ""


def _entries(soup):
    rows = soup.select("tr[data-name][data-url]")
    if rows:
        out = []
        for tr in rows:
            name = (tr.get("data-name") or "").strip()
            href = tr.get("data-url") or ""
            if not name or name in ("..", "Parent Directory") or name.startswith("."):
                continue
            out.append((name, urljoin(BASE, href), _row_size(tr)))
        return out
    out = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True).rstrip("/")
        href = a["href"]
        if not text or text in ("..", "Parent Directory") or "discord" in href.lower():
            continue
        out.append((text, urljoin(BASE, href), _row_size(a)))
    return out


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _title_hit(name, title):
    s = (name or "").lstrip()
    if s.startswith("["):
        inner = re.sub(r"^\[[^\]]+\]\s*", "", s, count=1)
        if inner != s and _title_core(inner, title):
            return True
    return _title_core(name, title)


def _anime_hit(name, title):
    n = _norm(name)
    short = _norm(re.split(r"\s+-", (title or "").strip(), 1)[0])
    words = [w for w in short.split() if len(w) >= 2]
    if words and all(re.search(rf"\b{re.escape(w)}\b", n) for w in words):
        return True
    compact = re.sub(r"[^a-z0-9]+", "", short)
    if len(compact) >= 4 and compact in re.sub(r"[^a-z0-9]+", "", n):
        return True
    return _title_hit(name, title)


def _title_core(name, title):
    t, n = _norm(title), _norm(name)
    if not t or not n:
        return False
    if n == t:
        return True
    if not n.startswith(t + " "):
        return False
    rest = n[len(t) + 1 :].split()[:1]
    if not rest or REL_TOK.match(rest[0]):
        return True
    return bool(re.search(rf"{re.escape(title)}\s*[!?:(\[]", name, re.I))


def _item(url, name, size=None):
    return {"url": url, "name": name, "tags": tags_from(name, size or "")}


def _file_urls(folder_url, season=None, depth=0):
    try:
        soup = _get(folder_url)
    except Exception:
        return []
    files, dirs = [], []
    for name, url, size in _entries(soup):
        fname = unquote(url.split("?")[0].rstrip("/").split("/")[-1].replace("+", " "))
        low = (fname or name).lower()
        if any(low.endswith(ext) for ext in VIDEO_EXT):
            files.append(_item(url, fname or name, size))
        elif url.endswith("/") and not SKIP_DIR.match(name):
            dirs.append((name, url))
    if files or depth >= 1:
        return files
    if season is not None:
        seasonal = [(n, u) for n, u in dirs if _season_ok(n, season)]
        if seasonal:
            dirs = seasonal
    out = []
    for _, u in dirs[:8]:
        out.extend(_file_urls(u, season=season, depth=1))
    return out


def _try_folder(path):
    try:
        soup = _get(path)
        if "Index of" in (soup.title.get_text() if soup.title else "") or soup.find("a", href=True):
            url = _abs(path)
            return url if url.endswith("/") else url + "/"
    except Exception:
        return None
    return None


def _name_vars(title):
    out = []
    for t in (title or "", (title or "").replace(":", "").replace("  ", " ").strip()):
        t = t.strip()
        if t and t not in out:
            out.append(t)
    return out


def _season_nums(name):
    found = [int(x) for x in re.findall(r"season\s*0*(\d{1,2})", name, re.I)]
    found += [int(x) for x in re.findall(r"(?:^|[^a-z0-9])s0*(\d{1,2})(?:e\d|[^a-z0-9]|$)", name, re.I)]
    return found


def _season_ok(name, season):
    n = int(season)
    found = _season_nums(name)
    if not found:
        return n == 1
    if n in found:
        return True
    if min(found) <= n <= max(found) and re.search(r"s\d+\s*[-~to]+\s*s?\d+|season\s*\d+\s*[-~to]", name, re.I):
        return True
    return False


def _ep_match(name, season, episode):
    s, e = int(season), int(episode)
    if re.search(rf"[sS]0*{s}\s*[eE]0*{e}\b|0*{s}x0*{e}\b", name):
        return True
    if re.search(r"S\d{1,2}E\d{1,3}", name, re.I):
        return False
    if re.search(rf"(?:^|[\s._-])E0*{e}(?:[\s._-]|$)", name, re.I):
        return True
    if re.search(rf"\s-\s0*{e}(?:\s|$|\.|\[)", name):
        return True
    return bool(re.search(rf"(?:^|[\s._\[-])0*{e}(?:[\s._\].]|$)", name))


def _dedupe(items):
    seen, out = set(), []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        out.append(it)
    return out


def _extra(title, year=None, season=None, movie=False):
    files = []
    for root in EXTRA_ROOTS:
        try:
            entries = _entries(_get(root))
        except Exception:
            continue
        anime = "anime" in root
        hit = _anime_hit if anime else _title_hit
        hits, loose = [], []
        for name, url, size in entries:
            if not hit(name, title):
                continue
            if movie:
                if year is not None and str(year) not in _norm(name).split():
                    continue
                if SERIES_NAME.search(name):
                    continue
            elif not anime and not _season_ok(name, season):
                continue
            if any(name.lower().endswith(ext) for ext in VIDEO_EXT):
                loose.append(_item(url, name, size))
                continue
            score = 0
            if year is not None and str(year) in _norm(name).split():
                score += 2
            if season is not None and int(season) in _season_nums(name):
                score += 2
            if re.search(r"2160p|\buhd\b|\b4k\b", name, re.I):
                score += 3
            elif re.search(r"1080p", name, re.I):
                score += 2
            elif re.search(r"720p", name, re.I):
                score += 1
            if _norm(name) == _norm(f"{title} ({year})" if year is not None else title):
                score += 5
            hits.append((-score, len(name), url, name))
        files.extend(loose)
        hits.sort()
        attempts = 0
        for _, _, url, _name in hits:
            if attempts >= MAX_FOLDERS:
                break
            got = _file_urls(url, season=None if anime else season)
            attempts += 1
            if not got:
                continue
            files.extend(got)
            break
        if files:
            return _dedupe(files)
    return _dedupe(files)


def _season_from_show(show, title, season):
    seasons = _entries(_get(show))
    for name, url, size in seasons:
        if re.search(rf"\bseason\s*0*{int(season)}\b", name, re.I) or _norm(name) == f"season {int(season)}":
            return url
    return _try_folder(f"/tvs/{quote(title)}/Season%20{int(season)}/")


def _season_folder(title, season, year=None):
    for t in _name_vars(title):
        show = _try_folder(f"/tvs/{quote(t)}/")
        if not show and year is not None:
            show = _try_folder(f"/tvs/{quote(f'{t} ({year})')}/")
        if show:
            return _season_from_show(show, t, season)
    return None


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        candidates = []
        for t in _name_vars(title):
            if year is not None:
                candidates.append(f"/movies/{quote(f'{t} ({year})')}/")
            candidates.append(f"/movies/{quote(t)}/")
        for path in candidates:
            folder = _try_folder(path)
            if folder:
                files = _file_urls(folder)
                if files:
                    return files
        return _extra(title, year=year, movie=True)
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    return


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        season_url = _season_folder(title, season, year=year)
        if not season_url:
            return []
        return [
            u
            for u in _file_urls(season_url, season=season)
            if _ep_match(u["name"], season, episode) or _ep_match(u["url"], season, episode)
        ]
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

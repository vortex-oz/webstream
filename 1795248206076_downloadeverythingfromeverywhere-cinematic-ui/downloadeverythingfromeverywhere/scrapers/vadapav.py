import re
from urllib.parse import quote

from scrapers import _http as requests
from scrapers._tags import format_size

BASE = "https://vadapav.mov"
VIDEO_EXT = (".mkv", ".mp4", ".avi", ".m4v", ".ts", ".iso", ".m2ts")
SKIP_DIR = re.compile(r"^(sample|samples|proof|subs?|subtitles?|screens?|extras?)$", re.I)
SKIP_FILE = re.compile(r"(^|[._-])sample([._-]|$)", re.I)


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _size_tag(n):
    if n is None or n == "":
        return None
    if isinstance(n, str):
        m = re.search(r"([\d.,]+)\s*(TiB|GiB|MiB|KiB|TB|GB|MB|KB)", n, re.I)
        if m:
            num = m.group(1).replace(",", "")
            if "." in num:
                num = num.rstrip("0").rstrip(".")
            if not num:
                return None
            return f"{num}{m.group(2).upper().replace('IB', 'B')}"
        try:
            n = float(n.replace(",", "").strip())
        except Exception:
            return None
    try:
        n = float(n)
    except Exception:
        return None
    return format_size(n)


def _head_size(url):
    try:
        r = requests.head(url, timeout=15, allow_redirects=True)
        n = r.headers.get("Content-Length")
        if n and str(n).isdigit() and int(n) > 0:
            return _size_tag(int(n))
    except Exception:
        pass
    return None


def _items(path):
    r = requests.get(BASE + path, timeout=25, headers={"Accept": "application/json"})
    if r.status_code != 200:
        return []
    try:
        j = r.json()
    except Exception:
        return []
    return [x for x in (j.get("items") or []) if isinstance(x, dict)]


def _search(q):
    q = (q or "").strip()
    if len(q) < 4:
        return []
    return _items(f"/api/s/{quote(q, safe='()')}")


def _is_folder(it):
    return it.get("type") == "folder" or "folder" in str(it.get("mimeType") or "")


def _is_video(it):
    if _is_folder(it):
        return False
    name = (it.get("name") or "").lower()
    return name.endswith(VIDEO_EXT) and not SKIP_FILE.search(name)


def _pick_folder(title, year=None):
    queries = []
    if year is not None:
        queries.append(f'"{title} ({year})"')
    if len(title.strip()) >= 4:
        queries.append(title)
    elif year is not None:
        queries.append(f"{title} {year}")
    want = _norm(f"{title} ({year})" if year is not None else title)
    title_n = _norm(title)
    exact, partial = [], []
    seen = set()
    for q in queries:
        for it in _search(q):
            iid = it.get("id")
            if not iid or iid in seen or not _is_folder(it):
                continue
            seen.add(iid)
            name = it.get("name") or ""
            n = _norm(name)
            size = it.get("size") or 0
            row = (-size, it)
            if n == want or (year is None and n == title_n):
                exact.append(row)
            elif title_n and title_n in n and (year is None or str(year) in name):
                partial.append(row)
        if exact:
            break
    pool = exact or partial
    pool.sort()
    return pool[0][1] if pool else None


def _file_item(it):
    url = f"{BASE}/f/{it['id']}"
    name = it.get("name") or it["id"]
    st = _size_tag(it.get("size")) or _head_size(url)
    tags = [st] if st else []
    return {"url": url, "name": name, "tags": tags}


def _videos(dir_id, depth=0):
    out = []
    for it in _items(f"/api/d/{dir_id}"):
        if _is_video(it):
            out.append(_file_item(it))
        elif _is_folder(it) and depth < 2 and not SKIP_DIR.match(it.get("name") or ""):
            out.extend(_videos(it["id"], depth + 1))
    return out


def _season_dir(show_id, season):
    n = int(season)
    for it in _items(f"/api/d/{show_id}"):
        if not _is_folder(it):
            continue
        name = it.get("name") or ""
        if re.search(rf"\bseason\s*0*{n}\b", name, re.I) or re.fullmatch(rf"s0*{n}", name, re.I):
            return it["id"]
    return None


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        folder = _pick_folder(title, year)
        return _videos(folder["id"]) if folder else []
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    return


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        folder = _pick_folder(title, year)
        if not folder:
            return []
        sid = _season_dir(folder["id"], season)
        if not sid:
            return []
        pat = re.compile(rf"[sS]0*{int(season)}\s*[eE]0*{int(episode)}\b|0*{int(season)}x0*{int(episode)}\b")
        return [u for u in _videos(sid) if pat.search(u["name"]) or pat.search(u["url"])]
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

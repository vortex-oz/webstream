import re
from urllib.parse import quote

from bs4 import BeautifulSoup
from scrapers import _http as requests
from scrapers._tags import tags_from, format_size

BASE = "https://phonofilm.net"
API = BASE + "/svc/api"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": BASE + "/",
}
TIMEOUT = 20
TG = re.compile(r"(?:t\.me|telegram\.me|telegram\.dog)/", re.I)
EP = re.compile(r"(?:^|[^a-z0-9])s0*(\d{1,2})e0*(\d{1,3})(?:[^a-z0-9]|$)", re.I)
SEASON = re.compile(r"(?:season|s)\s*0*(\d{1,2})\b", re.I)


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


def _item(url, name, size=None, *extra):
    tags = []
    if TG.search(url or ""):
        tags.append("Telegram")
    st = _size_tag(size)
    if st:
        tags.append(st)
    more = tags_from(name, *extra, url)
    if st:
        more = [t for t in more if not re.fullmatch(r"\d+(?:\.\d+)?(?:KB|MB|GB|TB)", t, re.I)]
    tags.extend(more)
    seen, out = set(), []
    for t in tags:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return {"url": url, "name": name, "tags": out}


def _get(url, params=None):
    r = requests.get(url, headers=UA, timeout=TIMEOUT, params=params)
    if int(getattr(r, "status_code", 0) or 0) != 200:
        return None
    t = r.text or ""
    if "Just a moment" in t[:2000]:
        return None
    return r


def _json(path, params=None):
    r = _get(API + path, params=params)
    if not r:
        return None
    try:
        return r.json()
    except Exception:
        return None


def _search_html(q):
    r = _get(f"{BASE}/result/{quote(q)}")
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    out, seen = [], set()
    for a in soup.select('a[href*="/content/"]'):
        href = a.get("href") or ""
        m = re.search(r"/content/[^/?#]*-(\d+)(?:/|$|\?)", href)
        if not m:
            continue
        cid = int(m.group(1))
        if cid in seen:
            continue
        seen.add(cid)
        out.append(
            {
                "content_id": cid,
                "content_type": "",
                "title": a.get_text(" ", strip=True),
                "release_date": "",
            }
        )
    return out


def _search(q, kind=None):
    params = {"q": q, "limit": 20}
    if kind:
        params["content_type"] = kind
    data = _json("/search", params=params)
    rows = data.get("results") if isinstance(data, dict) else None
    if isinstance(rows, list) and rows:
        return rows
    return _search_html(q)


def _pick(title, year=None, tv=False, tmdb_id=None, imdb_id=None):
    wt = _norm(title)
    kind = "SERIES" if tv else "MOVIE"
    rows = _search(title, kind) or _search(title)
    cands = []
    for it in rows or []:
        cid = it.get("content_id")
        if not str(cid).isdigit():
            continue
        typ = (it.get("content_type") or "").upper()
        if tv and typ == "MOVIE":
            continue
        if not tv and typ and typ != "MOVIE":
            continue
        if _norm(it.get("title")) != wt:
            continue
        rd = str(it.get("release_date") or "")[:4]
        if year and rd and rd != str(year):
            continue
        cands.append(it)
    if year:
        yhit = [it for it in cands if str(it.get("release_date") or "")[:4] == str(year)]
        if yhit:
            cands = yhit
    if not cands:
        return None
    if tmdb_id or imdb_id:
        for it in cands:
            d = _json(f"/content/{it['content_id']}")
            if not isinstance(d, dict):
                continue
            if tmdb_id and str(d.get("tmdb_id") or "") == str(tmdb_id):
                return int(it["content_id"])
            if imdb_id and str(d.get("imdb_id") or "") == str(imdb_id):
                return int(it["content_id"])
    return int(cands[0]["content_id"])


def _walk_files(data):
    out = []
    if not isinstance(data, dict):
        return out
    for resmap in data.values():
        if not isinstance(resmap, dict):
            continue
        for arr in resmap.values():
            if not isinstance(arr, list):
                continue
            for f in arr:
                if isinstance(f, dict) and f.get("download_url"):
                    out.append(f)
    return out


def _flat_buttons(buttons):
    out, stack = [], list(buttons or [])
    while stack:
        x = stack.pop(0)
        if isinstance(x, list):
            stack = list(x) + stack
        elif isinstance(x, dict) and x.get("url"):
            out.append(x)
    return out


def _loads(cid, tv=False):
    if tv:
        b = _json(f"/content/{cid}/buttons")
        buttons = _flat_buttons(b.get("buttons") if isinstance(b, dict) else None)
        if buttons:
            return [], buttons
        return _walk_files(_json(f"/content/{cid}/files")), []
    files = _walk_files(_json(f"/content/{cid}/files"))
    if files:
        return files, []
    b = _json(f"/content/{cid}/buttons")
    return [], _flat_buttons(b.get("buttons") if isinstance(b, dict) else None)


def _btn_season(text, season):
    nums = [int(x) for x in SEASON.findall(text or "")]
    return int(season) in nums


def _ep_hit(name, season, episode):
    m = EP.search(name or "")
    return bool(m and int(m.group(1)) == int(season) and int(m.group(2)) == int(episode))


def _is_single_ep(name):
    if re.search(r"s\d{1,2}[\s._-]*e\d{1,3}[\s._-]*(?:-|–|to)[\s._-]*e?\d", name or "", re.I):
        return False
    return bool(EP.search(name or ""))


def _dedupe(items):
    seen, out = set(), []
    for it in items:
        k = (it["url"], it["name"])
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        cid = _pick(title, year=year, tv=False, tmdb_id=tmdb_id, imdb_id=imdb_id)
        if not cid:
            return []
        files, buttons = _loads(cid, tv=False)
        out = []
        for f in files:
            out.append(_item(f["download_url"], f.get("file_name") or title, f.get("file_size_bytes")))
        for b in buttons:
            out.append(_item(b["url"], b.get("text") or title))
        return _dedupe(out)
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        cid = _pick(title, year=year, tv=True, tmdb_id=tmdb_id, imdb_id=imdb_id)
        if not cid:
            return []
        files, buttons = _loads(cid, tv=True)
        sn = int(season)
        out = []
        for b in buttons:
            text = b.get("text") or ""
            if _btn_season(text, sn):
                out.append(_item(b["url"], f"{title} {text}".strip()))
        for f in files:
            name = f.get("file_name") or ""
            if _is_single_ep(name):
                continue
            nums = [int(x) for x in SEASON.findall(name)]
            if nums and sn not in nums:
                continue
            out.append(_item(f["download_url"], name, f.get("file_size_bytes")))
        return _dedupe(out)
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        cid = _pick(title, year=year, tv=True, tmdb_id=tmdb_id, imdb_id=imdb_id)
        if not cid:
            return []
        files = _walk_files(_json(f"/content/{cid}/files"))
        out = []
        for f in files:
            name = f.get("file_name") or ""
            if _ep_hit(name, season, episode):
                out.append(_item(f["download_url"], name, f.get("file_size_bytes")))
        return _dedupe(out)
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

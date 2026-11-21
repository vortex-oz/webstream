# WARNING: Upstream may return 403 for HTML and wp-json
import re
from urllib.parse import quote_plus, unquote, urljoin

from scrapers import _http as requests
from scrapers._tags import tags_from
from bs4 import BeautifulSoup

SITES = ("https://lightdownload.xyz", "https://lightdl.xyz")
CDN = "https://dl11.sermoviedown.pw"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 20
VIDEO_EXT = (".mkv", ".mp4", ".avi", ".m4v", ".ts")
SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".srt", ".nfo", ".txt", ".idx", ".sub")
SKIP_DIR = re.compile(r"^(subs?|subtitles?|samples?|screenshots?|extras?)$", re.I)
IMPS = ("chrome131", "safari18_0", "firefox")
_dead = set()


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _cf(r):
    try:
        if int(getattr(r, "status_code", 0) or 0) not in (403, 503):
            return False
        t = (r.text or "")[:2000]
        return "Just a moment" in t or "cf-browser-verification" in t
    except Exception:
        return False


def _ok(r):
    if r is None or int(getattr(r, "status_code", 0) or 0) != 200:
        return False
    t = r.text or ""
    return "Just a moment" not in t[:2000] and "cf-browser-verification" not in t[:2000]


def _get(url, params=None):
    host = url.split("/")[2] if "://" in url else ""
    if host in _dead:
        return None
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT, params=params)
    except Exception:
        r = None
    if _ok(r):
        return r
    if r is None or not _cf(r):
        return None
    try:
        from curl_cffi import requests as cr
    except Exception:
        _dead.add(host)
        return None
    for imp in IMPS:
        try:
            s = cr.Session(impersonate=imp)
            s.headers.update(UA)
            r2 = s.get(url, timeout=TIMEOUT, params=params)
            if _ok(r2):
                return r2
        except Exception:
            continue
    _dead.add(host)
    return None


def _title_ok(name, title, year=None):
    n, t = _norm(name), _norm(title)
    if not t or not (n == t or n.startswith(t + " ")):
        return False
    if t == "avatar" and re.search(r"airbender|way of water|fire and ash|\baang\b", n):
        return False
    if year and str(year) not in (name or "") and str(year) not in n and n != t:
        return False
    return True


def _fname(href, text=""):
    t = (text or "").strip()
    if t.lower().endswith(VIDEO_EXT) or (len(t) > 12 and "." in t and " " not in t[:3]):
        return t
    return unquote((href or "").split("?")[0].rstrip("/").split("/")[-1])


def _item(url, name, size=None):
    return {"url": url, "name": name, "tags": tags_from(name, size or "")}


def _near_size(a):
    chunks = [a.get_text(" ", strip=True)]
    for sib in (a.next_sibling, a.previous_sibling):
        if isinstance(sib, str):
            chunks.append(sib)
        elif getattr(sib, "get_text", None):
            chunks.append(sib.get_text(" ", strip=True))
    blob = " ".join(chunks)
    m = re.search(r"[\d.]+\s*(?:Ki?B|Mi?B|Gi?B|Ti?B)", blob, re.I)
    if m:
        return m.group(0)
    parent = a.find_parent(["p", "li", "td", "div"])
    if parent:
        ms = re.findall(r"[\d.]+\s*(?:Ki?B|Mi?B|Gi?B|Ti?B)", parent.get_text(" ", strip=True), re.I)
        if len(ms) == 1:
            return ms[0]
    return ""


def _row_size(a):
    tr = a.find_parent("tr")
    if not tr:
        return ""
    for td in tr.find_all("td"):
        t = td.get_text(strip=True)
        if re.search(r"[\d.]+\s*(?:Ki?B|Mi?B|Gi?B|Ti?B)", t, re.I):
            return t
    return ""


def _is_dl(href):
    h = (href or "").lower()
    return "sermoviedown" in h or "gofile.io" in h or h.split("?")[0].endswith(VIDEO_EXT)


def _links(html):
    soup = BeautifulSoup(html or "", "html.parser")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not _is_dl(href) or href in seen:
            continue
        seen.add(href)
        out.append(_item(href, _fname(href, a.get_text(" ", strip=True)), _near_size(a)))
    for m in re.finditer(r"https?://[^\s\"'<>]+", html or ""):
        href = m.group(0).rstrip(").,]")
        if href in seen or not _is_dl(href):
            continue
        seen.add(href)
        out.append(_item(href, _fname(href)))
    return out


def _wp(q):
    items = []
    for base in SITES:
        for kind in ("posts", "pages"):
            r = _get(f"{base}/wp-json/wp/v2/{kind}", params={"search": q, "per_page": 20})
            if not r:
                continue
            try:
                rows = r.json()
            except Exception:
                rows = []
            for p in rows if isinstance(rows, list) else []:
                title = re.sub(r"<[^>]+>", "", (p.get("title") or {}).get("rendered") or "")
                items.append(
                    {
                        "title": title,
                        "url": p.get("link"),
                        "html": (p.get("content") or {}).get("rendered") or "",
                    }
                )
            if items:
                return items
        r = _get(f"{base}/?s={quote_plus(q)}")
        if r:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("h1 a, h2 a, h3 a, .entry-title a"):
                href, t = a.get("href"), a.get_text(strip=True)
                if href and t:
                    items.append({"title": t, "url": href, "html": ""})
            if items:
                return items
        r = _get(f"{base}/feed/", params={"s": q})
        if r:
            soup = BeautifulSoup(r.text, "html.parser")
            for it in soup.find_all("item"):
                t = it.find("title")
                link = it.find("link")
                body = it.find("encoded") or it.find("description")
                items.append(
                    {
                        "title": t.get_text(strip=True) if t else "",
                        "url": link.get_text(strip=True) if link else "",
                        "html": body.get_text() if body else "",
                    }
                )
            if items:
                return items
    return items


def _wp_links(title, year=None):
    q = f"{title} {year}" if year else title
    posts = [p for p in _wp(q) if _title_ok(p.get("title") or "", title, year=year)]
    if not posts:
        posts = [p for p in _wp(title) if _title_ok(p.get("title") or p.get("url") or "", title, year=year)]
    out = []
    for p in posts[:3]:
        html = p.get("html") or ""
        if not html and p.get("url"):
            r = _get(p["url"])
            html = r.text if r else ""
        out.extend(_links(html))
    seen, dedup = set(), []
    for it in out:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        dedup.append(it)
    return dedup


def _list(url):
    r = _get(url if url.endswith("/") else url + "/")
    if not r:
        return [], []
    soup = BeautifulSoup(r.text, "html.parser")
    dirs, files = [], []
    base = url if url.endswith("/") else url + "/"
    for a in soup.find_all("a", href=True):
        href = a["href"].split("?")[0]
        if not href or href.startswith("?") or href in ("../", "./", "/"):
            continue
        name = unquote(href.rstrip("/").split("/")[-1])
        if not name or name.lower() in ("parent directory", ".."):
            continue
        full = urljoin(base, href)
        low = name.lower()
        if low.endswith(VIDEO_EXT):
            files.append(_item(full, name, _row_size(a)))
        elif not low.endswith(SKIP_EXT):
            dirs.append((name, full if full.endswith("/") else full + "/"))
    return dirs, files


def _qual(name):
    return bool(re.match(r"^(soft|hard|\d{3,4}p?|4k|uhd|hd|sd)(\b|[._x-])", name or "", re.I))


def _videos(url, depth=0, title=None, year=None):
    dirs, files = _list(url)
    out = list(files)
    if depth >= 3:
        return out
    for name, u in dirs:
        if SKIP_DIR.match(name):
            continue
        if not _qual(name) and title and not _title_ok(name, title, year=year):
            continue
        out.extend(_videos(u, depth + 1, title=title, year=year))
    return out


def _year_only(items, year):
    if not year:
        return items
    y = str(year)
    hit = [x for x in items if y in x["name"]]
    return hit or items


def _pick(dirs, title, year=None, need_year=False):
    t = _norm(title)
    best, score = None, 0
    for name, u in dirs:
        if not _title_ok(name, title, year=year if need_year else None):
            continue
        n = _norm(name)
        s = 10 if n == t else 5
        if year and str(year) in name:
            s += 3
        if s > score:
            best, score = u, s
    return best


def _roots(kind):
    dirs, _ = _list(f"{CDN}/{kind}/")
    years = [(n, u) for n, u in dirs if n.isdigit()]
    named = [(n, u) for n, u in dirs if not n.isdigit()]
    return years, named


def _cdn_movie(title, year=None):
    years, named = _roots("Movies")
    hit = None
    if year:
        for n, u in years:
            if n == str(year):
                hit = _pick(_list(u)[0], title)
                break
    if not hit:
        hit = _pick(named, title, year=year)
    if not hit:
        return []
    dirs, _ = _list(hit)
    child = _pick(dirs, title, year=year, need_year=bool(year))
    return _year_only(_videos(child or hit, title=title, year=year), year)


def _cdn_show(title, year=None):
    years, named = _roots("Series")
    if year:
        for n, u in years:
            if n == str(year):
                hit = _pick(_list(u)[0], title)
                if hit:
                    return hit
    for _n, u in years:
        hit = _pick(_list(u)[0], title)
        if hit:
            return hit
    return _pick(named, title)


def _season_dir(show, season):
    n = int(season)
    for name, u in _list(show)[0]:
        if re.fullmatch(rf"s0*{n}", name, re.I) or re.search(rf"season\s*0*{n}\b", name, re.I):
            return u
    return None


def _ep_re(season, episode):
    return re.compile(rf"[sS]0*{int(season)}\s*[eE]0*{int(episode)}\b|0*{int(season)}x0*{int(episode)}\b")


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        links = _wp_links(title, year=year)
        if links:
            return links
        return _cdn_movie(title, year=year)
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        links = _wp_links(title, year=year)
        if not links:
            return []
        seas = re.compile(rf"\bseason\s*0*{int(season)}\b|\bS0*{int(season)}\b")
        ep = re.compile(rf"[sS]0*{int(season)}\s*[eE]\d+")
        return [
            x
            for x in links
            if (seas.search(x["name"]) or seas.search(x["url"]))
            and not ep.search(x["name"])
            and not ep.search(x["url"])
        ]
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        pat = _ep_re(season, episode)
        links = [x for x in _wp_links(title, year=year) if pat.search(x["name"]) or pat.search(x["url"])]
        if links:
            return links
        show = _cdn_show(title, year=year)
        if not show:
            return []
        seas = _season_dir(show, season)
        if not seas:
            return []
        return [x for x in _videos(seas) if pat.search(x["name"]) or pat.search(x["url"])]
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

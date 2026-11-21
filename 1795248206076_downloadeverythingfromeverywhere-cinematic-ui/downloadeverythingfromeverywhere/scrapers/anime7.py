import re
from urllib.parse import quote_plus

from scrapers import _http as requests
from bs4 import BeautifulSoup

BASE = "https://anime7.download"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}
TIMEOUT = 20
HOST_RE = re.compile(
    r"(vikingfile\.com|mega\.nz|gofile\.io|pixeldrain\.|krakenfiles\.|"
    r"buzzheavier|mediafire\.com|drive\.google\.com|mir\.cr)",
    re.I,
)
SKIP = re.compile(
    r"memory snow|hyouketsu|shin henshuu|repetit|re petit", re.I
)
DL = re.compile(r"https?://dl\.anime7\.download/[A-Za-z0-9]+", re.I)
SIZE_RE = re.compile(r"Size\s*:\s*([\d.]+)\s*(TB|GB|MB|KB)\b", re.I)


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _compact(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _alts(title):
    t = (title or "").strip()
    qs = [t]
    n, c = _norm(t), _compact(t)
    if "rezero" in c or "re zero" in n:
        qs += ["Re:Zero", "ReZero", "Re:Zero kara Hajimeru Isekai Seikatsu"]
    if "your name" in n or "kimi no na" in n:
        qs += ["Kimi no Na wa", "kimi-no-na-wa", "Your Name"]
    out, seen = [], set()
    for q in qs:
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out


def _hit(post, title):
    nt, wt = _norm(post), _norm(title)
    pc, tc = _compact(post), _compact(title)
    if "rezero" in tc or "re zero" in wt:
        return "rezero" in pc
    if "your name" in wt or "kimi no na wa" in wt:
        return "kimi no na wa" in nt or "your name" in nt
    return bool(wt) and wt in nt


def _season_hit(t, season):
    s = int(season)
    if re.search(rf"{s}(?:st|nd|rd|th)\s*season", t, re.I) or re.search(
        rf"\bseason\s*0*{s}\b", t, re.I
    ):
        return True
    if s == 1 and not re.search(r"(?:2nd|3rd|4th|5th|\bseason\s*[2-9])", t, re.I):
        return True
    return False


def _search(s, q):
    items = []
    try:
        r = s.get(
            f"{BASE}/wp-json/wp/v2/posts",
            params={"search": q, "per_page": 20},
            timeout=TIMEOUT,
        )
        if r.ok:
            for p in r.json():
                t = re.sub(r"<[^>]+>", "", (p.get("title") or {}).get("rendered") or "")
                items.append(
                    {
                        "title": t,
                        "url": p.get("link"),
                        "html": (p.get("content") or {}).get("rendered") or "",
                    }
                )
            if items:
                return items
    except Exception:
        pass
    try:
        r = s.get(f"{BASE}/?s={quote_plus(q)}", timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("h1 a, h2 a, h3 a, .entry-title a"):
            href, t = a.get("href"), a.get_text(strip=True)
            if href and t and BASE in href:
                items.append({"title": t, "url": href, "html": ""})
    except Exception:
        pass
    return items


def _posts(s, title):
    seen, out = set(), []
    for q in _alts(title):
        for it in _search(s, q):
            u = it.get("url")
            if not u or u in seen or not _hit(it.get("title") or "", title):
                continue
            if SKIP.search(it.get("title") or ""):
                continue
            seen.add(u)
            out.append(it)
        if out:
            break
    return out


def _hosts(html):
    soup = BeautifulSoup(html or "", "html.parser")
    prefer, rest = [], []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href in seen or not HOST_RE.search(href):
            continue
        seen.add(href)
        lab = a.get_text(" ", strip=True)
        row = (href, lab)
        if re.search(r"vikingfile|mega\.nz|gofile|pixeldrain|mediafire|krakenfiles|buzzheavier|drive\.google", href, re.I):
            prefer.append(row)
        else:
            rest.append(row)
    return prefer + rest


def _follow(s, url):
    try:
        r = s.get(url, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return []
        return _hosts(r.text)
    except Exception:
        return []


def _viking(s, url):
    try:
        r = s.get(url, timeout=TIMEOUT, allow_redirects=True, headers={"Range": "bytes=0-0"})
        final = r.url or url
        return [final] if "/download/" in final else [url]
    except Exception:
        return [url]


def _mir(s, url):
    try:
        r = s.get(url, timeout=TIMEOUT, allow_redirects=True)
        final = r.url or url
        if re.search(r"ouo\.|cuty\.|gplinks", final, re.I):
            return []
        if HOST_RE.search(final) and "mir.cr" not in final:
            return [final]
        out = []
        soup = BeautifulSoup(r.text or "", "html.parser")
        for a in soup.find_all("a", href=True):
            h = a["href"].strip()
            if not HOST_RE.search(h) or re.search(
                r"ouo\.|cuty\.|gplinks|mir\.cr|dl\.anime7", h, re.I
            ):
                continue
            out.append(h)
        return out
    except Exception:
        return []


def _ep_links(html):
    """(kind, num, url) kind is 'ep' or 'pack'."""
    rows = []
    for m in re.finditer(
        r"Episode\s*0*(\d+)\s*(?:&#8211;|–|&ndash;|-|to)\s*0*(\d+)[^<]{0,160}<a href=\"(https?://[^\"]+)\"",
        html or "",
        re.I,
    ):
        rows.append(("pack", int(m.group(1)), m.group(3)))
    pack_urls = {u for _, _, u in rows}
    for m in re.finditer(
        r"Episode\s*0*(\d+)\s*:\s*<a href=\"(https?://[^\"]+)\"",
        html or "",
        re.I,
    ):
        url = m.group(2)
        if url in pack_urls:
            continue
        rows.append(("ep", int(m.group(1)), url))
    return rows


def _html(s, post):
    html = post.get("html") or ""
    if DL.search(html):
        return html
    try:
        r = s.get(post["url"], timeout=TIMEOUT)
        return r.text if r.status_code == 200 else html
    except Exception:
        return html


def _size_tag(html):
    m = SIZE_RE.search(html or "")
    if not m:
        return None
    num = m.group(1)
    if "." in num:
        num = num.rstrip("0").rstrip(".")
    return f"{num}{m.group(2).upper()}" if num else None


def _resolve(s, urls, prefix, size=None):
    seen, out = set(), []
    for u in urls:
        if "dl.anime7.download" in u:
            hosts = _follow(s, u)
        elif HOST_RE.search(u):
            hosts = [(u, "")]
        else:
            continue
        for href, lab in hosts:
            if "vikingfile.com" in href and "/f/" in href:
                hops = _viking(s, href)
            elif "mir.cr" in href:
                hops = _mir(s, href)
            else:
                hops = [href]
            for h in hops:
                if h in seen or "dl.anime7.download" in h:
                    continue
                seen.add(h)
                name = " ".join(x for x in (prefix, lab) if x).strip() or prefix
                row = {"url": h, "name": name}
                if size:
                    row["tags"] = [size]
                out.append(row)
    return out


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        posts = _posts(s, title)
        if not posts:
            return []
        html = _html(s, posts[0])
        urls = [u for _, _, u in _ep_links(html)] or DL.findall(html)
        return _resolve(s, urls[:4], title, size=_size_tag(html)) or []
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        posts = [p for p in _posts(s, title) if _season_hit(p["title"], season)]
        if not posts:
            return []
        html = _html(s, posts[0])
        rows = _ep_links(html)
        packs = [u for k, _, u in rows if k == "pack"]
        urls = packs or [u for k, _, u in rows if k == "ep"][:12]
        if not urls:
            urls = DL.findall(html)[:4]
        # listed Size is per-episode, not the batch pack
        sz = None if packs and urls == packs else _size_tag(html)
        return _resolve(s, urls, f"{title} S{int(season):02d}", size=sz) or []
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        en = int(episode)
        posts = _posts(s, title)
        prefer = [p for p in posts if str(en) in (p.get("title") or "") or _season_hit(p["title"], season)]
        ordered = prefer + [p for p in posts if p not in prefer]
        for p in ordered[:6]:
            html = _html(s, p)
            urls = [u for k, n, u in _ep_links(html) if k == "ep" and n == en]
            if urls:
                return _resolve(s, urls, f"{title} E{en:02d}", size=_size_tag(html)) or []
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
    rz = "Re:ZERO -Starting Life in Another World-"
    print("rezero_e1", dlseriesepisode(rz, 1, 1, year=2016, tmdb_id=65942, imdb_id="tt5607616"))
    print("rezero_e78", dlseriesepisode(rz, 1, 78, year=2016, tmdb_id=65942, imdb_id="tt5607616"))

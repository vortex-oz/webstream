import re
from urllib.parse import quote_plus, urljoin

from scrapers import _http as requests
from bs4 import BeautifulSoup

BASE = "https://new.katmoviehd.top"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}
TIMEOUT = 20
HOST_RE = re.compile(
    r"(kmhd\.eu|gd\.kmhd\.eu|links\.kmhd\.eu|katdrive\.|filepress\.|"
    r"hubdrive\.|yuudrive|sharer\.pw|serfile|multiup|gdflix|katdrive)",
    re.I,
)


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _size_tag(n):
    m = re.search(r"([\d.,]+)\s*(TiB|GiB|MiB|KiB|TB|GB|MB|KB)", str(n or ""), re.I)
    if not m:
        return None
    num = m.group(1).replace(",", "")
    if "." in num:
        num = num.rstrip("0").rstrip(".")
    if not num:
        return None
    return f"{num}{m.group(2).upper().replace('IB', 'B')}"


def _search(s, q):
    items = []
    try:
        r = s.get(f"{BASE}/?s={quote_plus(q)}", timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("h1 a, h2 a, h3 a, .entry-title a"):
            href, t = a.get("href"), a.get_text(strip=True)
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
            # allow all-season packs
            if not re.search(r"season\s*1\s*,?\s*2|season\s*12345|s01.?s0?\d", t, re.I):
                return False
    return True


def _pick(items, title, year=None, season=None):
    out = []
    for it in items:
        if _title_ok(it["title"], title, year=year, season=season):
            out.append(it["url"])
    return out


def _dedupe(urls):
    seen, out = set(), []
    for u in urls:
        k = u["url"] if isinstance(u, dict) else u
        if k not in seen:
            seen.add(k)
            out.append(u)
    return out


def _with_size(a, name=None):
    href = a["href"]
    lab = a.get_text(" ", strip=True)
    nm = name or lab or href.split("/")[-1]
    st = _size_tag(lab)
    if not st:
        prev = a.find_previous(["h2", "h3", "h4", "strong", "b"])
        if prev:
            pt = prev.get_text(" ", strip=True)
            if len(re.findall(r"[\d.,]+\s*(?:TiB|GiB|MiB|KiB|TB|GB|MB|KB)", pt, re.I)) == 1:
                st = _size_tag(pt)
    return {"url": href, "name": nm, "tags": [st] if st else []}


def _all_hosts(html):
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):
        if HOST_RE.search(a["href"]):
            urls.append(_with_size(a))
    return _dedupe(urls)


def _pack_links(html):
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    cutoff = None
    for el in soup.find_all(string=re.compile(r"Single Episodes", re.I)):
        cutoff = el
        break
    for a in soup.find_all("a", href=True):
        if not HOST_RE.search(a["href"]):
            continue
        if cutoff is not None:
            # skip anchors that appear after Single Episodes marker
            try:
                if a.sourcepos and cutoff.sourcepos and a.sourcepos > cutoff.sourcepos:
                    continue
            except Exception:
                pass
        text = a.get_text(" ", strip=True)
        prev = a.find_previous(["h2", "h3", "h4", "strong", "b"])
        ctx = prev.get_text(" ", strip=True) if prev else ""
        if re.search(r"Pack|ZIP|Season\s*Pack|GDFlix|Index\.Of", text + " " + ctx, re.I) or (
            cutoff is None and re.search(r"Pack", ctx, re.I)
        ):
            urls.append(_with_size(a, text or ctx))
    if urls:
        return _dedupe(urls)
    # fallback: links before first "S 1 Episode" / "Episode 1" style marker via HTML split
    raw = html
    m = re.search(r"Single Episodes Link", raw, re.I)
    chunk = raw[: m.start()] if m else raw
    soup2 = BeautifulSoup(chunk, "html.parser")
    for a in soup2.find_all("a", href=True):
        if HOST_RE.search(a["href"]):
            urls.append(_with_size(a))
    return _dedupe(urls)


def _episode_links(s, html, title, season, episode):
    soup = BeautifulSoup(html, "html.parser")
    sn, en = int(season), int(episode)
    prefix = f"{title} S{sn:02d}E{en:02d}"
    want = re.compile(
        rf"(?:S0*{sn}E0*{en}\b|S\s*0*{sn}\s*Episode\s*0*{en}\b)",
        re.I,
    )
    nxt = re.compile(r"(?:S\d{1,2}E\d{1,3}|S\s*\d{1,2}\s*Episode\s*\d{1,3})", re.I)
    on = False
    items = []
    for el in soup.find_all(True):
        if el.name in ("p", "b", "strong", "h2", "h3", "h4"):
            t = " ".join(el.stripped_strings)
            if len(t) < 160 and nxt.search(t):
                on = bool(want.search(t))
        if not on or el.name != "a":
            continue
        href = (el.get("href") or "").strip()
        if not href or not (HOST_RE.search(href) or "kmhd.eu" in href):
            continue
        lab = el.get_text(" ", strip=True)
        st = _size_tag(lab)
        if re.search(r"/archives/\d+", href):
            items.extend(_from_kmhd(s, href, prefix, st) or [{"url": href, "name": prefix, "tags": [st] if st else []}])
        elif re.search(r"\d{3,4}p", lab, re.I):
            items.append({"url": href, "name": f"{prefix} {lab}".strip(), "tags": [st] if st else []})
        else:
            items.append({"url": href, "name": prefix, "tags": [st] if st else []})
    seen, out = set(), []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        out.append(it)
    return out


def _from_kmhd(s, url, prefix, size=None):
    try:
        r = s.get(url, timeout=TIMEOUT)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception:
        return []
    out = []
    tags = [size] if size else []
    for h in soup.find_all("h3"):
        q = re.sub(r"\s*\|\|.*", "", h.get_text(" ", strip=True)).strip()
        q = re.sub(r"\s*links?\s*$", "", q, flags=re.I).strip()
        if not re.search(r"\d{3,4}p", q, re.I) or re.search(r"watch\s*online", q, re.I):
            continue
        name = f"{prefix} {q}".strip()
        st = _size_tag(q) or size
        ht = [st] if st else list(tags)
        for a in h.find_all("a", href=True):
            href = a["href"].strip()
            if HOST_RE.search(href):
                out.append({"url": href, "name": name, "tags": ht})
    return out


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = f"{title} {year}" if year else title
        posts = _pick(_search(s, q), title, year=year)
        if not posts:
            posts = _pick(_search(s, title), title, year=year)
        if not posts:
            return []
        r = s.get(posts[0], timeout=TIMEOUT)
        from scrapers._resolve import expand

        return expand(s, _all_hosts(r.text) or [])
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = f"{title} season {int(season)}"
        posts = _pick(_search(s, q), title, year=year, season=season)
        if not posts:
            posts = _pick(_search(s, f"{title} s{int(season)}"), title, year=year, season=season)
        if not posts:
            return []
        # prefer dedicated season post
        prefer = [u for u in posts if re.search(rf"s0*{int(season)}(?:-|$|/)", u, re.I)]
        url = (prefer or posts)[0]
        r = s.get(url, timeout=TIMEOUT)
        from scrapers._resolve import expand

        return expand(s, _pack_links(r.text) or _all_hosts(r.text) or [])
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = f"{title} season {int(season)}"
        posts = _pick(_search(s, q), title, year=year, season=season)
        if not posts:
            posts = _pick(_search(s, f"{title} s{int(season)}"), title, year=year, season=season)
        if not posts:
            return []
        prefer = [u for u in posts if re.search(rf"s0*{int(season)}(?:-|$|/)", u, re.I)]
        from scrapers._resolve import expand

        for url in prefer or posts:
            r = s.get(url, timeout=TIMEOUT)
            links = _episode_links(s, r.text, title, season, episode)
            if links:
                return expand(s, links)
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

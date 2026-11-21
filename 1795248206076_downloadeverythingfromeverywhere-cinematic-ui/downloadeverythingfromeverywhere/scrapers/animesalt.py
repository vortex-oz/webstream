import re
from urllib.parse import quote_plus, urljoin

from scrapers import _http as requests
from bs4 import BeautifulSoup

SITES = ("https://animesalt.link", "https://animesalt.top")
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}
TIMEOUT = 20
HOST = re.compile(
    r"(mega\.nz|mediafire\.com|gofile\.io|pixeldrain\.|drive\.google\.com)",
    re.I,
)


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
        qs += ["Your Name", "Kimi no Na wa"]
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
        return "re zero" in nt or "rezero" in pc
    if "your name" in wt or "kimi no na wa" in wt:
        return "your name" in nt or "kimi no na wa" in nt
    return bool(wt) and wt in nt


def _href(a):
    return (a.get("href") or "").split()[0].strip()


def _base(s):
    for b in SITES:
        try:
            r = s.get(b + "/", timeout=TIMEOUT)
            if r.status_code == 200 and "Just a moment" not in (r.text or "")[:500]:
                return r.url.rstrip("/") if getattr(r, "url", None) else b
        except Exception:
            continue
    return SITES[0]


def _search(s, base, q):
    items = []
    try:
        r = s.get(f"{base}/?s={quote_plus(q)}", timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")
        for art in soup.select("article"):
            a = art.find("a", href=True)
            h = art.find(["h1", "h2", "h3"])
            href = urljoin(base + "/", _href(a)) if a else ""
            t = (h.get_text(" ", strip=True) if h else "") or (a.get_text(" ", strip=True) if a else "")
            if href and ("/series/" in href or "/movies/" in href):
                items.append({"title": t or href.rstrip("/").split("/")[-1], "url": href})
    except Exception:
        pass
    return items


def _find(s, base, title, movies=False):
    want = "/movies/" if movies else "/series/"
    other = "/series/" if movies else "/movies/"
    seen, out = set(), []
    for q in _alts(title):
        for it in _search(s, base, q):
            u = it["url"]
            if u in seen or other in u:
                continue
            if want not in u:
                continue
            if not _hit(it["title"], title):
                continue
            seen.add(u)
            out.append(it)
        if out:
            break
    return out


def _ok(u):
    u = (u or "").split()[0]
    if not u.startswith("http"):
        return None
    if "animesalt." in u or "trdownload" in u:
        return None
    return u if HOST.search(u) else None


def _size_tag(blob):
    m = re.search(r"([\d.]+)\s*(TB|GB|MB|KB)\b", blob or "", re.I)
    if not m:
        return None
    num = m.group(1)
    if "." in num:
        num = num.rstrip("0").rstrip(".")
    return f"{num}{m.group(2).upper()}" if num else None


def _file(s, url, page):
    href = urljoin(page, (url or "").split()[0])
    got = _ok(href)
    if got:
        return got
    try:
        r = s.get(href, timeout=TIMEOUT, allow_redirects=False)
        loc = (r.headers.get("Location") or "").split()[0]
        got = _ok(urljoin(href, loc) if loc else "")
        if got:
            return got
        r2 = s.get(href, timeout=TIMEOUT, allow_redirects=True)
        return _ok(r2.url or "")
    except Exception:
        return None


def _tr_links(s, html, prefix, page):
    soup = BeautifulSoup(html or "", "html.parser")
    out, seen = [], set()
    for tr in soup.select(".download-links tr"):
        a = tr.find("a", href=True)
        href = _href(a) if a else ""
        if not href:
            continue
        q = ""
        tds = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        blob = " ".join(tds)
        m = re.search(r"\b(\d{3,4}p)\b", blob, re.I)
        if m:
            q = m.group(1)
        dest = _file(s, href, page)
        if not dest or dest in seen:
            continue
        seen.add(dest)
        lab = "Mega" if "mega.nz" in dest else "Host"
        st = None
        for td in tds:
            st = _size_tag(td)
            if st:
                break
        name = " ".join(x for x in (prefix, q, st, lab) if x)
        row = {"url": dest, "name": name}
        if st:
            row["tags"] = [st]
        out.append(row)
    return out


def _page_dls(s, url, prefix):
    try:
        r = s.get(url, timeout=TIMEOUT)
        if r.status_code != 200:
            return []
        return _tr_links(s, r.text, prefix, r.url or url)
    except Exception:
        return []


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        base = _base(s)
        posts = _find(s, base, title, movies=True)
        if not posts:
            return []
        name = f"{title} ({year})" if year else title
        return _page_dls(s, posts[0]["url"], name) or []
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    return


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        base = _base(s)
        posts = _find(s, base, title, movies=False)
        if not posts:
            return []
        sn, en = int(season), int(episode)
        slug = posts[0]["url"].rstrip("/").split("/")[-1]
        prefix = f"{title} S{sn:02d}E{en:02d}"
        direct = f"{base}/episode/{slug}-{sn}x{en}/"
        rows = _page_dls(s, direct, prefix)
        if rows:
            return rows
        try:
            r = s.get(posts[0]["url"], timeout=TIMEOUT)
            soup = BeautifulSoup(r.text, "html.parser")
        except Exception:
            return []
        seas = []
        pid = None
        for btn in soup.select("a.season-btn[data-post][data-season]"):
            pid = pid or btn.get("data-post")
            try:
                seas.append(int(btn.get("data-season")))
            except Exception:
                pass
        if not pid:
            return []
        ajax = f"{base}/wp-admin/admin-ajax.php"
        for sea in seas or [sn]:
            try:
                r = s.get(
                    ajax,
                    params={"action": "action_select_season", "season": sea, "post": pid},
                    timeout=TIMEOUT,
                )
            except Exception:
                continue
            soup = BeautifulSoup(r.text or "", "html.parser")
            for a in soup.find_all("a", href=True):
                href = urljoin(base + "/", _href(a))
                if re.search(rf"/episode/[^/]+-(?:{sea}|[1-9]\d?)x{en}/?$", href):
                    return _page_dls(s, href, f"{title} E{en:02d}") or []
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

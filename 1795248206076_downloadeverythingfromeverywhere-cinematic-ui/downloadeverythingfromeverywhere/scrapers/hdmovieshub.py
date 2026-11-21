import re
from urllib.parse import urljoin, quote_plus, unquote

from scrapers import _http as requests
from scrapers._tags import tags_from
from bs4 import BeautifulSoup

BASE = "https://hdmovieshub.fyi"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
TIMEOUT = 20
FINAL_HOST_RE = re.compile(
    r"(gdflix|hubcloud|hubdrive|multicloudlinks|vcloud\.|filebee|"
    r"gofile\.io|vikingfile|megaup\.|filepress)",
    re.I,
)


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _title_ok(post_title, want, year=None, series=False):
    pt = _norm(post_title)
    wt = _norm(want)
    if not wt or wt not in pt:
        return False
    if year and str(year) not in post_title and str(year) not in pt:
        if not series:
            return False
    # avoid longer franchise titles stealing exact matches (Avatar vs Avatar Fire)
    rest = pt.replace(wt, "", 1).strip()
    if not series and rest and not re.match(r"^(\d{4}|dual|hindi|english|bluray|web|480|720|1080|2160|hevc|x264|x265|esub).*$", rest):
        # allow quality/audio tokens after title
        bad = re.search(r"\b(fire|way|airbender|aang|last)\b", rest)
        if bad and wt == "avatar":
            return False
    return True


def _wp_search(s, q):
    try:
        r = s.get(f"{BASE}/wp-json/wp/v2/posts", params={"search": q, "per_page": 20}, timeout=TIMEOUT)
        if r.ok:
            return r.json()
    except Exception:
        pass
    try:
        r = s.get(f"{BASE}/?s={quote_plus(q)}", timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for a in soup.select("h1 a, h2 a, h3 a, .entry-title a"):
            href = a.get("href")
            t = a.get_text(strip=True)
            if href and t:
                out.append({"title": {"rendered": t}, "link": href})
        return out
    except Exception:
        return []


def _pick_posts(posts, title, year=None, season=None):
    picked = []
    for p in posts:
        t = re.sub(r"<[^>]+>", "", (p.get("title") or {}).get("rendered") or p.get("title") or "")
        if not _title_ok(t, title, year=year, series=season is not None):
            continue
        if season is not None:
            if not re.search(rf"(?:season|s)\s*0*{int(season)}\b", t, re.I) and not re.search(
                rf"s0*{int(season)}\b", t, re.I
            ):
                # complete packs like Season 1-2 still ok for that season
                if not re.search(rf"(?:season|s)\s*0*{int(season)}\s*[-–to&]", t, re.I):
                    continue
        picked.append(p.get("link"))
    return picked


def _extract_links(html, base=BASE):
    soup = BeautifulSoup(html, "html.parser")
    quality, finals = [], []
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"])
        text = a.get_text(" ", strip=True)
        if "links.hdmovieshub" in href:
            quality.append((href, text))
        elif FINAL_HOST_RE.search(href):
            finals.append((href, text))
    return quality, finals


def _season_in_label(label, season):
    """True if label is for this season (or has no season marker)."""
    sn = int(season)
    nums = [int(x) for x in re.findall(r"(?:season|s)\s*0*(\d{1,2})\b", label or "", re.I)]
    if not nums:
        return True
    if sn in nums:
        return True
    # ranges like season 1-3 / s01-s03 already yield multiple nums via findall? 
    # "season 1-2" → findall may only get 1 depending on pattern; also check range form
    if re.search(rf"(?:season|s)\s*0*{sn}\s*[-–to&/]\s*0*\d+", label or "", re.I):
        return True
    if re.search(rf"(?:season|s)\s*0*\d+\s*[-–to&/]\s*0*{sn}\b", label or "", re.I):
        return True
    return False


def _label(name, url):
    slug = unquote((url or "").rstrip("/").split("/")[-1])
    slug = re.sub(r"(\d+)-(\d+)(kb|mb|gb|tb)\b", r"\1.\2\3", slug, flags=re.I)
    return name or slug.replace("-", " ")


def _expand_intermediate(s, quality_urls, finals, season=None):
    out = []
    seen = set()

    def add(url, name=""):
        if url in seen:
            return
        label = _label(name, url)
        if season is not None and not _season_in_label(label, season):
            return
        seen.add(url)
        out.append({"url": url, "name": label, "tags": tags_from(label)})

    for u, name in finals:
        add(u, name)
    for u, name in quality_urls[:8]:
        parent = _label(name, u)
        if season is not None and not _season_in_label(parent, season):
            continue
        add(u, parent)
        try:
            r = s.get(u, timeout=TIMEOUT)
            soup = BeautifulSoup(r.text, "html.parser")
            content = soup.select_one(".entry-content, .post-content, article .entry-content, .page-content")
            scope = content or soup
            for a in scope.find_all("a", href=True):
                href = urljoin(u, a["href"])
                if FINAL_HOST_RE.search(href):
                    add(href, parent)
        except Exception:
            pass
    from scrapers._resolve import expand

    return expand(s, out)


def _from_posts(s, posts, season=None):
    quality, finals = [], []
    for link in posts[:3]:
        try:
            r = s.get(link, timeout=TIMEOUT)
            q, f = _extract_links(r.text)
            quality.extend(q)
            finals.extend(f)
        except Exception:
            continue
    return _expand_intermediate(s, quality, finals, season=season)


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = f"{title} {year}" if year else title
        posts = _pick_posts(_wp_search(s, q), title, year=year)
        if not posts:
            posts = _pick_posts(_wp_search(s, title), title, year=year)
        if not posts:
            return []
        return _from_posts(s, posts) or []
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = f"{title} season {int(season)}"
        posts = _pick_posts(_wp_search(s, q), title, year=year, season=season)
        if not posts:
            posts = _pick_posts(_wp_search(s, title), title, year=year, season=season)
        if not posts:
            return []
        return _from_posts(s, posts, season=season) or []
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        q = f"{title} season {int(season)}"
        posts = _pick_posts(_wp_search(s, q), title, year=year, season=season)
        if not posts:
            posts = _pick_posts(_wp_search(s, title), title, year=year, season=season)
        if not posts:
            return []
        quality, finals = [], []
        ep_re = re.compile(rf"(?:e|ep|episode)\s*0*{int(episode)}\b", re.I)
        for link in posts[:3]:
            r = s.get(link, timeout=TIMEOUT)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = urljoin(link, a["href"])
                text = a.get_text(" ", strip=True)
                if not (ep_re.search(text) or ep_re.search(href)):
                    continue
                if "links.hdmovieshub" in href:
                    quality.append((href, text))
                elif FINAL_HOST_RE.search(href):
                    finals.append((href, text))
        out = _expand_intermediate(s, quality, finals, season=season)
        if out:
            return out
        # site often only has season packs — return those for this season only
        return _from_posts(s, posts, season=season) or []
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

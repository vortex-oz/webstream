import re
from urllib.parse import quote_plus, urljoin

from scrapers import _http as requests
from scrapers._tags import tags_from
from bs4 import BeautifulSoup

BASE = "https://pahe.ink"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 40


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _get(s, url):
    r = s.get(url, timeout=TIMEOUT)
    if r.status_code != 200 or "Just a moment" in r.text:
        return None
    return BeautifulSoup(r.text, "html.parser")


def _search(s, title):
    soup = _get(s, f"{BASE}/?s={quote_plus(title)}")
    if soup is None:
        return []
    items = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(BASE + "/", a["href"])
        t = a.get_text(" ", strip=True)
        if not t or href in seen:
            continue
        # post URLs look like /title-year-quality/
        if re.search(r"/[a-z0-9-]+-\d{4}[^/]*/$", href) or re.search(r"/[a-z0-9-]+-season-\d+", href):
            seen.add(href)
            items.append({"title": t, "url": href})
    return items


def _pick(items, title, year=None, season=None):
    wt = _norm(title)
    best = None
    for it in items:
        nt = _norm(it["title"])
        if wt == nt:
            return it["url"]
        if wt in nt or nt in wt:
            if year and str(year) in it["title"]:
                return it["url"]
            if season and f"season {season}" in nt:
                return it["url"]
            if best is None:
                best = it["url"]
    return best


def _dl_links(soup, prefix="", episode=None):
    out, seen = [], set()
    boxes = soup.select(".box-inner-block") or [soup]
    current_ep = None
    for box in boxes:
        for tag in box.find_all(["b", "strong"]):
            m = re.match(r"Episode\s*0*(\d+)\b", tag.get_text(" ", strip=True), re.I)
            if m:
                current_ep = int(m.group(1))
                break
        if episode is not None and current_ep != int(episode):
            continue
        buf, q_lab = "", ""
        for el in box.descendants:
            if isinstance(el, str):
                t = " ".join(el.split())
                if not t:
                    continue
                if re.search(r"\d{3,4}p", t, re.I):
                    buf = t
                elif buf:
                    buf += " " + t
                qm = re.search(
                    r"(\d{3,4}p\b.{0,70}?)\s*\|\s*([\d.]+\s*(?:GB|MB))",
                    buf,
                    re.I,
                )
                if qm:
                    q = re.sub(r"\s+", " ", qm.group(1)).strip()
                    q = re.sub(r"^Episode\s*\d+\s*", "", q, flags=re.I)
                    q_lab = f"{q} [{qm.group(2).strip()}]"
                    buf = ""
                continue
            if getattr(el, "name", None) != "a":
                continue
            href = el.get("href") or ""
            if "teknoasian.com" not in href or href in seen:
                continue
            seen.add(href)
            name = " ".join(x for x in (prefix, q_lab) if x).strip()
            out.append({
                "url": href,
                "name": name or prefix or "download",
                "tags": tags_from(name, q_lab),
            })
    return out


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        url = _pick(_search(s, title), title, year=year)
        if not url:
            return []
        soup = _get(s, url)
        if soup is None:
            return []
        return _dl_links(soup, f"{title} ({year})" if year else title) or []
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        url = _pick(_search(s, title), title, year=year, season=season)
        if not url:
            return []
        soup = _get(s, url)
        if soup is None:
            return []
        return _dl_links(soup, f"{title} S{int(season):02d}") or []
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        items = _search(s, title)
        wt = _norm(title)
        urls = []
        for it in items:
            nt = _norm(it["title"])
            if wt not in nt:
                continue
            if f"season {int(season)}" not in nt and not re.search(rf"s0*{int(season)}\b", nt):
                continue
            urls.append(it["url"])
        prefix = f"{title} S{int(season):02d}E{int(episode):02d}"
        for url in urls[:4]:
            soup = _get(s, url)
            if soup is None:
                continue
            rows = _dl_links(soup, prefix, episode=episode)
            if rows:
                return rows
        return []
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

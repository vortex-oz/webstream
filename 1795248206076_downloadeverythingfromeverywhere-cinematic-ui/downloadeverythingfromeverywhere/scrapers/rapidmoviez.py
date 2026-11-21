# Free hosts only (rapidrar / clicknupload)
import re
from urllib.parse import quote, urlparse

from scrapers import _http as requests
from scrapers._tags import tags_from
from bs4 import BeautifulSoup

BASE = "https://rmz.cr"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 20
HOST_RE = re.compile(
    r"https?://(?:(?:www\.)?(?:rapidrar|clicknupload)[^\s<>\"']+)",
    re.I,
)


def _get(url):
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
        if r.status_code != 200:
            return None
        return r
    except Exception:
        return None


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _search(query):
    # spaces in /search/ often 403; prefer hyphenated form
    q = query.strip().replace(" ", "-")
    r = _get(f"{BASE}/search/{quote(q)}")
    if not r:
        r = _get(f"{BASE}/search/{quote(query)}")
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(" ", strip=True)
        if href.startswith("/") and not href.startswith(("/search", "/account", "/static", "/release")):
            if text and href.count("/") == 1:
                out.append((text, BASE + href))
        elif href.startswith("/release/"):
            out.append((text, BASE + href))
    return out


def _title_page(title, year=None, imdb_id=None):
    if imdb_id:
        results = _search(imdb_id)
        for text, url in results:
            if "/release/" not in url and _norm(title) in _norm(text):
                return url
        for text, url in results:
            if "/release/" not in url:
                return url
    results = _search(title)
    nt = _norm(title)
    for text, url in results:
        if "/release/" in url:
            continue
        if nt in _norm(text):
            if year is None or str(year) in text:
                return url
    for text, url in results:
        if "/release/" not in url and nt in _norm(text):
            return url
    return None


def _title_token(title):
    return _norm(title)


def _has_title(blob, title):
    nt = _title_token(title)
    if not nt:
        return False
    # require full normalized title; reject longer titles that only share a prefix
    if nt not in blob:
        return False
    # avoid matching "avatar" inside "avatarfireandash" / "avatarthewayofwater"
    idx = blob.find(nt)
    after = blob[idx + len(nt) : idx + len(nt) + 12]
    if after and after[0].isalpha() and not after.startswith(("extended", "remastered", "repack", "edition", "bluray", "webrip", "hdtv", "dvdrip", "internal", "complete")):
        # allow year or quality markers right after title
        if not re.match(r"\d{4}|19\d{2}|20\d{2}|s\d{2}|19|20", after):
            return False
    return True


def _release_urls(title_url, title, pred):
    r = _get(title_url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    releases = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("/release/"):
            continue
        text = a.get_text(" ", strip=True)
        blob = _norm(text + href)
        if not _has_title(blob, title):
            continue
        if pred(text, href, blob):
            releases.append((BASE + href, text))
    seen, out = set(), []
    for url, text in releases:
        if url in seen:
            continue
        seen.add(url)
        out.append((url, text))
    return out


def _host_links(release_url, release_name=""):
    r = _get(release_url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    h1 = soup.find("h1")
    name = release_name or (h1.get_text(" ", strip=True) if h1 else "") or release_url.rstrip("/").split("/")[-1]
    tags = []
    for q in ("2160p", "1080p", "720p", "480p", "360p"):
        if re.search(rf"\b{q}\b", name, re.I):
            tags.append(q)
    for lab, pat in (("WEB-DL", r"web"), ("x265", r"x265|hevc"), ("x264", r"x264"), ("BluRay", r"bluray|blu.?ray")):
        if re.search(pat, name, re.I):
            tags.append(lab)
    links = []
    seen_ids = set()
    for m in HOST_RE.findall(r.text):
        low = m.lower()
        if any(x in low for x in ("payment", "guide", "account", "premium", "reseller")):
            continue
        url = m.rstrip(").,;\"'")
        path = re.sub(r"^https?://[^/]+", "", url)
        key = path or url
        if key in seen_ids:
            continue
        seen_ids.add(key)
        # prefer filename in host URL when present
        from urllib.parse import unquote

        fname = unquote(urlparse(url).path.rstrip("/").split("/")[-1] if "://" in url else "")
        item_name = fname if fname and re.search(r"\.(mkv|mp4|rar|zip)$", fname, re.I) else name
        item_tags = list(dict.fromkeys(
            tags
            + [q for q in ("1080p", "720p", "480p") if re.search(rf"\b{q}\b", item_name, re.I)]
            + [t for t in tags_from(item_name, name) if re.fullmatch(r"\d+(?:\.\d+)?(?:KB|MB|GB|TB)", t, re.I)]
        ))
        links.append({"url": url, "name": item_name or name or "RMZ", "tags": item_tags})
    return links


def _collect(title_url, title, pred, limit=3):
    out = []
    for rel, text in _release_urls(title_url, title, pred)[:limit]:
        out.extend(_host_links(rel, text))
    # dedupe by url
    seen, deduped = set(), []
    for it in out:
        u = it["url"] if isinstance(it, dict) else it
        if u in seen:
            continue
        seen.add(u)
        deduped.append(it)
    return deduped


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        page = _title_page(title, year=year, imdb_id=imdb_id)
        if not page:
            return []

        def pred(text, href, blob):
            if re.search(r"s\d{2}e\d{2}", blob):
                return False
            if re.search(r"s\d{2}", blob) and "trilogy" not in blob:
                return False
            if year is not None and str(year) not in text and str(year) not in href:
                return False
            return True

        return _collect(page, title, pred)
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        page = _title_page(title, year=year, imdb_id=imdb_id)
        if not page:
            return []
        s = f"s{int(season):02d}"

        def pred(text, href, blob):
            if re.search(rf"{s}e\d{{2}}", blob):
                return False
            if s not in blob:
                return False
            return True

        return _collect(page, title, pred)
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        page = _title_page(title, year=year, imdb_id=imdb_id)
        ep = f"s{int(season):02d}e{int(episode):02d}"

        def pred(text, href, blob):
            return ep in blob

        out = []
        if page:
            out = _collect(page, title, pred)
        if out:
            return out
        # fallback: direct release search
        for text, url in _search(f"{title} S{int(season):02d}E{int(episode):02d}"):
            if "/release/" not in url:
                continue
            blob = _norm(text + url)
            if ep in blob and _has_title(blob, title):
                out.extend(_host_links(url, text))
        seen, deduped = set(), []
        for it in out:
            u = it["url"] if isinstance(it, dict) else it
            if u in seen:
                continue
            seen.add(u)
            deduped.append(it if isinstance(it, dict) else {"url": it})
        return deduped
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

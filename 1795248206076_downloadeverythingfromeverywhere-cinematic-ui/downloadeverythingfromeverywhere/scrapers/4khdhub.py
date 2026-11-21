import re
from urllib.parse import quote_plus, urljoin

from scrapers import _http as requests
from bs4 import BeautifulSoup

BASE = "https://4khdhub.one"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 20


def _get(url):
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        return r
    except Exception:
        return None


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _search(query):
    r = _get(f"{BASE}/?s={quote_plus(query)}")
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.select("a.movie-card"):
        href = a.get("href")
        text = a.get_text(" ", strip=True)
        if href:
            out.append((text, urljoin(BASE, href)))
    if not out:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ", strip=True)
            if re.search(r"-(movie|series)-\d+/?$", href) and text:
                out.append((text, urljoin(BASE, href)))
    return out


def _pick(results, title, year=None, want_series=None):
    nt = _norm(title)
    scored = []
    for text, url in results:
        if nt not in _norm(text) and nt not in _norm(url):
            continue
        if want_series is True and "-movie-" in url:
            continue
        if want_series is False and "-series-" in url:
            continue
        score = 2
        if year is not None and str(year) in text:
            score = 3
        scored.append((score, url))
    if not scored:
        return None
    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


def _tags(*parts):
    from scrapers._tags import tags_from

    return tags_from(*parts)


def _item_label(item):
    title = item.select_one(".file-title, .episode-file-title")
    name = title.get_text(" ", strip=True) if title else ""
    if not name:
        name = item.get_text(" ", strip=True)
    sz = ""
    el = item.select_one(".badge-size")
    if el:
        sz = el.get_text(strip=True)
    if not sz:
        for b in item.select(".badge"):
            t = b.get_text(strip=True)
            if re.search(r"[\d.]+\s*(KB|MB|GB|TB)\b", t, re.I):
                sz = t
                break
    if name and sz and sz not in name:
        name = f"{name} [{sz}]"
    return name


def _hub_links(soup_or_html, scope=None, label=""):
    from scrapers._tags import clean_name, tags_from

    root = soup_or_html
    if isinstance(soup_or_html, str):
        root = BeautifulSoup(soup_or_html, "html.parser")
    links = []
    nodes = scope.find_all("a", href=True) if scope is not None else root.find_all("a", href=True)
    for a in nodes:
        href = a["href"]
        if "hubcloud" in href or "hubdrive" in href:
            text = a.get_text(" ", strip=True)
            if label and re.search(r"\.(mkv|mp4|avi|iso|zip|rar)", label, re.I):
                name = label.strip()
            else:
                name = clean_name(label) or clean_name(text) or label or text
            links.append({"url": href, "name": name, "tags": tags_from(name, text, label)})
    seen, out = set(), []
    for it in links:
        u = it["url"]
        if u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out


def _section_html(html, start_heading, end_heading=None):
    pat = re.escape(start_heading) + r".*?"
    if end_heading:
        pat += r"(?=" + re.escape(end_heading) + r")"
    m = re.search(pat, html, re.S | re.I)
    return m.group(0) if m else ""


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        q = f"{title} {year}" if year else title
        url = _pick(_search(q), title, year=year, want_series=False)
        if not url:
            url = _pick(_search(title), title, year=year, want_series=False)
        if not url:
            return []
        r = _get(url)
        if not r:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for item in soup.select(".download-item, .episode-download-item"):
            out.extend(_hub_links(item, label=_item_label(item)))
        if not out:
            out = _hub_links(r.text)
        from scrapers._resolve import expand

        return expand(requests.Session(), out or _hub_links(r.text))
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    try:
        url = _pick(_search(title), title, year=year, want_series=True)
        if not url:
            return []
        r = _get(url)
        if not r:
            return []
        chunk = _section_html(r.text, "Download Complete Season", "Download Individual Episodes")
        if not chunk:
            return []
        soup = BeautifulSoup(chunk, "html.parser")
        s = f"S{int(season):02d}"
        links = []
        for item in soup.select(".download-item"):
            blob = item.get_text(" ", strip=True)
            if re.search(rf"\b{s}\b", blob) and not re.search(rf"{s}E\d{{2}}", blob, re.I):
                links.extend(_hub_links(item, label=_item_label(item)))
        if not links:
            for item in soup.select(".download-item"):
                num = item.select_one(".episode-number")
                if num and num.get_text(strip=True) == s:
                    links.extend(_hub_links(item, label=_item_label(item)))
        from scrapers._resolve import expand

        return expand(requests.Session(), links)
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        url = _pick(_search(title), title, year=year, want_series=True)
        if not url:
            return []
        r = _get(url)
        if not r:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        ep = f"S{int(season):02d}E{int(episode):02d}"
        links = []
        for item in soup.select(".episode-download-item"):
            label = _item_label(item)
            if ep in label:
                links.extend(_hub_links(item, label=label))
        from scrapers._resolve import expand

        return expand(requests.Session(), links)
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

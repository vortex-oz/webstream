import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from scrapers import _http as requests
from scrapers._tags import item as tag_item

BASE = "https://uhdmovies.autos"
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 20
SID_OK = re.compile(
    r"(?:cloud|tech)\.unblockedgames\.world|tech\.examzculture\.in|tech\.creativeexpressionsblog\.com",
    re.I,
)
FILE_HOST = re.compile(r"driveseed\.|driveleech\.", re.I)
JUNK_DEST = re.compile(r"uhdmovies\.|t\.me/|telegram", re.I)
EP_BTN = re.compile(r"^Episode\s+0*(\d+)\b", re.I)


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


def _seasons(text):
    found = set()
    t = text or ""
    for m in re.finditer(r"season[s]?[\s-]*(\d{1,2})(?:[\s\-–to]+(\d{1,2}))?", t, re.I):
        a = int(m.group(1))
        b = int(m.group(2) or a)
        lo, hi = min(a, b), max(a, b)
        if hi - lo <= 20:
            found.update(range(lo, hi + 1))
    for m in re.finditer(r"\bS(\d{1,2})(?:E\d{1,3})?\b", t, re.I):
        found.add(int(m.group(1)))
    return found


def _search(s, title):
    soup = _get(s, f"{BASE}/?s={quote_plus(title)}")
    if soup is None:
        return []
    items, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(BASE + "/", a["href"])
        t = a.get_text(" ", strip=True)
        if not t or href in seen or not re.search(r"download-[a-z0-9-]+", href):
            continue
        seen.add(href)
        items.append({"title": t, "url": href})
    return items


def _pick(items, title, year=None, season=None):
    wt = _norm(title)
    ranked = []
    for it in items:
        blob = it["title"] + " " + it["url"]
        nt = _norm(it["title"])
        if wt not in nt and nt not in wt:
            continue
        seasons = _seasons(blob)
        if season is not None and seasons and int(season) not in seasons:
            continue
        score = 2 if wt in nt else 1
        if year and str(year) in it["title"]:
            score += 2
        if season is not None and seasons:
            score += 3 if seasons == {int(season)} else 1
        ranked.append((score, it["url"]))
    ranked.sort(key=lambda x: -x[0])
    return ranked[0][1] if ranked else None


def _nearby(a, forward=False):
    el = a
    for _ in range(25):
        el = el.find_next(string=True) if forward else el.find_previous(string=True)
        if not el:
            break
        t = re.sub(r"\s+", " ", str(el)).strip()
        if len(t) < 12 or EP_BTN.match(t):
            continue
        if re.search(r"\d{3,4}p|\.mkv|\.mp4", t, re.I):
            return t[:220]
    return ""


def _label(a, per_ep=False):
    if per_ep:
        p = a.find_parent("p")
        if p:
            for el in p.previous_siblings:
                t = el.get_text(" ", strip=True) if hasattr(el, "get_text") else ""
                t = re.sub(r"\s+", " ", t).strip()
                if len(t) >= 12:
                    return t[:400]
        return _nearby(a)
    wrap = a
    while wrap.parent is not None and wrap.parent.name not in ("p", "div", "li", "td", "article"):
        wrap = wrap.parent
    for el in wrap.next_siblings:
        if getattr(el, "name", None) in (None, "hr", "br"):
            continue
        t = el.get_text(" ", strip=True) if hasattr(el, "get_text") else ""
        t = re.sub(r"\s+", " ", t or "").strip()
        if not t:
            continue
        if hasattr(el, "find") and el.find("a", href=True):
            break
        return t[:400]
    return _nearby(a, forward=True) or _nearby(a)


def _pick_size(text, per_ep=False):
    t = re.sub(r"([TGMK])\s+B\b", r"\1B", re.sub(r"\s+", " ", text or ""), flags=re.I)
    if per_ep:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*(KB|MB|GB|TB)\s*/\s*E\b", t, re.I)
        if m:
            return f"{m.group(1)} {m.group(2)}"
    m = re.search(r"\[\s*(\d+(?:[.,]\d+)?)\s*(KB|MB|GB|TB)\s*\]", t, re.I)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    found = re.findall(r"(\d+(?:[.,]\d+)?)\s*(KB|MB|GB|TB)\b", t, re.I)
    if len(found) == 1:
        return f"{found[0][0]} {found[0][1]}"
    return ""


def _sid_file(sid_url, label=""):
    try:
        s = _session()
        r = s.get(sid_url, timeout=TIMEOUT)
        if r.status_code != 200 or "Just a moment" in r.text:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        form = soup.find(id="landing")
        if not form:
            return None
        data = {i.get("name"): i.get("value", "") for i in form.find_all("input") if i.get("name")}
        r = s.post(
            urljoin(str(r.url), form.get("action") or "/"),
            data=data,
            timeout=TIMEOUT,
            headers={"Referer": str(r.url), "Content-Type": "application/x-www-form-urlencoded"},
        )
        soup = BeautifulSoup(r.text, "html.parser")
        form = soup.find(id="landing")
        if not form:
            return None
        data = {i.get("name"): i.get("value", "") for i in form.find_all("input") if i.get("name")}
        r = s.post(
            urljoin(str(r.url), form.get("action") or "/"),
            data=data,
            timeout=TIMEOUT,
            headers={"Referer": str(r.url), "Content-Type": "application/x-www-form-urlencoded"},
        )
        html = r.text
        cm = re.search(r"s_343\('([^']+)',\s*'([^']+)'", html)
        lm = re.search(r'c\.setAttribute\("href",\s*"([^"]+)"\)', html)
        if not cm or not lm:
            return None
        name, val = cm.group(1), cm.group(2)
        go = urljoin(str(r.url), lm.group(1))
        try:
            s.cookies.set(name, val)
        except Exception:
            pass
        r = s.get(
            go,
            timeout=TIMEOUT,
            headers={"Referer": str(r.url), "Cookie": f"{name}={val}"},
        )
        soup = BeautifulSoup(r.text, "html.parser")
        meta = soup.find("meta", attrs={"http-equiv": lambda x: x and x.lower() == "refresh"})
        dest = ""
        if meta and meta.get("content"):
            m = re.search(r"url=(.*)", meta["content"], re.I)
            dest = (m.group(1) if m else "").strip().strip("\"'")
        dest = urljoin(str(r.url), dest) if dest else ""
        if not dest or JUNK_DEST.search(dest) or not FILE_HOST.search(dest):
            return None
        r = s.get(dest, timeout=TIMEOUT, allow_redirects=True)
        m = re.search(r'window\.location\.replace\("([^"]+)"\)', r.text or "")
        if m:
            dest = urljoin(str(r.url), m.group(1))
            r = s.get(dest, timeout=TIMEOUT, allow_redirects=True)
        soup = BeautifulSoup(r.text, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        title = re.sub(r"\s*[-–]\s*DriveSeed.*", "", title, flags=re.I).strip()
        final = str(r.url or dest)
        if not FILE_HOST.search(final):
            return None
        return tag_item(final, title, label)
    except Exception:
        return None


def _resolve(rows):
    pairs, seen = [], set()
    for row in rows or []:
        if isinstance(row, str):
            u, lab = row, ""
        else:
            u, lab = row[0], (row[1] if len(row) > 1 else "")
        if not u or u in seen:
            continue
        seen.add(u)
        pairs.append((u, lab))
    if not pairs:
        return []
    out = []
    with ThreadPoolExecutor(max_workers=min(6, len(pairs))) as ex:
        futs = [ex.submit(_sid_file, u, lab) for u, lab in pairs]
        for fut in as_completed(futs):
            got = fut.result()
            if got:
                out.append(got)
    return out


def _movie_sids(soup):
    urls = []
    for a in soup.select("a.maxbutton-download-g-drive[href]"):
        href = a.get("href") or ""
        if SID_OK.search(href) and "sid=" in href:
            urls.append((href, _pick_size(_label(a))))
    return urls


def _episode_sids(soup, season, episode):
    ep_re = re.compile(rf"^Episode\s+0*{int(episode)}(?!\d)", re.I)
    want = int(season)
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "sid=" not in href or not SID_OK.search(href):
            continue
        if not ep_re.match(a.get_text(" ", strip=True)):
            continue
        q = _label(a, per_ep=True) or _nearby(a)
        seasons = _seasons(q)
        if seasons and want not in seasons:
            continue
        urls.append((href, _pick_size(q, per_ep=True)))
    return urls


def _season_sids(soup, season):
    want = int(season)
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "sid=" not in href or not SID_OK.search(href):
            continue
        t = a.get_text(" ", strip=True)
        if not EP_BTN.match(t) and "gdrive-episode" not in " ".join(a.get("class") or []):
            continue
        q = _label(a, per_ep=True) or _nearby(a)
        seasons = _seasons(q)
        if seasons and want not in seasons:
            continue
        if not seasons:
            continue
        urls.append((href, _pick_size(q, per_ep=True)))
    return urls


def _keep_episode(rows, season, episode):
    want = f"S{int(season):02d}E{int(episode):02d}"
    alt = f"S{int(season)}E{int(episode)}"
    out = []
    for it in rows:
        blob = f"{it.get('name','')} {it.get('url','')}"
        if re.search(rf"{want}|{alt}\b", blob, re.I):
            out.append(it)
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
        return _resolve(_movie_sids(soup))
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
        return _resolve(_season_sids(soup, season))
    except Exception:
        return []


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        url = _pick(_search(s, title), title, year=year, season=season)
        if not url:
            return []
        soup = _get(s, url)
        if soup is None:
            return []
        rows = _resolve(_episode_sids(soup, season, episode))
        return _keep_episode(rows, season, episode)
    except Exception:
        return []

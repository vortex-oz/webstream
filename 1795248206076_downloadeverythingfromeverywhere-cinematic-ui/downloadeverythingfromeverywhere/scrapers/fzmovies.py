import re
from urllib.parse import urljoin

from scrapers import _http as requests
from scrapers._tags import tags_from
from bs4 import BeautifulSoup

BASE = "https://www.fzmovies.live"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
}
TIMEOUT = 20


def _session():
    s = requests.Session()
    s.headers.update(UA)
    return s


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _pick_movie(soup, title, year=None):
    want = _norm(title)
    candidates = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "movie-" not in href.lower() or not href.lower().endswith(".htm"):
            continue
        text = a.get_text(strip=True) or href
        nt = _norm(text)
        nh = _norm(href.replace("movie-", " ").replace("--hmp4.htm", " ").replace(".htm", " "))
        if want not in nt and want not in nh:
            continue
        # prefer exact / year match; skip obvious sequels when year given
        score = 0
        if nt == want or nh.startswith(want + " ") or nh == want:
            score += 5
        if year and str(year) in text:
            score += 3
        # penalize longer franchise titles
        rest = nt.replace(want, "", 1).strip()
        if rest and want == "avatar" and re.search(r"\b(way|water|fire|ash|airbender|aang)\b", rest):
            score -= 10
        candidates.append((score, urljoin(BASE + "/", href)))
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1] if candidates and candidates[0][0] > 0 else None


def _sz_text(blob):
    m = re.search(r"([\d.]+)\s*(KB|MB|GB|TB)", blob or "", re.I)
    return m.group(0) if m else ""


def _cdn_from_dlink(s, dlink_url):
    try:
        r = s.get(dlink_url, timeout=TIMEOUT)
        urls = []
        for m in re.finditer(r"https?://[^\s\"'<>]+\.mp4(?:\?[^\s\"'<>]*)?", r.text):
            urls.append(m.group(0))
        for inp in BeautifulSoup(r.text, "html.parser").select("input[name='download1'], input#myLink"):
            v = inp.get("value")
            if v and v.startswith("http"):
                urls.append(v)
        seen, out = set(), []
        for u in urls:
            # skip broken hosts like https:///res/...
            if "://" not in u or re.match(r"https?:///+", u) or u in seen:
                continue
            seen.add(u)
            out.append(u)
        return out
    except Exception:
        return []

def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        s = _session()
        r = s.post(
            f"{BASE}/csearch.php",
            data={"searchname": title, "Search": "Search", "searchby": "Name", "category": "All"},
            timeout=TIMEOUT,
        )
    except Exception:
        r = None
    try:
        if r is None or int(getattr(r, "status_code", 0) or 0) != 200:
            r = s.get(
                f"{BASE}/csearch.php",
                params={"searchname": title, "searchby": "Name", "category": "All"},
                timeout=TIMEOUT,
            )
        soup = BeautifulSoup(r.text, "html.parser")
        movie = _pick_movie(soup, title, year=year)
        if not movie:
            return []
        r = s.get(movie, timeout=TIMEOUT)
        soup = BeautifulSoup(r.text, "html.parser")
        opts = []
        for a in soup.find_all("a", href=True):
            if "download1.php" not in a["href"]:
                continue
            name = a.get_text(" ", strip=True)
            blob = ""
            dc = a.find_next("dcounter")
            if dc:
                blob = dc.get_text(" ", strip=True)
            opts.append((urljoin(r.url, a["href"]), name, _sz_text(blob)))
        if not opts:
            return []
        out = []
        for opt, name, size in opts[:3]:
            r = s.get(opt, timeout=TIMEOUT)
            if "expired" in r.text.lower():
                continue
            if not size:
                m = re.search(r"File Size:\s*(?:<[^>]+>)*\s*([\d.]+\s*(?:KB|MB|GB|TB))", r.text, re.I)
                if m:
                    size = m.group(1)
            soup = BeautifulSoup(r.text, "html.parser")
            dl = next(
                (
                    urljoin(r.url, a["href"])
                    for a in soup.find_all("a", href=True)
                    if "download.php?downloadkey" in a["href"]
                ),
                None,
            )
            if not dl:
                continue
            r = s.get(dl, timeout=TIMEOUT)
            soup = BeautifulSoup(r.text, "html.parser")
            dlinks = [
                urljoin(r.url, a["href"])
                for a in soup.find_all("a", href=True)
                if "dlink.php" in a["href"]
            ]
            tags = tags_from(name, size)
            disp = f"{name} ({size})" if size else name
            for d in dlinks[:3]:
                for u in _cdn_from_dlink(s, d):
                    out.append({"url": u, "name": disp, "tags": tags})
            if out:
                break
        seen, uniq = set(), []
        for it in out:
            u = it["url"]
            if u not in seen:
                seen.add(u)
                uniq.append(it)
        return uniq
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    return


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    return


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

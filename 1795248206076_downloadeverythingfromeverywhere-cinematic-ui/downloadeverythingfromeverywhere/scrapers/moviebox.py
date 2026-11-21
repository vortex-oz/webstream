"""MovieBox / aoneroom H5 + Android BFF → hakunaymatata CDN links."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from urllib.parse import urlencode, urlparse

from scrapers import _http as requests
from scrapers._tags import format_size

H5_BASES = [
    "https://h5-api.aoneroom.com/wefeed-h5api-bff",
    "https://h5.aoneroom.com/wefeed-h5-bff",
    "https://h5api.moviebox.ng/wefeed-h5api-bff",
]
ORIGINS = [
    "https://videodownloader.site",
    "https://fmoviesunblocked.net",
    "https://moviebox.ph",
    "https://www.moviebox.ph",
    "https://moviebox.pk",
    "https://moviebox.id",
    "https://moviebox.ng",
    "https://moviebox.gd",
    "https://moviebox.pe",
    "https://lok-lok.cc",
    "https://www.movieboxpro.app",
    "https://y2moviebox.com",
    "https://mb.aoneroom.com",
    "https://h5.aoneroom.com",
]
ANDROID = [
    "https://api.inmoviebox.com",
    "https://api6.aoneroom.com",
    "https://api5.aoneroom.com",
    "https://api4.aoneroom.com",
    "https://api3.aoneroom.com",
    "https://api-sin.aoneroom.com",
    "https://api.moviebox.ph",
    "https://api.moviebox.ng",
    "https://i-api.aoneroom.com",
    "https://mb-api.aoneroom.com",
]
CDN = re.compile(r"hakunaymatata\.com", re.I)
DUB = re.compile(r"\[[^\]]+\]")
SEASON_SUFFIX = re.compile(r"\s+S\d+\b", re.I)
SECRET = base64.b64decode("76iRl07s0xSN9jqmEWAt79EBJZulIQIsV64FZr2O")
APPID = "4U01pxRu278GqCZKY9"
GUEST = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJ1aWQiOjcwNjU5NDg0MTAyMTM4MTYyMzIsInV0cCI6MSwiZXhwIjoxNzkxNzMyMjMzLCJpYXQiOjE3ODM5NTU5MzN9."
    "7iyEzTj4vWAbOF0oXwNnZ0p3Nc1QaO6K9eMiGFyVfGs"
)
H5_XCI = '{"timezone":"Africa/Nairobi"}'
AND_XCI = (
    '{"timezone":"Asia/Kolkata","package_name":"com.community.mbox.in",'
    '"os":"android","region":"IN","version_name":"3.0.16.0804.03"}'
)
TIMEOUT = 12
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )
}


def _md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _client_token() -> str:
    ts = str(int(time.time() * 1000))
    return f"{ts},{_md5(ts[::-1])}"


def _tr_sig(method: str, url: str, body: str, ts: int) -> str:
    u = urlparse(url)
    q = sorted([p.split("=", 1) for p in (u.query.split("&") if u.query else []) if p])
    resource = f"{u.path}?{'&'.join(f'{k}={v}' for k, v in q)}" if q else u.path
    canon = "\n".join(
        [
            method.upper(),
            "application/json",
            "application/json;charset=UTF-8",
            str(len(body)) if body else "",
            str(ts),
            _md5(body[:0x19000]) if body else "",
            resource,
        ]
    )
    sig = base64.b64encode(hmac.new(SECRET, canon.encode(), hashlib.md5).digest()).decode()
    return f"{ts}|2|{sig}"


def _base_title(t: str) -> str:
    return _norm(DUB.sub("", SEASON_SUFFIX.sub("", str(t or ""))))


def _pick(items, title, year=None, want_type=None):
    wt = _norm(title)
    scored = []
    for it in items or []:
        if want_type is not None and int(it.get("subjectType") or 0) != want_type:
            continue
        t = str(it.get("title") or "")
        nt = _base_title(t)
        if wt not in nt and wt not in _norm(t):
            continue
        score = 0
        if nt == wt:
            score += 5
        elif nt.startswith(wt + " "):
            score += 3
        if year is not None and str(it.get("releaseDate") or "").startswith(str(year)):
            score += 4
        if not DUB.search(t):
            score += 2
        if it.get("hasResource"):
            score += 1
        if it.get("detailPath"):
            score += 1
        if wt == "avatar" and re.search(r"\b(way|fire|airbender|aang)\b", nt):
            score -= 10
        scored.append((score, it))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored and scored[0][0] > 0 else None


def _detail_path(item) -> str:
    if item.get("detailPath"):
        return item["detailPath"]
    u = str(item.get("detailUrl") or "")
    m = re.search(r"/detail/([^/?#]+)", u)
    return m.group(1) if m else ""


def _h5_session(origin: str, h5: str = None) -> str:
    base = h5 or H5_BASES[0]
    r = requests.get(
        f"{base}/app/get-latest-app-pkgs",
        params={"app_name": "moviebox"},
        headers={"Accept": "application/json", "X-Client-Info": H5_XCI, "Referer": f"{origin}/", **UA},
        timeout=TIMEOUT,
    )
    xu = r.headers.get("x-user")
    if not xu:
        raise RuntimeError("no token")
    token = json.loads(xu).get("token")
    if not token:
        raise RuntimeError("no token")
    return token


def _h5_headers(token: str, origin: str, detail_path: str = "", subject_id=None) -> dict:
    referer = (
        f"{origin}/spa/videoPlayPage/movies/{detail_path}?id={subject_id}&type=/movie/detail"
        if detail_path
        else f"{origin}/"
    )
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "X-Client-Info": H5_XCI,
        "Origin": origin,
        "Referer": referer,
        **UA,
    }


def _h5_search(token: str, origin: str, keyword: str, subject_type: int, h5: str = None):
    base = h5 or H5_BASES[0]
    r = requests.post(
        f"{base}/subject/search",
        headers={**_h5_headers(token, origin), "Content-Type": "application/json"},
        data=json.dumps({"keyword": keyword, "page": 1, "perPage": 24, "subjectType": subject_type}),
        timeout=TIMEOUT,
    )
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(j.get("message") or r.status_code)
    return (j.get("data") or {}).get("items") or []


def _h5_download(token: str, origin: str, subject_id, detail_path: str, se: int, ep: int, h5: str = None):
    base = h5 or H5_BASES[0]
    qs = urlencode(
        {"subjectId": str(subject_id), "detailPath": detail_path or "", "se": str(se), "ep": str(ep)}
    )
    r = requests.get(
        f"{base}/subject/download?{qs}",
        headers=_h5_headers(token, origin, detail_path, subject_id),
        timeout=TIMEOUT,
    )
    return (r.json() or {}).get("data") or {}


def _from_downloads(dls, content_type: str, *labels):
    out, seen = [], set()
    for d in dls or []:
        url = d.get("url") if isinstance(d, dict) else None
        if not url or d.get("vipLocked") or not CDN.search(url) or url in seen:
            continue
        seen.add(url)
        res = d.get("resolution")
        name_parts = [p for p in labels if p]
        if res:
            name_parts.append(f"{res}p")
        codec = d.get("codecName") or ""
        tags = [content_type]
        st = format_size(d.get("size"))
        if st:
            tags.append(st)
        if res:
            tags.append(f"{res}p")
        if re.search(r"h265|hevc", str(codec) + url, re.I):
            tags.append("x265")
        elif re.search(r"h264|avc", str(codec) + url, re.I):
            tags.append("x264")
        name = " ".join(str(x) for x in name_parts if x) or "MovieBox"
        out.append({"url": url, "name": name, "tags": list(dict.fromkeys(tags))})
    return out


def _h5_pairs():
    for origin in ORIGINS:
        for h5 in H5_BASES:
            yield h5, origin


def _find_h5(title, year, subject_type):
    last = None
    for h5, origin in _h5_pairs():
        try:
            token = _h5_session(origin, h5)
            item = _pick(_h5_search(token, origin, title, subject_type, h5), title, year, subject_type)
            if not item or not item.get("subjectId"):
                continue
            return {
                "token": token,
                "origin": origin,
                "h5": h5,
                "item": item,
                "detailPath": _detail_path(item),
            }
        except Exception as e:
            last = e
    if last:
        raise last
    return None


def _h5_movie_downloads(title, year):
    last = None
    merged = []
    for h5, origin in _h5_pairs():
        try:
            token = _h5_session(origin, h5)
            item = _pick(_h5_search(token, origin, title, 1, h5), title, year, 1)
            if not item or not item.get("subjectId"):
                continue
            detail = _detail_path(item)
            data = _h5_download(token, origin, item["subjectId"], detail, 0, 0, h5)
            links = _from_downloads(data.get("downloads") or [], "Movie", item.get("title"))
            if links:
                merged = _merge(merged, links)
                # one working H5 unlock is enough; keep going across android edges separately
                break
        except Exception as e:
            last = e
    if merged:
        return merged
    if last:
        raise last
    return []


def _android_req(base: str, method: str, path: str, params=None, body=None, bearer=None):
    host = urlparse(base).hostname or ""
    qs = {**(params or {}), "host": host}
    sorted_qs = urlencode(sorted(qs.items()))
    url = f"{base}{path}?{sorted_qs}"
    body_str = json.dumps(body) if body is not None else ""
    ts = int(time.time() * 1000)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": "MovieBoxPro/16.2.1 (Android 14; com.community.mbox.in)",
        "appid": APPID,
        "region": "IN",
        "lang": "en",
        "os": "android",
        "X-Sign-Version": "2.0",
        "X-Timestamp": str(ts),
        "X-Client-Info": AND_XCI,
        "x-tr-signature": _tr_sig(method, url, body_str, ts),
    }
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
        headers["X-Client-Status"] = "0"
    else:
        headers["Authorization"] = f"Bearer {GUEST}"
        headers["X-Client-Token"] = _client_token()
        headers["X-Client-Status"] = "0"
    s = requests.Session()
    r = s.request(method, url, headers=headers, data=body_str or None, timeout=TIMEOUT)
    next_bearer = bearer
    xu = r.headers.get("x-user")
    if xu:
        try:
            next_bearer = json.loads(xu).get("token") or next_bearer
        except Exception:
            pass
    try:
        j = r.json()
    except Exception:
        j = {}
    return j, next_bearer


def _detectors_to_downloads(data, se=None, ep=None):
    out = []
    for d in (data or {}).get("resourceDetectors") or []:
        for r in d.get("resolutionList") or []:
            url = r.get("resourceLink")
            if not url or not CDN.search(url):
                continue
            if se is not None and ep is not None:
                if int(r.get("se") or 0) != int(se) or int(r.get("ep") or 0) != int(ep):
                    continue
            elif r.get("se") or r.get("ep"):
                continue
            out.append(
                {
                    "url": url,
                    "resolution": r.get("resolution"),
                    "codecName": r.get("codecName"),
                    "vipLocked": int(r.get("requireMemberType") or 0) > 0,
                    "size": r.get("size") or r.get("fileSize") or r.get("fileSizeInByte"),
                }
            )
        if (se is None or se == 0) and d.get("downloadUrl") and CDN.search(d["downloadUrl"]):
            out.append(
                {
                    "url": d["downloadUrl"],
                    "resolution": d.get("resolution"),
                    "codecName": d.get("codecName"),
                    "size": d.get("size") or d.get("fileSize") or d.get("fileSizeInByte"),
                }
            )
    return out


def _android_downloads(title, year, subject_type, se=None, ep=None):
    out = []
    bearer = None
    subject_id = None
    for base in ANDROID:
        try:
            if not subject_id:
                j, bearer = _android_req(
                    base,
                    "POST",
                    "/wefeed-mobile-bff/subject-api/search",
                    body={"keyword": title, "page": 1, "pageSize": 24},
                    bearer=bearer,
                )
                item = _pick((j.get("data") or {}).get("items") or [], title, year, subject_type)
                if not item or not item.get("subjectId"):
                    return out
                subject_id = item["subjectId"]
            j, bearer = _android_req(
                base,
                "GET",
                "/wefeed-mobile-bff/subject-api/get",
                params={"subjectId": str(subject_id)},
                bearer=bearer,
            )
            out.extend(_detectors_to_downloads(j.get("data"), se, ep))
        except Exception:
            continue
    return out


def _merge(*lists):
    seen, out = set(), []
    for lst in lists:
        for it in lst or []:
            u = it.get("url") if isinstance(it, dict) else it
            if not u or u in seen:
                continue
            seen.add(u)
            out.append(it if isinstance(it, dict) else {"url": u})
    return out


def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    try:
        h5, and_ = [], []
        try:
            h5 = _h5_movie_downloads(title, year)
        except Exception:
            pass
        try:
            and_ = _from_downloads(_android_downloads(title, year, 1), "Movie", title)
        except Exception:
            pass
        return _merge(and_, h5)
    except Exception:
        return []


def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    # MovieBox only exposes per-episode downloads, not season packs.
    return


def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    try:
        h5, and_ = [], []
        try:
            hit = _find_h5(title, year, 2)
            if hit and season is not None and episode is not None:
                data = _h5_download(
                    hit["token"],
                    hit["origin"],
                    hit["item"]["subjectId"],
                    hit["detailPath"],
                    int(season),
                    int(episode),
                    hit.get("h5"),
                )
                h5 = _from_downloads(
                    data.get("downloads") or [],
                    "Episode",
                    hit["item"].get("title"),
                    f"S{int(season)}E{int(episode)}",
                )
        except Exception:
            pass
        try:
            and_ = _from_downloads(
                _android_downloads(title, year, 2, season, episode),
                "Episode",
                title,
                f"S{int(season)}E{int(episode)}",
            )
        except Exception:
            pass
        return _merge(and_, h5)
    except Exception:
        return []

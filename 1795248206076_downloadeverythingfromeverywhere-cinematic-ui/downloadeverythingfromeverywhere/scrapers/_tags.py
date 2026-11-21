"""Shared tag / name helpers for Python scrapers."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse, parse_qs

TAG_RULES = [
    (re.compile(r"\b(2160p+|4k|uhd)\b|\b\d{3,4}\s*[x×]\s*2160\b", re.I), "2160p"),
    (re.compile(r"\b1080p+\b|\b\d{3,4}\s*[x×]\s*1080\b", re.I), "1080p"),
    (re.compile(r"\b720p+\b|\b720\s*hc\b|\b720hc\b|\b\d{3,4}\s*[x×]\s*720\b", re.I), "720p"),
    (re.compile(r"\b540p+\b|\b\d{3,4}\s*[x×]\s*540\b", re.I), "540p"),
    (re.compile(r"\b480p+\b|\b480\s*hc\b|\b\d{3,4}\s*[x×]\s*480\b", re.I), "480p"),
    (re.compile(r"\b400p+\b|\b\d{3,4}\s*[x×]\s*400\b", re.I), "400p"),
    (re.compile(r"\b360p+\b|\b\d{3,4}\s*[x×]\s*360\b", re.I), "360p"),
    (re.compile(r"\bremux\b", re.I), "REMUX"),
    (re.compile(r"\bbluray|blu[-\s]?ray|bdrip|brrip\b", re.I), "BluRay"),
    (re.compile(r"\bweb[-\s]?dl\b", re.I), "WEB-DL"),
    (re.compile(r"\bwebrip\b", re.I), "WEBRip"),
    (re.compile(r"\bhdtv\b", re.I), "HDTV"),
    (re.compile(r"\bhdrip\b", re.I), "HDRip"),
    (re.compile(r"\b(x265|h\.?265|hevc)\b", re.I), "x265"),
    (re.compile(r"\b(x264|h\.?264|avc)\b", re.I), "x264"),
    (re.compile(r"\b10\s*-?\s*bit\b", re.I), "10bit"),
    (re.compile(r"\bhdr10?\+?\b", re.I), "HDR"),
    (re.compile(r"\bdolby\.?\s*vision|\bdv\b", re.I), "DV"),
    (re.compile(r"\batmos\b", re.I), "Atmos"),
    (re.compile(r"\bddp?5\.?1|truehd|dts\b", re.I), "5.1"),
    (re.compile(r"\bdual(?:[_\s-]*audio)?\b", re.I), "Dual"),
    (re.compile(r"\bmulti(?:[_\s-]*audio)?\b", re.I), "Multi"),
    (re.compile(r"\bhindi\b", re.I), "Hindi"),
    (re.compile(r"\benglish\b", re.I), "English"),
    (re.compile(r"\bindonesian\b|\bsubtitle\s+indonesia\b|\bsub(?:title)?\s*indo(?:nesia)?\b", re.I), "Indonesian"),
    (re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(KB|MB|GB|TB|KiB|MiB|GiB|TiB)\b", re.I), None),
]

QUALITY = {"2160p", "1080p", "720p", "540p", "480p", "400p", "360p"}
HOST_JUNK = re.compile(
    r"\b(?:hubcloud|hubdrive|gdflix|gdlink|filebee|v-?cloud|nexdrive|filepress|"
    r"g-?drive|g-?direct|pixeldrain|gofile|mega(?:up)?)\b",
    re.I,
)


def _size_tag(num: str, unit: str) -> str:
    n = num.replace(",", ".")
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return f"{n}{unit.upper().replace('IB', 'B')}"


def format_size(n: int | float) -> str | None:
    try:
        n = float(n)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    units = ("B", "KB", "MB", "GB", "TB")
    i = 0
    while n >= 1024 and i < 4:
        n /= 1024
        i += 1
    if i == 0:
        n /= 1024
        i = 1
    if n >= 100:
        s = str(int(round(n)))
    else:
        n = round(n, 1)
        s = str(int(n)) if n == int(n) else str(n)
    return f"{s}{units[i]}"


def tags_from(*parts: str) -> list[str]:
    blob = " ".join(str(p) for p in parts if p)
    if not blob.strip():
        return []
    tags, seen, quals = [], set(), []
    for pat, tag in TAG_RULES:
        if tag is None:
            for m in pat.finditer(blob):
                t = _size_tag(m.group(1), m.group(2))
                if t not in seen:
                    seen.add(t)
                    tags.append(t)
            continue
        if tag in seen or not pat.search(blob):
            continue
        seen.add(tag)
        if tag in QUALITY:
            quals.append(tag)
        else:
            tags.append(tag)
    if len(quals) == 1:
        tags.insert(0, quals[0])
    return tags


def name_from_url(url: str) -> str:
    try:
        u = urlparse(url)
        cands = []
        base = unquote(u.path).rstrip("/").split("/")[-1]
        if base:
            cands.append(base.replace("+", " "))
        qs = parse_qs(u.query)
        for key in ("id", "name", "file", "filename", "title", "fn", "n"):
            for v in qs.get(key) or []:
                cands.append(unquote(v).replace("+", " "))
        for s in cands:
            t = s.strip()
            if not t or len(t) < 4:
                continue
            if re.fullmatch(r"[A-Za-z0-9_-]{6,}", t) and not re.search(r"\d{3,4}p|S\d{2}E\d{2}|\.", t, re.I):
                continue
            if re.search(r"\.(mkv|mp4|avi|zip|rar|html)(\?|$)", t, re.I) or re.search(
                r"\d{3,4}p|S\d{1,2}E\d{1,3}", t, re.I
            ):
                return t
        for s in cands:
            if s.strip():
                return s.strip()
    except Exception:
        pass
    return ""


def clean_name(s: str) -> str:
    t = re.sub(r"\s+", " ", str(s or "")).strip()
    if re.search(r"\.(mkv|mp4|avi|iso|m4v|m2ts|ts|zip|rar)(?:\s*\[|$)", t, re.I) and len(t) < 400:
        return t
    m = re.search(
        r"([A-Za-z0-9][A-Za-z0-9._()\[\]+'’\s,~&%#@!;–—-]{8,}\.(?:mkv|mp4|avi|iso|zip|rar))",
        t,
        re.I,
    )
    if m:
        t = m.group(1)
    t = re.sub(r"\.html?$", "", t, flags=re.I)
    t = HOST_JUNK.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip(" -–—|")
    return t


def item(url: str, name: str = "", *extra_parts: str) -> dict:
    nm = clean_name(name) or name_from_url(url) or clean_name(" ".join(extra_parts))
    tags = tags_from(nm, name, *extra_parts, url)
    return {"url": url, "name": nm or "download", "tags": tags}

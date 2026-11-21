# Scraper contract (for agent writers)

Each site = one file: `scrapers/<slug>.py`

## Required API

```python
def dlmovie(title, year=None, tmdb_id=None, imdb_id=None):
    """Return list of download URL strings, or bare return if movies unsupported."""

def dlseries(title, season, year=None, tmdb_id=None, imdb_id=None):
    """Return list of download URL strings for a whole season pack, or bare return if unsupported."""

def dlseriesepisode(title, season, episode, year=None, tmdb_id=None, imdb_id=None):
    """Return list of download URL strings for one episode, or bare return if unsupported."""
```

- Prefer returning `list[str]` of http(s) download / host / intermediate links found.
- On failure / not found: return `[]`.
- Unsupported capability: bare `return` (None).
- Minimal comments. Only comment complex logic.
- If site needs captcha / Turnstile / rate-limit / forced signup / login / is broken: first line of file must be exactly:
  `# WARNING: <short reason>`
- Use `requests` + `bs4`. Optionally `cloudscraper` for Cloudflare. No other deps.
- UA header: Mozilla/5.0 Chrome-like.
- Timeouts ~15–25s. Swallow exceptions → `[]`.
- Do not write exploits. Do not invent captcha tokens.

## `__main__` (every file)

Load sibling JSONs and print:

```python
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
```

## Test titles

- Movie: Avatar (2009) — tmdb 19995 — imdb tt0499549
- Series S1: Breaking Bad (2008) — tmdb 1396 — imdb tt0903747
- Episode: Breaking Bad S01E05 "Gray Matter"

## Capability rules (from sites.txt)

- Movies-only → `dlseries` / `dlseriesepisode` bare `return`
- TV-only → `dlmovie` bare `return`
- Season packs only (no per-episode) → `dlseriesepisode` bare `return`
- Per-episode only (no season pack) → `dlseries` bare `return`
- Both → implement both TV functions when possible

Implement real HTTP scraping following the site's documented flow in sites.txt. Extract whatever download-related hrefs are available without solving captchas/Turnstile.

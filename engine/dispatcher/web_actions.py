# engine/dispatcher/web_actions.py
"""
Cross-platform web actions: Google search, Google Maps, websites, YouTube,
and Spotify Web API lookups. Used by both the macOS and Windows dispatchers.
"""

from __future__ import annotations

import base64
import itertools
import platform
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPOTIFY_KEY_PATH = PROJECT_ROOT / "spotify_key.txt"  # "client_id:client_secret"

# Spoken names that are websites rather than installed apps.
KNOWN_SITES = {
    "youtube": "https://www.youtube.com",
    "youtube music": "https://music.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "google maps": "https://www.google.com/maps",
    "maps": "https://www.google.com/maps",
    "google drive": "https://drive.google.com",
    "google docs": "https://docs.google.com",
    "netflix": "https://www.netflix.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
    "tiktok": "https://www.tiktok.com",
    "chatgpt": "https://chatgpt.com",
    "github": "https://github.com",
    "linkedin": "https://www.linkedin.com",
    "reddit": "https://www.reddit.com",
    "amazon": "https://www.amazon.com",
    "wikipedia": "https://www.wikipedia.org",
}


_BROWSER_APPS = {
    "safari": "Safari",
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "brave": "Brave Browser",
    "brave browser": "Brave Browser",
    "edge": "Microsoft Edge",
    "microsoft edge": "Microsoft Edge",
    "firefox": "Firefox",
    "arc": "Arc",
    "opera": "Opera",
}


def open_url(url: str, browser: str | None = None):
    """Open url in the default browser, or in a named one ("Safari", "Chrome") on macOS."""
    app = _BROWSER_APPS.get((browser or "").strip().lower())
    print(f"[Web] Opening {url}" + (f" in {app}" if app else ""), flush=True)
    if platform.system() == "Darwin":
        if app and subprocess.run(["open", "-a", app, url], check=False).returncode == 0:
            return
        subprocess.run(["open", url], check=False)
    else:
        webbrowser.open(url, new=2)


def site_for(name: str) -> str | None:
    return KNOWN_SITES.get((name or "").strip().lower())


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return "https://www.google.com"
    if "://" not in url:
        url = "https://" + url
    return url


def web_search(query: str, browser: str | None = None):
    open_url("https://www.google.com/search?q=" + urllib.parse.quote_plus(query), browser)


def maps_search(query: str):
    open_url("https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote_plus(query))


#  YouTube

def youtube_search(query: str, newest_first: bool = False):
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(query)
    if newest_first:
        url += "&sp=CAI%253D"  # YouTube's "sort by upload date" filter
    open_url(url)


def _ydl():
    import yt_dlp

    return yt_dlp.YoutubeDL({
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "playlistend": 1,
        "socket_timeout": 5,
    })


def _first_entry(info):
    return next(itertools.islice(info.get("entries") or [], 1), None)


def find_youtube_video(query: str, latest: bool = False) -> tuple[str, str] | None:
    """
    Returns (video_id, title).
    latest=False: the top search result for the query.
    latest=True:  the newest upload from the channel that best matches the query.
    """
    with _ydl() as ydl:
        if not latest:
            entry = _first_entry(ydl.extract_info(f"ytsearch1:{query}", download=False))
            return (entry["id"], entry.get("title") or "") if entry else None

        channels_url = (
            "https://www.youtube.com/results?search_query="
            + urllib.parse.quote_plus(query)
            + "&sp=EgIQAg%253D%253D"  # "Channels" filter
        )
        channel = _first_entry(ydl.extract_info(channels_url, download=False, process=False))
        if not channel or not channel.get("url"):
            return None
        uploads = ydl.extract_info(channel["url"].rstrip("/") + "/videos", download=False, process=False)
        video = _first_entry(uploads)
        return (video["id"], video.get("title") or "") if video else None


def youtube_play(query: str, latest: bool = False, time_budget: float = 7.0) -> bool:
    """Open the best matching video so it starts playing. Returns False on fallback."""
    t0 = time.time()
    result: dict = {}

    def lookup():
        try:
            result["found"] = find_youtube_video(query, latest=latest)
        except Exception as e:
            print(f"[YouTube] Lookup failed: {e}", flush=True)

    worker = threading.Thread(target=lookup, daemon=True)
    worker.start()
    worker.join(time_budget)
    if worker.is_alive():
        print(f"[YouTube] Lookup took over {time_budget:.0f}s; opening search results.", flush=True)
    found = result.get("found")

    if found:
        video_id, title = found
        print(f"[YouTube] Found {title!r} in {time.time() - t0:.1f}s", flush=True)
        open_url(f"https://www.youtube.com/watch?v={video_id}")
        return True

    youtube_search(query, newest_first=latest)
    return False


#  Spotify Web API (optional: needs spotify_key.txt)

_spotify_token: tuple[str, float] | None = None


def spotify_api_available() -> bool:
    return SPOTIFY_KEY_PATH.exists()


def _spotify_access_token() -> str | None:
    global _spotify_token
    if _spotify_token and _spotify_token[1] > time.time() + 30:
        return _spotify_token[0]
    try:
        client_id, client_secret = SPOTIFY_KEY_PATH.read_text(encoding="utf-8").strip().split(":", 1)
    except Exception:
        print(f"[Spotify] {SPOTIFY_KEY_PATH.name} should contain client_id:client_secret", flush=True)
        return None

    auth = base64.b64encode(f"{client_id.strip()}:{client_secret.strip()}".encode()).decode()
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {auth}"},
        data={"grant_type": "client_credentials"},
        timeout=5,
    )
    if not resp.ok:
        print(f"[Spotify] Token request failed: {resp.status_code} {resp.text[:200]}", flush=True)
        return None
    data = resp.json()
    _spotify_token = (data["access_token"], time.time() + float(data.get("expires_in", 3600)))
    return _spotify_token[0]


def spotify_find_uri(query: str, kind: str = "track") -> tuple[str, str] | None:
    """Returns (spotify_uri, name) for the best match, or None."""
    kind = kind if kind in ("artist", "track", "album", "playlist") else "track"
    token = _spotify_access_token()
    if not token:
        return None
    resp = requests.get(
        "https://api.spotify.com/v1/search",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": query, "type": kind, "limit": 1},
        timeout=5,
    )
    if not resp.ok:
        print(f"[Spotify] Search failed: {resp.status_code} {resp.text[:200]}", flush=True)
        return None
    items = (resp.json().get(f"{kind}s") or {}).get("items") or []
    items = [i for i in items if i]
    if not items:
        return None
    return items[0]["uri"], items[0].get("name", query)

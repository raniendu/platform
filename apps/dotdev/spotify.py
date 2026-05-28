"""spotify.py - Spotify API utility for personal website.

Fetches the user's top played tracks in the last month (short_term)
using the standard library urllib. Implements a thread-safe in-memory cache
and a high-fidelity curated fallback system.
"""

import base64
import json
import os
import threading
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

# Thread-safe lock for cache access
_lock = threading.Lock()

# 15 minutes cache duration
CACHE_DURATION = 900

_cache: Dict[str, Any] = {
    "tracks": None,
    "expires_at": 0,
}


def fetch_access_token(
    client_id: str, client_secret: str, refresh_token: str
) -> Optional[str]:
    """Exchanges a Spotify refresh token for a new short-lived access token."""
    url = "https://accounts.spotify.com/api/token"
    auth_str = f"{client_id}:{client_secret}"
    auth_header = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")

    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data.get("access_token")
    except Exception as e:
        print(f"Error fetching Spotify access token: {e}")
        return None


def fetch_top_tracks(
    access_token: str, limit: int = 5
) -> Optional[List[Dict[str, Any]]]:
    """Queries Spotify Web API for the user's top played tracks in the last ~4 weeks."""
    url = (
        f"https://api.spotify.com/v1/me/top/tracks?time_range=short_term&limit={limit}"
    )
    headers = {
        "Authorization": f"Bearer {access_token}",
    }
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            items = res_data.get("items", [])
            tracks = []
            for item in items:
                # Format artists as comma-separated string
                artists = ", ".join(
                    [artist["name"] for artist in item.get("artists", [])]
                )
                album_images = item.get("album", {}).get("images", [])
                image_url = album_images[0]["url"] if album_images else ""
                tracks.append(
                    {
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "artists": artists,
                        "album": item.get("album", {}).get("name"),
                        "image_url": image_url,
                        "spotify_url": item.get("external_urls", {}).get("spotify"),
                        "preview_url": item.get("preview_url"),
                    }
                )
            return tracks
    except Exception as e:
        print(f"Error fetching Spotify top tracks: {e}")
        return None


def get_fallback_tracks() -> List[Dict[str, Any]]:
    """Returns a curated list of high-quality fallback tracks when API is unavailable."""
    return [
        {
            "id": "25S46Jz6iF7960m780uIRg",
            "name": "Intro",
            "artists": "The xx",
            "album": "xx",
            "image_url": "https://i.scdn.co/image/ab67616d0000b273a5a73e6af2b71a06cf8a27d2",
            "spotify_url": "https://open.spotify.com/track/25S46Jz6iF7960m780uIRg",
            "preview_url": "https://p.scdn.co/mp3-preview/a9ed0d8a6b1df30e84b80b2a3fa9d8b746fa01c3?cid=774b29d4f1384e14be87d54269e00d8a",
        },
        {
            "id": "0bV628469UgNgu1945uWlS",
            "name": "Strobe",
            "artists": "deadmau5",
            "album": "For Lack of a Better Name",
            "image_url": "https://i.scdn.co/image/ab67616d0000b273b0a21fb6621f37e6d24a0d92",
            "spotify_url": "https://open.spotify.com/track/0bV628469UgNgu1945uWlS",
            "preview_url": "https://p.scdn.co/mp3-preview/f4a0a4c0eb9d8ff7227d853e34b92bcf74291880?cid=774b29d4f1384e14be87d54269e00d8a",
        },
        {
            "id": "1eyzsl2IU4uzv6uJZ2ZFyv",
            "name": "Midnight City",
            "artists": "M83",
            "album": "Hurry Up, We're Dreaming",
            "image_url": "https://i.scdn.co/image/ab67616d0000b273e925345759efc9913165b40f",
            "spotify_url": "https://open.spotify.com/track/1eyzsl2IU4uzv6uJZ2ZFyv",
            "preview_url": "https://p.scdn.co/mp3-preview/3e1a8cf822ebff1129f12d8a5712e6cc462f4838?cid=774b29d4f1384e14be87d54269e00d8a",
        },
        {
            "id": "2ctvdKmETyJ22K5C246ggB",
            "name": "Breathe (In the Air)",
            "artists": "Pink Floyd",
            "album": "The Dark Side of the Moon",
            "image_url": "https://i.scdn.co/image/ab67616d0000b273ea7ca1500a7894aefe029ea9",
            "spotify_url": "https://open.spotify.com/track/2ctvdKmETyJ22K5C246ggB",
            "preview_url": None,
        },
        {
            "id": "5Nn2Dj7OStGL6uK9Hgpt7g",
            "name": "Ghostwriter",
            "artists": "RJD2",
            "album": "Deadringer",
            "image_url": "https://i.scdn.co/image/ab67616d0000b27376e107df0df0df4ea20f8c7d",
            "spotify_url": "https://open.spotify.com/track/5Nn2Dj7OStGL6uK9Hgpt7g",
            "preview_url": "https://p.scdn.co/mp3-preview/2b9ed3cb1624c96570d8a9e6d0347895ee9adcb9?cid=774b29d4f1384e14be87d54269e00d8a",
        },
    ]


def get_spotify_tracks() -> List[Dict[str, Any]]:
    """Returns the list of Spotify tracks, reading from cache, API, or fallback."""
    global _cache
    now = time.time()

    # Thread-safe read from cache
    with _lock:
        if _cache["tracks"] is not None and _cache["expires_at"] > now:
            return _cache["tracks"]

    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN")

    if client_id and client_secret and refresh_token:
        # Clean credentials if they contain inline comments
        client_id = client_id.split("#")[0].strip()
        client_secret = client_secret.split("#")[0].strip()
        refresh_token = refresh_token.split("#")[0].strip()

        access_token = fetch_access_token(client_id, client_secret, refresh_token)
        if access_token:
            tracks = fetch_top_tracks(access_token)
            if tracks:
                with _lock:
                    _cache["tracks"] = tracks
                    _cache["expires_at"] = now + CACHE_DURATION
                return tracks

    return get_fallback_tracks()

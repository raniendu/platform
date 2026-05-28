import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import spotify
from app import app


@pytest.fixture()
def client():
    app.config.update({"TESTING": True})
    with app.test_client() as client:
        yield client


def test_about_page_renders_with_fallback(client):
    """Verifies that the about page renders successfully with fallback tracks when no env vars exist."""
    # Ensure no environment variables interfere
    with patch.dict("os.environ", {}, clear=True):
        # Clear cache to force fallback evaluation
        with patch("spotify._cache", {"tracks": None, "expires_at": 0}):
            response = client.get("/about")
            assert response.status_code == 200
            assert b'id="spotify-widget-heading"' in response.data
            assert b"On Repeat" in response.data
            assert b"The xx" in response.data
            assert b"Intro" in response.data
            assert b"deadmau5" in response.data
            assert b"Strobe" in response.data


def test_about_page_renders_with_mocked_tracks(client):
    """Verifies that the about page renders dynamic track lists supplied by the spotify module."""
    mock_tracks = [
        {
            "id": "mock1",
            "name": "Mock Song One",
            "artists": "Mock Artist",
            "album": "Mock Album",
            "image_url": "https://example.com/mock.jpg",
            "spotify_url": "https://open.spotify.com/track/mock1",
            "preview_url": "https://example.com/mock.mp3",
        }
    ]

    with patch("spotify.get_spotify_tracks", return_value=mock_tracks):
        with patch.dict(
            "os.environ", {"SPOTIFY_PROFILE_URL": "https://spotify.com/user/raniendu"}
        ):
            response = client.get("/about")
            assert response.status_code == 200
            assert b"Mock Song One" in response.data
            assert b"Mock Artist" in response.data
            assert b"https://spotify.com/user/raniendu" in response.data
            assert b"spotify-profile-link" in response.data


def test_spotify_token_exchange_failure_graceful():
    """Asserts that token exchange failures return None instead of raising exceptions."""
    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        token = spotify.fetch_access_token("mock_id", "mock_secret", "mock_refresh")
        assert token is None


def test_spotify_top_tracks_failure_graceful():
    """Asserts that top tracks endpoint errors return None instead of raising exceptions."""
    with patch(
        "urllib.request.urlopen", side_effect=Exception("HTTP 401 Unauthorized")
    ):
        tracks = spotify.fetch_top_tracks("mock_access_token")
        assert tracks is None

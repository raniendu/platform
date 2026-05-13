import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app


@pytest.fixture()
def client():
    app.config.update({"TESTING": True})
    with app.test_client() as client:
        yield client


def test_healthz_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_posts_api_returns_sorted_posts(client):
    response = client.get("/api/posts")
    assert response.status_code == 200
    data = response.get_json()

    posts = data["posts"]
    assert posts, "Expected at least one post in the API payload"

    dates = [post["date"] for post in posts]
    assert dates == sorted(dates, reverse=True), "Posts should be sorted newest first"

    first_post = posts[0]
    assert "tags" in first_post and isinstance(first_post["tags"], list)
    assert data["archive"], "Archive index should not be empty"
    assert data["wordCloud"], "Word cloud data should not be empty"


def test_notes_redirects_to_posts(client):
    response = client.get("/notes")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/posts")


def test_posts_page_renders(client):
    response = client.get("/posts")
    assert response.status_code == 200
    assert b'id="posts-app"' in response.data

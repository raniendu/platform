"""
app.py - Flask application for personal website.

This module defines the Flask web application serving pages such as home,
posts, travels, resume, and about (with interactive travel map).

Usage:
    flask run
or
    python app.py
"""

import datetime
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple, Union

import blog

try:  # pragma: no cover - prefer real Flask when available
    # fmt: off
    from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

    # fmt: on
except ModuleNotFoundError:  # pragma: no cover - lightweight fallback for tests

    class _Response:
        """Minimal HTTP response object used by the fallback web framework."""

        def __init__(
            self,
            data: Union[bytes, str] = b"",
            *,
            status: int = 200,
            headers: Optional[Dict[str, str]] = None,
            mimetype: str = "text/plain",
        ) -> None:
            if isinstance(data, str):
                data = data.encode("utf-8")
            self.data = data
            self.status_code = status
            self.mimetype = mimetype
            self.headers: Dict[str, str] = headers.copy() if headers else {}

        def get_json(self) -> Any:
            if "application/json" not in self.headers.get("Content-Type", ""):
                raise ValueError("Response does not contain JSON data")
            return json.loads(self.data.decode("utf-8"))

    class _HTTPException(Exception):
        """Exception carrying a response object to simulate Flask abort behaviour."""

        def __init__(self, response: _Response) -> None:
            super().__init__(response.status_code)
            self.response = response

    def abort(status_code: int) -> None:
        raise _HTTPException(_Response(status=status_code))

    def jsonify(payload: Any) -> _Response:
        data = json.dumps(payload)
        return _Response(
            data,
            status=200,
            headers={"Content-Type": "application/json"},
            mimetype="application/json",
        )

    def redirect(location: str, code: int = 302) -> _Response:
        return _Response(
            b"",
            status=code,
            headers={"Location": location},
            mimetype="text/plain",
        )

    def render_template(template_name: str, **_: Any) -> str:
        template_path = Path(__file__).resolve().parent / "templates" / template_name
        return template_path.read_text(encoding="utf-8")

    _ACTIVE_APP: Optional["Flask"] = None
    request = SimpleNamespace(url="", args={})

    class Flask:
        """Simplified stand-in for Flask used solely for unit tests."""

        def __init__(self, name: str) -> None:
            self.name = name
            self.config: Dict[str, Any] = {"TESTING": False}
            self._routes: Dict[str, Tuple[str, Any]] = {}
            self._dynamic_routes: Dict[str, Tuple[str, Any]] = {}
            global _ACTIVE_APP
            _ACTIVE_APP = self

        def route(self, rule: str, **options: Any):
            methods = tuple(options.get("methods", ("GET",)))

            def decorator(func: Any) -> Any:
                endpoint = options.get("endpoint", func.__name__)
                if "<" in rule:
                    self._dynamic_routes[rule] = (endpoint, func)
                else:
                    self._routes[rule] = (endpoint, func)
                setattr(func, "methods", methods)
                return func

            return decorator

        def context_processor(self, func: Any) -> Any:  # pragma: no cover - no-op
            return func

        def test_client(self):
            return _TestClient(self)

        def _dispatch(self, path: str) -> _Response:
            view = self._routes.get(path)
            if view is not None:
                _, func = view
                return _call_view(func)

            for rule, (_, func) in self._dynamic_routes.items():
                matched, kwargs = _match_route(rule, path)
                if matched:
                    return _call_view(func, **kwargs)

            return _Response(status=404)

        def url_for(self, endpoint: str, **values: Any) -> str:
            for rule, (ep, _) in {**self._routes, **self._dynamic_routes}.items():
                if ep == endpoint:
                    return _fill_rule(rule, values)
            raise KeyError(f"Unknown endpoint {endpoint}")

    class _TestClient:
        def __init__(self, application: Flask) -> None:
            self._app = application

        def get(self, path: str) -> _Response:
            if not path.startswith("/"):
                path = f"/{path}"
            return self._app._dispatch(path)

        def __enter__(self) -> "_TestClient":
            return self

        def __exit__(self, exc_type, exc: Any, tb: Any) -> None:
            return None

    def _call_view(func: Any, **kwargs: Any) -> _Response:
        try:
            result = func(**kwargs)
        except _HTTPException as exc:  # pragma: no cover - propagated abort
            return exc.response

        if isinstance(result, _Response):
            return result
        if isinstance(result, tuple):
            body, status = result
            return _Response(body, status=status, mimetype="text/html")
        if isinstance(result, bytes):
            return _Response(result, mimetype="text/html")
        return _Response(str(result), mimetype="text/html")

    def _match_route(rule: str, path: str) -> Tuple[bool, Dict[str, str]]:
        rule_parts = [part for part in rule.strip("/").split("/") if part]
        path_parts = [part for part in path.strip("/").split("/") if part]
        if len(rule_parts) != len(path_parts):
            return False, {}

        params: Dict[str, str] = {}
        for rule_part, path_part in zip(rule_parts, path_parts):
            if rule_part.startswith("<") and rule_part.endswith(">"):
                params[rule_part[1:-1]] = path_part
            elif rule_part != path_part:
                return False, {}
        return True, params

    def _fill_rule(rule: str, values: Dict[str, Any]) -> str:
        segments = []
        for segment in rule.split("/"):
            if segment.startswith("<") and segment.endswith(">"):
                key = segment[1:-1]
                segments.append(str(values.get(key, "")))
            else:
                segments.append(segment)
        return "/".join(segments).replace("//", "/") or "/"

    def url_for(endpoint: str, **values: Any) -> str:
        if _ACTIVE_APP is None:
            raise RuntimeError("No application instance registered")
        return _ACTIVE_APP.url_for(endpoint, **values)


app = Flask(__name__)


TRAVEL_ENTRIES = [
    {
        "slug": "isle-of-skye",
        "title": "Highland Landscapes",
        "location": "Isle of Skye, Scotland 🇬🇧",
        "date": "2025-09-01",
        "summary": "Exploring the rugged landscapes of the Highlands.",
        "photos": [
            {
                "src": "images/travels/isle_of_skye.jpeg",
                "alt": "Isle of Skye landscapes",
                "caption": "Isle of Skye, September 2025",
            },
        ],
    },
    {
        "slug": "krimchi-temples",
        "title": "Ancient Temples of Krimchi",
        "location": "Udhampur, India 🇮🇳",
        "date": "2025-03-15",
        "summary": "Visiting the ancient temple complex in the foothills.",
        "photos": [
            {
                "src": "images/travels/krimchi_temples.jpeg",
                "alt": "Krimchi Temples",
                "caption": "Krimchi Temples, March 2025",
            },
        ],
    },
    {
        "slug": "cambodia-angkor-wat",
        "title": "Angkor Wat temple complex",
        "location": "Siem Reap, Cambodia 🇰🇭",
        "date": "2022-12-21",
        "summary": "Sunrise over the ancient temple complex.",
        "photos": [
            {
                "src": "images/travels/cambodia_angkor_wat.jpeg",
                "alt": "Angkor Wat temple complex, Cambodia",
                "caption": "Angkor Wat, December 2022",
            },
        ],
    },
    {
        "slug": "lake-louise",
        "title": "Banff National Park",
        "location": "Lake Louise, Canada 🇨🇦",
        "date": "2022-07-02",
        "summary": "Turquoise waters and mountain peaks in Banff.",
        "photos": [
            {
                "src": "images/travels/lake_louise.jpeg",
                "alt": "Lake Louise",
                "caption": "Lake Louise, July 2022",
            },
        ],
    },
    {
        "slug": "mount-rainier",
        "title": "Mount Rainier National Park",
        "location": "Washington, USA 🇺🇸",
        "date": "2021-07-25",
        "summary": "Hiking the trails around the iconic volcano.",
        "photos": [
            {
                "src": "images/travels/mount_rainer.jpeg",
                "alt": "Mount Rainier",
                "caption": "Mount Rainier, July 2021",
            },
        ],
    },
    {
        "slug": "hawaii",
        "title": "Hanalei Bay",
        "location": "Kauai, Hawaii 🇺🇸",
        "date": "2020-11-30",
        "summary": "Relaxing on the beaches of Hanalei.",
        "photos": [
            {
                "src": "images/travels/hawaii.jpeg",
                "alt": "Hanalei Bay",
                "caption": "Hanalei Bay, November 2020",
            },
        ],
    },
    {
        "slug": "nice",
        "title": "French Riviera",
        "location": "Nice, France 🇫🇷",
        "date": "2015-09-10",
        "summary": "Sunny days on the French Riviera.",
        "photos": [
            {
                "src": "images/travels/nice.jpeg",
                "alt": "Nice, France",
                "caption": "Nice, September 2015",
            },
        ],
    },
]


@app.context_processor
def inject_current_year():
    """Injects the current year into all templates."""
    return {"current_year": datetime.datetime.now().year}


@app.route("/")
def home():
    """Render the home page.

    Returns:
        Response: Rendered home page template with navigation highlighting.
    """
    posts = blog.load_posts()
    latest_posts = [
        {
            "title": post.title,
            "date": post.date.date().isoformat(),
            "display_date": post.date.strftime("%b %d, %Y"),
            "tags": list(post.tags),
            "slug": post.slug,
            "excerpt": post.excerpt,
        }
        for post in posts[:4]
    ]

    travels_url = url_for("travels")
    latest_photos = []
    for entry in TRAVEL_ENTRIES:
        for photo in entry["photos"]:
            latest_photos.append(
                {
                    "src": photo["src"],
                    "alt": photo["alt"],
                    "caption": photo["caption"],
                    "href": f"{travels_url}#{entry['slug']}",
                    "location": entry["location"],
                }
            )
    latest_photos = latest_photos[:8]

    return render_template(
        "home.html",
        active_page="home",
        latest_posts=latest_posts,
        latest_photos=latest_photos,
    )


@app.route("/posts")
def posts():
    """Render the posts page powered by Markdown content."""
    bundle = blog.load_posts_bundle()
    available_tags = sorted(
        {tag for post in bundle["posts"] for tag in post.get("tags", [])}
    )
    selected_tag = request.args.get("tag")
    return render_template(
        "posts.html",
        active_page="posts",
        posts=bundle["posts"],
        available_tags=available_tags,
        selected_tag=selected_tag,
    )


@app.route("/notes")
def notes():
    """Legacy route maintained for bookmarks. Redirect to /posts."""
    return redirect(url_for("posts"), code=302)


@app.route("/api/posts")
def api_posts():
    """Expose posts bundle (content, archive index, word cloud) as JSON."""
    return jsonify(blog.load_posts_bundle())


@app.route("/api/posts/<slug>")
def api_post_detail(slug: str):
    """Return a single post by slug."""
    for post in blog.load_posts():
        if post.slug == slug:
            return jsonify(post.to_dict())
    abort(404)


@app.route("/travels")
def travels():
    """Render the travels page with an interactive travel map.

    Uses a static list of locations with pre-defined coordinates for map markers.

    Returns:
        Response: Rendered travels page template with locations.
    """
    # Static locations with coordinates (no API calls needed)
    locations = [
        # Place I am from / born
        {"name": "Jammu, India", "type": "from", "lat": 32.7266, "lng": 74.8570},
        # Places Lived
        {"name": "Sangamner, India", "type": "lived", "lat": 19.5717, "lng": 74.2097},
        {"name": "Pune, India", "type": "lived", "lat": 18.5204, "lng": 73.8567},
        {"name": "Hyderabad, India", "type": "lived", "lat": 17.3850, "lng": 78.4867},
        {
            "name": "Seattle, Washington, USA",
            "type": "lived",
            "lat": 47.6062,
            "lng": -122.3321,
        },
        {
            "name": "North Vancouver, BC, Canada",
            "type": "lived",
            "lat": 49.3163,
            "lng": -123.0693,
        },
        {
            "name": "Redmond, Washington, USA",
            "type": "lived",
            "lat": 47.6740,
            "lng": -122.1215,
        },
        # Places Visited - India
        {
            "name": "Srinagar, Jammu and Kashmir, India",
            "type": "visited",
            "lat": 34.0837,
            "lng": 74.7973,
        },
        {
            "name": "Katra, Jammu and Kashmir, India",
            "type": "visited",
            "lat": 32.9916,
            "lng": 74.9318,
        },
        {
            "name": "Amritsar, Punjab, India",
            "type": "visited",
            "lat": 31.6340,
            "lng": 74.8723,
        },
        {
            "name": "Chandigarh, India",
            "type": "visited",
            "lat": 30.7333,
            "lng": 76.7794,
        },
        {"name": "New Delhi, India", "type": "visited", "lat": 28.6139, "lng": 77.2090},
        {"name": "Jaipur, India", "type": "visited", "lat": 26.9124, "lng": 75.7873},
        {"name": "Udaipur, India", "type": "visited", "lat": 24.5854, "lng": 73.7125},
        {"name": "Jodhpur, India", "type": "visited", "lat": 26.2389, "lng": 73.0243},
        {"name": "Shimla, India", "type": "visited", "lat": 31.1048, "lng": 77.1734},
        {"name": "Mumbai, India", "type": "visited", "lat": 19.0760, "lng": 72.8777},
        {"name": "Alibaug, India", "type": "visited", "lat": 18.6414, "lng": 72.8722},
        {"name": "Lonavala, India", "type": "visited", "lat": 18.7537, "lng": 73.4068},
        {"name": "Nashik, India", "type": "visited", "lat": 19.9975, "lng": 73.7898},
        {"name": "Bengaluru, India", "type": "visited", "lat": 12.9716, "lng": 77.5946},
        {"name": "Chennai, India", "type": "visited", "lat": 13.0827, "lng": 80.2707},
        {
            "name": "Varca, Goa, India",
            "type": "visited",
            "lat": 15.2993,
            "lng": 74.1240,
        },
        {"name": "Kolkata, India", "type": "visited", "lat": 22.5726, "lng": 88.3639},
        {"name": "Guwahati, India", "type": "visited", "lat": 26.1445, "lng": 91.7362},
        {"name": "Shillong, India", "type": "visited", "lat": 25.5788, "lng": 91.8933},
        {
            "name": "Cherrapunji, India",
            "type": "visited",
            "lat": 25.3000,
            "lng": 91.7000,
        },
        {
            "name": "Aurangabad, India",
            "type": "visited",
            "lat": 19.8762,
            "lng": 75.3433,
        },
        {"name": "Ellora, India", "type": "visited", "lat": 20.0269, "lng": 75.1791},
        {"name": "Shirdi, India", "type": "visited", "lat": 19.7645, "lng": 74.4769},
        {"name": "Patnitop, India", "type": "visited", "lat": 33.0742, "lng": 75.3312},
        {"name": "Gulmarg, India", "type": "visited", "lat": 34.0484, "lng": 74.3860},
        {"name": "Gurgaon, India", "type": "visited", "lat": 28.4595, "lng": 77.0266},
        # SEA
        {"name": "Singapore", "type": "visited", "lat": 1.3521, "lng": 103.8198},
        {"name": "Macao", "type": "visited", "lat": 22.1987, "lng": 113.5439},
        {"name": "Hong Kong", "type": "visited", "lat": 22.3193, "lng": 114.1694},
        {
            "name": "Siem Reap, Cambodia",
            "type": "visited",
            "lat": 13.3671,
            "lng": 103.8448,
        },
        {
            "name": "Angkor Wat, Cambodia",
            "type": "visited",
            "lat": 13.4125,
            "lng": 103.8670,
        },
        {
            "name": "Bangkok, Thailand",
            "type": "visited",
            "lat": 13.7563,
            "lng": 100.5018,
        },
        # Europe
        {"name": "Paris, France", "type": "visited", "lat": 48.8566, "lng": 2.3522},
        {"name": "Nice, France", "type": "visited", "lat": 43.7102, "lng": 7.2620},
        {
            "name": "London, United Kingdom",
            "type": "visited",
            "lat": 51.5074,
            "lng": -0.1278,
        },
        {
            "name": "Edinburgh, United Kingdom",
            "type": "visited",
            "lat": 55.9533,
            "lng": -3.1883,
        },
        {
            "name": "Bath, United Kingdom",
            "type": "visited",
            "lat": 51.3811,
            "lng": -2.3590,
        },
        {
            "name": "Portree, United Kingdom",
            "type": "visited",
            "lat": 57.4126,
            "lng": -6.1944,
        },
        {
            "name": "Old Man of Storr, United Kingdom",
            "type": "visited",
            "lat": 57.5050,
            "lng": -6.1807,
        },
        # Canada
        {
            "name": "Quebec City, Canada",
            "type": "visited",
            "lat": 46.8139,
            "lng": -71.2080,
        },
        {
            "name": "Montreal, Canada",
            "type": "visited",
            "lat": 45.5017,
            "lng": -73.5673,
        },
        {
            "name": "Lake Louise, Canada",
            "type": "visited",
            "lat": 51.4254,
            "lng": -116.1773,
        },
        {
            "name": "Vancouver, Canada",
            "type": "visited",
            "lat": 49.2827,
            "lng": -123.1207,
        },
        {
            "name": "Whistler, Canada",
            "type": "visited",
            "lat": 50.1163,
            "lng": -122.9574,
        },
        {
            "name": "Victoria, Canada",
            "type": "visited",
            "lat": 48.4284,
            "lng": -123.3656,
        },
        {"name": "Tofino, Canada", "type": "visited", "lat": 49.1533, "lng": -125.9063},
        {
            "name": "Ucluelet, Canada",
            "type": "visited",
            "lat": 48.9420,
            "lng": -125.5463,
        },
        {
            "name": "Jasper National Park, Alberta, Canada",
            "type": "visited",
            "lat": 52.8734,
            "lng": -118.0814,
        },
        {
            "name": "Banff National Park, Alberta, Canada",
            "type": "visited",
            "lat": 51.4968,
            "lng": -115.9281,
        },
        {
            "name": "Yoho National Park, British Columbia, Canada",
            "type": "visited",
            "lat": 51.4254,
            "lng": -116.1773,
        },
        # USA
        {
            "name": "Portland, Oregon, USA",
            "type": "visited",
            "lat": 45.5152,
            "lng": -122.6784,
        },
        {
            "name": "San Francisco, California, USA",
            "type": "visited",
            "lat": 37.7749,
            "lng": -122.4194,
        },
        {
            "name": "Los Angeles, California, USA",
            "type": "visited",
            "lat": 34.0522,
            "lng": -118.2437,
        },
        {
            "name": "Las Vegas, Nevada, USA",
            "type": "visited",
            "lat": 36.1699,
            "lng": -115.1398,
        },
        {
            "name": "New York City, New York, USA",
            "type": "visited",
            "lat": 40.7128,
            "lng": -74.0060,
        },
        {
            "name": "Washington, D.C., USA",
            "type": "visited",
            "lat": 38.9072,
            "lng": -77.0369,
        },
        {
            "name": "Philadelphia, Pennsylvania, USA",
            "type": "visited",
            "lat": 39.9526,
            "lng": -75.1652,
        },
        {
            "name": "Miami, Florida, USA",
            "type": "visited",
            "lat": 25.7617,
            "lng": -80.1918,
        },
        {
            "name": "Orlando, Florida, USA",
            "type": "visited",
            "lat": 28.5383,
            "lng": -81.3792,
        },
        {
            "name": "Key West, Florida, USA",
            "type": "visited",
            "lat": 24.5551,
            "lng": -81.7800,
        },
        {
            "name": "Yellowstone National Park, Wyoming, USA",
            "type": "visited",
            "lat": 44.4280,
            "lng": -110.5885,
        },
        {
            "name": "Yosemite National Park, California, USA",
            "type": "visited",
            "lat": 37.8651,
            "lng": -119.5383,
        },
        {
            "name": "Mount Rainier National Park, Washington, USA",
            "type": "visited",
            "lat": 46.8523,
            "lng": -121.7603,
        },
        {
            "name": "Crater Lake National Park, Oregon, USA",
            "type": "visited",
            "lat": 42.8684,
            "lng": -122.1685,
        },
        {
            "name": "Antelope Canyon, Arizona, USA",
            "type": "visited",
            "lat": 36.8619,
            "lng": -111.3743,
        },
        {
            "name": "Hoover Dam, Nevada, USA",
            "type": "visited",
            "lat": 36.0162,
            "lng": -114.7377,
        },
        {
            "name": "North Cascades National Park, Washington, USA",
            "type": "visited",
            "lat": 48.7718,
            "lng": -121.2985,
        },
        {
            "name": "Olympic National Park, Washington, USA",
            "type": "visited",
            "lat": 47.8021,
            "lng": -123.6044,
        },
        {
            "name": "Glacier National Park, Montana, USA",
            "type": "visited",
            "lat": 48.7596,
            "lng": -113.7870,
        },
        {
            "name": "Fairbanks, Alaska, USA",
            "type": "visited",
            "lat": 64.8378,
            "lng": -147.7164,
        },
        {
            "name": "Castner Glacier, Alaska, USA",
            "type": "visited",
            "lat": 63.2780,
            "lng": -145.9070,
        },
        {
            "name": "Oahu, Hawaii, USA",
            "type": "visited",
            "lat": 21.4389,
            "lng": -158.0001,
        },
        {
            "name": "Maui, Hawaii, USA",
            "type": "visited",
            "lat": 20.7984,
            "lng": -156.3319,
        },
        {
            "name": "Kauai, Hawaii, USA",
            "type": "visited",
            "lat": 22.0964,
            "lng": -159.5261,
        },
        {
            "name": "Big Island, Hawaii, USA",
            "type": "visited",
            "lat": 19.8968,
            "lng": -155.5828,
        },
        {
            "name": "Cannon Beach, Oregon, USA",
            "type": "visited",
            "lat": 45.8918,
            "lng": -123.9615,
        },
        {
            "name": "Hoh Rainforest, Washington, USA",
            "type": "visited",
            "lat": 47.8606,
            "lng": -123.9348,
        },
        {
            "name": "Santa Monica, California, USA",
            "type": "visited",
            "lat": 34.0195,
            "lng": -118.4912,
        },
        {
            "name": "Lake Tahoe, California, USA",
            "type": "visited",
            "lat": 39.0968,
            "lng": -120.0324,
        },
        {
            "name": "Kennedy Space Center, Florida, USA",
            "type": "visited",
            "lat": 28.5721,
            "lng": -80.6480,
        },
        {
            "name": "Disneyland Paris, France",
            "type": "visited",
            "lat": 48.8674,
            "lng": 2.7834,
        },
        {
            "name": "Dallas, Texas, USA",
            "type": "visited",
            "lat": 32.7767,
            "lng": -96.7970,
        },
        {
            "name": "Houston, Texas, USA",
            "type": "visited",
            "lat": 29.7604,
            "lng": -95.3698,
        },
        {
            "name": "Salt Lake City, Utah, USA",
            "type": "visited",
            "lat": 40.7608,
            "lng": -111.8910,
        },
        # Mexico
        {"name": "Tulum, Mexico", "type": "visited", "lat": 20.2114, "lng": -87.4654},
        {
            "name": "Playa del Carmen, Mexico",
            "type": "visited",
            "lat": 20.6296,
            "lng": -87.0739,
        },
        {"name": "Cozumel, Mexico", "type": "visited", "lat": 20.4230, "lng": -86.9223},
        {
            "name": "Chichen Itza, Mexico",
            "type": "visited",
            "lat": 20.6843,
            "lng": -88.5678,
        },
        {
            "name": "Valladolid, Mexico",
            "type": "visited",
            "lat": 20.6906,
            "lng": -88.2025,
        },
    ]

    formatted_entries = []
    for entry in TRAVEL_ENTRIES:
        display_date = entry["date"]
        try:
            display_date = datetime.date.fromisoformat(entry["date"]).strftime(
                "%B %d, %Y"
            )
        except (ValueError, TypeError):
            pass
        formatted_entry = dict(entry)
        formatted_entry["display_date"] = display_date
        formatted_entries.append(formatted_entry)

    return render_template(
        "travels.html",
        travel_pins=locations,
        travel_entries=formatted_entries,
        active_page="travels",
    )


@app.route("/resume")
def resume():
    """Render the resume page.

    Returns:
        Response: Rendered resume page template for downloading or viewing resume.
    """
    return render_template("resume.html", active_page="resume")


@app.route("/about")
def about():
    """Render the about page.

    Returns:
        Response: Rendered about page template.
    """
    travels_url = url_for("travels")
    latest_photos = []
    for entry in TRAVEL_ENTRIES:
        for photo in entry["photos"]:
            latest_photos.append(
                {
                    "src": photo["src"],
                    "alt": photo["alt"],
                    "caption": photo["caption"],
                    "href": f"{travels_url}#{entry['slug']}",
                    "location": entry["location"],
                }
            )
    latest_photos = latest_photos[:2]  # Show top 2 latest photos

    return render_template(
        "about.html", active_page="about", latest_photos=latest_photos
    )


@app.route("/contact")
def contact():
    """Render the contact form page."""
    return render_template("contact.html", active_page="contact")


# Add the main execution block if you run this file directly
if __name__ == "__main__":
    # Debug=True is useful for development, disable for production
    # Host='0.0.0.0' makes it accessible on your network
    # Note: Gunicorn runs this, so this block isn't executed by CMD
    app.run(debug=False, host="0.0.0.0")  # Set debug=False when run by Gunicorn

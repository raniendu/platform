"""
Property-based tests for Nginx authentication and HTTPS enforcement.

**Feature: prefect-digitalocean-deployment, Property 6 & 7**

Tests authentication enforcement and HTTPS redirect behavior.

**Validates: Requirements 5.1, 5.3, 6.4**
"""

import subprocess
import time
from typing import Optional

import pytest
import requests
from hypothesis import given, settings, strategies as st


# Helper function to check if Docker Compose stack is running
def is_production_stack_running() -> bool:
    """Check if production Docker Compose stack is running."""
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", "docker-compose.prod.yml", "ps", "-q", "nginx"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# Skip tests if production stack is not running
pytestmark = pytest.mark.skipif(
    not is_production_stack_running(),
    reason="Production Docker Compose stack not running. Start with: docker compose -f docker-compose.prod.yml up -d",
)


# Strategies for generating test data
http_path_strategy = st.sampled_from([
    "/",
    "/api",
    "/api/health",
    "/docs",
    "/flows",
])

http_method_strategy = st.sampled_from(["GET", "POST", "PUT", "DELETE"])

# Strategy for generating various invalid/missing auth headers
invalid_auth_strategy = st.one_of(
    st.none(),  # No auth header
    st.just(""),  # Empty auth header
    st.just("Basic invalid"),  # Invalid base64
    st.just("Bearer token"),  # Wrong auth type
    st.text(min_size=1, max_size=50).map(lambda s: f"Basic {s}"),  # Random invalid
)


@given(path=http_path_strategy, auth_header=invalid_auth_strategy)
@settings(max_examples=100, deadline=5000)
def test_authentication_enforcement_property(path: str, auth_header: Optional[str]) -> None:
    """
    **Feature: prefect-digitalocean-deployment, Property 6: Authentication enforcement**
    
    Property: For any HTTPS request to the Prefect UI or API without valid credentials,
    the system SHALL return a 401 Unauthorized response.
    
    This ensures that all endpoints are protected by basic authentication and
    unauthorized access is consistently rejected.
    
    **Validates: Requirements 5.1, 5.3**
    """
    # Construct URL (using localhost since we're testing locally)
    url = f"https://localhost{path}"
    
    # Prepare headers
    headers = {}
    if auth_header is not None:
        headers["Authorization"] = auth_header
    
    try:
        # Make request without valid credentials
        response = requests.get(
            url,
            headers=headers,
            verify=False,  # Skip SSL verification for local testing
            timeout=3,
            allow_redirects=False,
        )
        
        # Verify 401 Unauthorized response
        assert response.status_code == 401, (
            f"Expected 401 Unauthorized for unauthenticated request to {path}, "
            f"but got {response.status_code}"
        )
        
        # Verify WWW-Authenticate header is present (required for 401)
        assert "WWW-Authenticate" in response.headers, (
            f"401 response missing WWW-Authenticate header for {path}"
        )
        
    except requests.exceptions.ConnectionError:
        pytest.skip("Cannot connect to production stack - ensure it's running")
    except requests.exceptions.Timeout:
        pytest.skip("Request timeout - production stack may be slow to respond")


@given(path=http_path_strategy, method=http_method_strategy)
@settings(max_examples=100, deadline=5000)
def test_https_redirect_property(path: str, method: str) -> None:
    """
    **Feature: prefect-digitalocean-deployment, Property 7: HTTPS enforcement**
    
    Property: For any HTTP request to the domain (except ACME challenge and health check),
    the system SHALL redirect to HTTPS with a 301 or 302 response.
    
    This ensures all traffic is encrypted and users are automatically redirected
    to the secure version of the site.
    
    **Validates: Requirements 6.4**
    """
    # Skip ACME challenge path (needed for Let's Encrypt)
    if path.startswith("/.well-known/acme-challenge"):
        return
    
    # Skip health check path (no redirect for monitoring)
    if path == "/health":
        return
    
    # Construct HTTP URL
    url = f"http://localhost{path}"
    
    try:
        # Make HTTP request without following redirects
        response = requests.request(
            method,
            url,
            allow_redirects=False,
            timeout=3,
        )
        
        # Verify redirect response (301 or 302)
        assert response.status_code in [301, 302], (
            f"Expected 301/302 redirect for HTTP request to {path}, "
            f"but got {response.status_code}"
        )
        
        # Verify Location header points to HTTPS
        assert "Location" in response.headers, (
            f"Redirect response missing Location header for {path}"
        )
        
        location = response.headers["Location"]
        assert location.startswith("https://"), (
            f"Redirect location should use HTTPS, but got: {location}"
        )
        
    except requests.exceptions.ConnectionError:
        pytest.skip("Cannot connect to production stack - ensure it's running")
    except requests.exceptions.Timeout:
        pytest.skip("Request timeout - production stack may be slow to respond")


def test_health_check_no_redirect() -> None:
    """
    Test that the health check endpoint does NOT redirect to HTTPS.
    
    This is important for load balancers and monitoring tools that may
    only support HTTP health checks.
    """
    url = "http://localhost/health"
    
    try:
        response = requests.get(url, allow_redirects=False, timeout=3)
        
        # Health check should return 200, not redirect
        assert response.status_code == 200, (
            f"Health check should return 200, but got {response.status_code}"
        )
        
        assert response.text.strip() == "healthy", (
            f"Health check should return 'healthy', but got: {response.text}"
        )
        
    except requests.exceptions.ConnectionError:
        pytest.skip("Cannot connect to production stack - ensure it's running")
    except requests.exceptions.Timeout:
        pytest.skip("Request timeout - production stack may be slow to respond")


def test_acme_challenge_no_redirect() -> None:
    """
    Test that ACME challenge paths do NOT redirect to HTTPS.
    
    This is required for Let's Encrypt certificate validation.
    """
    url = "http://localhost/.well-known/acme-challenge/test"
    
    try:
        response = requests.get(url, allow_redirects=False, timeout=3)
        
        # Should not redirect (may return 404 if file doesn't exist, but not 301/302)
        assert response.status_code not in [301, 302], (
            f"ACME challenge path should not redirect, but got {response.status_code}"
        )
        
    except requests.exceptions.ConnectionError:
        pytest.skip("Cannot connect to production stack - ensure it's running")
    except requests.exceptions.Timeout:
        pytest.skip("Request timeout - production stack may be slow to respond")

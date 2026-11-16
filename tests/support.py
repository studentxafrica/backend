"""Shared helpers for API tests."""
from __future__ import annotations

from http.cookies import SimpleCookie

PASSWORD = "Correct-Horse-Battery-1"


def access_token_from(response) -> str:
    """Pull the access token out of a login response's Set-Cookie header."""
    for header in response.headers.getlist("Set-Cookie"):
        cookie = SimpleCookie()
        cookie.load(header)
        if "access_token" in cookie:
            return cookie["access_token"].value
    raise AssertionError("response did not set an access token")


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}

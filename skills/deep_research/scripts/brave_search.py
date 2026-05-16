"""Thin Brave Search API client."""

from __future__ import annotations

import os
from typing import Any

import httpx

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"


class BraveSearchError(Exception):
    pass


def search(query: str, count: int = 5) -> list[dict[str, Any]]:
    """Return a list of results: [{title, url, description}].

    Raises BraveSearchError on missing API key or non-200 response.
    """
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        raise BraveSearchError("BRAVE_API_KEY environment variable is not set")

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    params = {"q": query, "count": min(count, 20), "search_lang": "en", "safesearch": "moderate"}

    with httpx.Client(timeout=20.0) as client:
        resp = client.get(BRAVE_API_URL, headers=headers, params=params)

    if resp.status_code != 200:
        raise BraveSearchError(f"Brave API returned HTTP {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    results = []
    for item in data.get("web", {}).get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "description": item.get("description", ""),
        })
    return results

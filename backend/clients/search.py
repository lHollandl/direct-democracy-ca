"""Web search for reference recommendation (ARCHITECTURE.md §8.2).

One interface, one implementation per `SEARCH_PROVIDER`. If `SEARCH_API_KEY` is
unset the admin trigger returns 503 `search_not_configured` and nothing else
breaks — the director has not chosen a provider yet (TODO P0-13), and a stub
that invented results would be worse than an honest refusal.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from backend.config.settings_env import get_env_settings
from backend.errors import ExternalServiceDown

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Result:
    title: str
    url: str
    snippet: str

    def as_dict(self) -> dict[str, str]:
        return {"title": self.title, "url": self.url, "snippet": self.snippet}


class SearchClient:
    """The provider is configuration. `raw` keeps whatever the provider sent,
    because the `ai_actions` row stores it verbatim (DEMOCRACY.md §9.4)."""

    def __init__(self) -> None:
        env = get_env_settings()
        self.provider = env.SEARCH_PROVIDER
        self.api_key = env.SEARCH_API_KEY
        self.base_url = env.SEARCH_BASE_URL
        self.configured = env.search_configured

    def require_configured(self) -> None:
        if not self.configured:
            raise ExternalServiceDown(
                "Reference recommendation needs a web search provider, and none "
                "is configured on this platform yet.",
                code="search_not_configured",
            )

    async def search(self, query: str) -> tuple[list[Result], Any]:
        """Returns the parsed results and the provider's raw response."""
        self.require_configured()
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(
                    self.base_url,
                    params={"q": query},
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                response.raise_for_status()
                raw = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ExternalServiceDown(
                "The search provider is not answering right now.",
                code="search_unavailable",
            ) from exc
        return _parse(raw), raw


def _parse(raw: Any) -> list[Result]:
    """Providers differ; the shapes below cover the common ones. A provider
    whose shape is not here is a one-function change, which is the point of
    keeping the interface this small."""
    items = []
    if isinstance(raw, dict):
        for key in ("results", "web", "organic", "data"):
            candidate = raw.get(key)
            if isinstance(candidate, dict):
                candidate = candidate.get("results")
            if isinstance(candidate, list):
                items = candidate
                break
    elif isinstance(raw, list):
        items = raw
    parsed = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("url") or item.get("link") or ""
        if not url:
            continue
        parsed.append(
            Result(
                title=str(item.get("title") or url),
                url=str(url),
                snippet=str(item.get("snippet") or item.get("description") or ""),
            )
        )
    return parsed


_client: SearchClient | None = None


def get_search() -> SearchClient:
    global _client
    if _client is None:
        _client = SearchClient()
    return _client


def override_search(client) -> None:
    global _client
    _client = client

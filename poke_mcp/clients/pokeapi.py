"""Lightweight wrapper around PokAPI for fetching species data."""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

import requests


class PokeAPIClientError(RuntimeError):
    """Raised when the PokeAPI request fails."""


class PokeAPIClient:
    """Small helper client with naive in-memory caching."""

    BASE_URL = "https://pokeapi.co/api/v2"

    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
        cache_ttl: int = 600,
        timeout: int = 10,
        user_agent: str = "poke-mcp/0.1 (+https://github.com/)",
    ) -> None:
        self.session = session or requests.Session()
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self.user_agent = user_agent
        self._cache: Dict[str, tuple[float, Any]] = {}
        self._type_cache: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_pokemon(self, name: str) -> Dict[str, Any]:
        slug = self._slugify_name(name)
        endpoint = f"pokemon/{slug}"
        return self._get_json(endpoint)

    def get_pokemon_types(self, name: str) -> List[str]:
        payload = self.get_pokemon(name)
        return [slot["type"]["name"] for slot in payload.get("types", [])]

    def get_type(self, type_name: str) -> Dict[str, Any]:
        slug = self._slugify_type(type_name)
        endpoint = f"type/{slug}"
        return self._get_json(endpoint)

    def get_type_damage_relations(self, type_name: str) -> Dict[str, Any]:
        slug = self._slugify_type(type_name)
        cached = self._type_cache.get(slug)
        if cached:
            return cached
        payload = self.get_type(slug)
        relations = payload.get("damage_relations", {})
        self._type_cache[slug] = relations
        return relations

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_json(self, endpoint: str) -> Dict[str, Any]:
        url = self._build_url(endpoint)
        now = time.time()
        cached = self._cache.get(url)
        if cached and now - cached[0] < self.cache_ttl:
            return cached[1]

        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
            )
            response.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover - network
            raise PokeAPIClientError(str(exc)) from exc

        payload = response.json()
        self._cache[url] = (now, payload)
        return payload

    def _build_url(self, endpoint: str) -> str:
        endpoint = endpoint.lstrip("/")
        return f"{self.BASE_URL}/{endpoint}"

    @staticmethod
    def _slugify_name(name: str) -> str:
        slug = name.strip().lower()
        slug = re.sub(r"[\s\.]+", "-", slug)
        slug = slug.replace("'", "")
        slug = slug.replace(":", "")
        slug = slug.replace("%", "")
        slug = re.sub(r"[^a-z0-9\-]", "", slug)
        return slug

    @staticmethod
    def _slugify_type(type_name: str) -> str:
        slug = type_name.strip().lower().replace(" ", "-")
        return slug

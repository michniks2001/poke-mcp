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
        self._move_data_cache: Dict[str, Dict[str, Any]] = {}

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

    def get_move_data(self, move_name: str) -> Dict[str, Any]:
        slug = self._slugify_move(move_name)
        cached = self._move_data_cache.get(slug)
        if cached:
            return cached

        endpoint = f"move/{slug}"
        payload = self._get_json(endpoint, allow_404=True)
        if payload is None:
            data = self._default_move_payload(move_name)
            self._move_data_cache[slug] = data
            return data

        meta = payload.get("meta", {}) or {}
        stat_changes = [
            {
                "stat": (change.get("stat") or {}).get("name"),
                "change": change.get("change", 0),
            }
            for change in payload.get("stat_changes", [])
        ]
        data = {
            "name": payload.get("name", move_name).replace("-", " "),
            "type": (payload.get("type") or {}).get("name"),
            "damage_class": (payload.get("damage_class") or {}).get("name"),
            "priority": payload.get("priority", 0),
            "base_power": payload.get("power"),
            "meta": {
                "ailment": (meta.get("ailment") or {}).get("name"),
                "stat_chance": meta.get("stat_chance"),
                "crit_rate": meta.get("crit_rate"),
                "drain": meta.get("drain"),
                "healing": meta.get("healing"),
                "flinch_chance": meta.get("flinch_chance"),
            },
            "stat_changes": stat_changes,
        }
        self._move_data_cache[slug] = data
        return data

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_json(self, endpoint: str, *, allow_404: bool = False) -> Optional[Dict[str, Any]]:
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
            if response.status_code == 404 and allow_404:
                return None
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

    @staticmethod
    def _slugify_move(move_name: str) -> str:
        return PokeAPIClient._slugify_name(move_name)

    @staticmethod
    def _default_move_payload(move_name: str) -> Dict[str, Any]:
        return {
            "name": move_name,
            "type": None,
            "damage_class": None,
            "priority": 0,
            "base_power": None,
            "meta": {
                "ailment": None,
                "stat_chance": None,
                "crit_rate": None,
                "drain": None,
                "healing": None,
                "flinch_chance": None,
            },
            "stat_changes": [],
        }

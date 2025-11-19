"""HTML scraping and ladder data client for Pikalytics usage pages."""

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

FALLBACK_THREATS: Dict[str, List[tuple[str, float]]] = {
    "hatterene": [("Incineroar", 0.68), ("Chi-Yu", 0.62)],
    "amoonguss": [("Armarouge", 0.6), ("Tornadus", 0.58)],
    "torkoal": [("Chi-Yu", 0.7), ("Landorus-Therian", 0.62)],
    "hawlucha": [("Amoonguss", 0.6)],
    "ogerpon-cornerstone": [("Iron Bundle", 0.64)],
    "grimmsnarl": [("Amoonguss", 0.55)],
    "walking wake": [("Rillaboom", 0.6)],
    "polteageist": [("Kingambit", 0.66)],
    "dragonite": [("Iron Hands", 0.58), ("Landorus-Therian", 0.6)],
    "*": [("Incineroar", 0.6), ("Landorus-Therian", 0.58)],
}


class PikalyticsClientError(RuntimeError):
    """Raised when scraping Pikalytics fails."""


@dataclass
class TeammateEntry:
    pokemon: str
    usage: float
    types: List[str] = field(default_factory=list)


@dataclass
class MoveEntry:
    move: str
    usage: float


@dataclass
class ItemEntry:
    item: str
    usage: float


@dataclass
class AbilityEntry:
    ability: str
    usage: float


@dataclass
class ThreatEntry:
    """Represents a Pokemon that performs well versus the subject."""

    pokemon: str
    win_rate: float
    detail: Optional[str] = None


@dataclass
class PokemonMeta:
    name: str
    usage_percent: Optional[float] = None
    teammates: List[TeammateEntry] = field(default_factory=list)
    moves: List[MoveEntry] = field(default_factory=list)
    items: List[ItemEntry] = field(default_factory=list)
    abilities: List[AbilityEntry] = field(default_factory=list)
    common_threats: List[ThreatEntry] = field(default_factory=list)
    offensive_coverage: List[str] = field(default_factory=list)


LADDER_API_TEMPLATE = "https://www.pikalytics.com/api/l/{season}/{format_slug}"


class PikalyticsClient:
    """Scrapes Pikalytics HTML pages for meta stats."""

    BASE_URL = "https://www.pikalytics.com/pokedex"

    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
        cache_ttl: int = 900,
        timeout: int = 10,
        user_agent: str = "poke-mcp/0.1 (+https://github.com/)",
        ladder_season: str = "2025-09",
        ladder_format: str = "gen9vgc2025regh-1760",
        ladder_data_dir: str | None = None,
        ladder_snapshot: Optional[List[Dict[str, object]]] = None,
    ) -> None:
        self.session = session or requests.Session()
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self.user_agent = user_agent
        self.ladder_season = ladder_season
        self.ladder_format = ladder_format
        self.ladder_data_dir = Path(
            ladder_data_dir
            or Path(__file__).resolve().parents[1] / "data" / "pikalytics"
        )
        self._cache: Dict[str, tuple[float, PokemonMeta]] = {}
        self._ladder_cache: Optional[List[Dict[str, object]]] = ladder_snapshot
        self._ladder_cache_timestamp: float = 0.0

    def fetch_pokemon(self, format_slug: str, name: str) -> PokemonMeta:
        url = self._build_url(format_slug, name)
        now = time.time()
        cached = self._cache.get(url)
        if cached and now - cached[0] < self.cache_ttl:
            return cached[1]

        html = self._fetch_html(url)
        meta = self._parse_html(html, name)
        self._cache[url] = (now, meta)
        return meta

    def get_ladder_entry(self, species: str) -> Optional[Dict[str, object]]:
        """Return the cached ladder entry for a given species, if present."""

        snapshot = self._ensure_ladder_snapshot()
        if not snapshot:
            return None
        target = species.lower().replace(" ", "").replace("-", "")
        for entry in snapshot:
            name = str(entry.get("name") or "").lower().replace(" ", "").replace("-", "")
            if name == target:
                return entry
        return None

    def iter_ladder_entries(self, limit: Optional[int] = None) -> List[Dict[str, object]]:
        snapshot = self._ensure_ladder_snapshot() or []
        if limit is not None:
            return snapshot[:limit]
        return snapshot

    def get_ladder_snapshot(self) -> List[Dict[str, object]]:
        """Return the full cached ladder snapshot."""

        return self._ensure_ladder_snapshot() or []

    def _fetch_html(self, url: str) -> str:
        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
            )
            response.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover
            raise PikalyticsClientError(str(exc)) from exc
        return response.text

    def _parse_html(self, html: str, pokemon_name: str) -> PokemonMeta:
        soup = BeautifulSoup(html, "html.parser")
        usage = self._parse_usage_percent(soup)
        teammates = self._parse_teammates(soup)
        moves = self._parse_table(soup, header="Moves")
        items = self._parse_table(soup, header="Items")
        abilities = self._parse_table(soup, header="Abilities")
        common_threats = self._parse_common_threats(pokemon_name, soup)
        offensive_coverage = self._infer_offensive_coverage(moves)
        return PokemonMeta(
            name=pokemon_name,
            usage_percent=usage,
            teammates=teammates,
            moves=moves,
            items=items,
            abilities=abilities,
            common_threats=common_threats,
            offensive_coverage=offensive_coverage,
        )

    def _parse_usage_percent(self, soup: BeautifulSoup) -> Optional[float]:
        title = soup.find("div", class_="pokemon-ind-summary-title", string=lambda s: s and "Usage Percent" in s)
        if not title:
            return None
        wrapper = title.find_parent("div", class_="pokemon-ind-summary-item")
        if not wrapper:
            return None
        text = wrapper.find("div", class_="pokemon-ind-summary-text")
        if not text:
            return None
        value = text.get_text(strip=True).rstrip("%")
        try:
            return float(value)
        except ValueError:
            return None

    def _parse_teammates(self, soup: BeautifulSoup) -> List[TeammateEntry]:
        entries: List[TeammateEntry] = []
        wrapper = soup.find("div", id="dex_team_wrapper")
        if not wrapper:
            return entries
        for anchor in wrapper.find_all("a", class_="teammate_entry"):
            name = anchor.get("data-name") or anchor.get_text(strip=True)
            usage_text = anchor.find("div", style=lambda v: v and "float:right" in v)
            usage = self._extract_percentage(usage_text.get_text(strip=True)) if usage_text else None
            types = [span.get_text(strip=True) for span in anchor.find_all("span", class_="type")]
            if name and usage is not None:
                entries.append(TeammateEntry(pokemon=name, usage=usage, types=types))
        return entries

    def _parse_table(self, soup: BeautifulSoup, *, header: str) -> List[MoveEntry]:
        results: List[MoveEntry] = []
        header_div = soup.find("div", string=lambda s: s and header in s)
        if not header_div:
            return results
        container = header_div.find_parent("div", class_="pokedex-category-wrapper")
        if not container:
            return results
        for row in container.find_all("div", class_="pokedex-move-entry-new"):
            label = row.find("span", class_=None)
            if not label:
                continue
            text = label.get_text(strip=True)
            pct_div = row.find("div", style=lambda v: v and "float:right" in v)
            usage = self._extract_percentage(pct_div.get_text(strip=True)) if pct_div else None
            if usage is not None:
                results.append(MoveEntry(move=text, usage=usage))
        return results

    def _parse_common_threats(self, pokemon_name: str, soup: BeautifulSoup) -> List[ThreatEntry]:
        """Best-effort scrape for common threat listings (if present)."""

        threats: List[ThreatEntry] = []
        candidate_wrappers = []

        for label in ("Counters", "Matchups", "Common Threats"):
            header = soup.find("div", string=lambda s: s and label in s)
            if header:
                container = header.find_parent("div", class_="pokedex-category-wrapper")
                if container:
                    candidate_wrappers.append(container)

        seen: set[str] = set()
        for container in candidate_wrappers:
            for entry in container.find_all("a", class_="teammate_entry"):
                name = entry.get("data-name") or entry.get_text(strip=True)
                if not name or name in seen:
                    continue
                seen.add(name)
                rate_node = entry.find("div", style=lambda v: v and "float:right" in v)
                win_rate = 0.5
                if rate_node:
                    pct = self._extract_percentage(rate_node.get_text(strip=True))
                    if pct is not None:
                        win_rate = pct / 100
                threats.append(ThreatEntry(pokemon=name, win_rate=win_rate))

        if threats:
            return threats

        key = pokemon_name.lower()
        fallback = FALLBACK_THREATS.get(key, FALLBACK_THREATS.get("*", []))
        return [ThreatEntry(pokemon=name, win_rate=rate) for name, rate in fallback]

    def _infer_offensive_coverage(self, moves: List[MoveEntry]) -> List[str]:
        """Map notable moves to coverage types."""

        move_type_map = {
            # Fire
            "Fire Punch": "Fire",
            "Flamethrower": "Fire",
            "Fire Blast": "Fire",
            "Will-O-Wisp": "Fire",
            # Water
            "Aqua Jet": "Water",
            "Hydro Pump": "Water",
            "Surf": "Water",
            "Aqua Tail": "Water",
            # Electric
            "Thunderbolt": "Electric",
            "Thunder": "Electric",
            "Thunder Wave": "Electric",
            # Psychic
            "Psychic": "Psychic",
            "Psyshock": "Psychic",
            # Ground
            "Earthquake": "Ground",
            "Earth Power": "Ground",
            # Ice
            "Ice Beam": "Ice",
            "Ice Punch": "Ice",
            "Ice Spinner": "Ice",
            # Dark
            "Dark Pulse": "Dark",
            "Knock Off": "Dark",
            # Fighting
            "Close Combat": "Fighting",
            "Focus Blast": "Fighting",
            "Superpower": "Fighting",
            # Fairy
            "Play Rough": "Fairy",
            "Dazzling Gleam": "Fairy",
            # Dragon
            "Dragon Claw": "Dragon",
            "Draco Meteor": "Dragon",
            # Rock
            "Stone Edge": "Rock",
            "Power Gem": "Rock",
        }

        coverage: set[str] = set()
        for move in moves:
            coverage_type = move_type_map.get(move.move)
            if coverage_type:
                coverage.add(coverage_type)
        return sorted(coverage)

    def _extract_percentage(self, text: str) -> Optional[float]:
        text = text.replace("%", "").strip()
        try:
            return float(text)
        except ValueError:
            return None

    def _build_url(self, format_slug: str, name: str) -> str:
        slug = name.replace(" ", "-")
        return f"{self.BASE_URL}/{format_slug}/{slug}?l=en"

    # ------------------------------------------------------------------
    # Ladder snapshot helpers
    # ------------------------------------------------------------------
    def _ensure_ladder_snapshot(self) -> Optional[List[Dict[str, object]]]:
        if self._ladder_cache and (time.time() - self._ladder_cache_timestamp) < self.cache_ttl:
            return self._ladder_cache

        path = self._ladder_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
                self._ladder_cache = data
                self._ladder_cache_timestamp = path.stat().st_mtime
                return data
            except json.JSONDecodeError:
                path.unlink(missing_ok=True)

        data = self._download_ladder_snapshot()
        if data is not None:
            self._ladder_cache = data
            self._ladder_cache_timestamp = time.time()
        return self._ladder_cache

    def _ladder_path(self) -> Path:
        self.ladder_data_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{self.ladder_season}-{self.ladder_format}.json"
        return self.ladder_data_dir / filename

    def _download_ladder_snapshot(self) -> Optional[List[Dict[str, object]]]:
        url = LADDER_API_TEMPLATE.format(
            season=self.ladder_season,
            format_slug=self.ladder_format,
        )
        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent},
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException:  # pragma: no cover - network issues
            return None
        self._ladder_path().write_text(json.dumps(data))
        return data

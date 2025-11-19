"""Tests for the TeamAnalyzer offensive heuristics."""

from __future__ import annotations

from poke_mcp.analysis.team_analyzer import TeamAnalyzer
from poke_mcp.clients.pikalytics import PokemonMeta, ThreatEntry
from poke_mcp.models import PokemonSet, Team


class FakePokeAPI:
    def __init__(self) -> None:
        self._types = {
            "Hatterene": ["psychic"],
            "Amoonguss": ["grass"],
        }

    def get_pokemon_types(self, name: str):
        return self._types.get(name, ["normal"])

    def get_type_damage_relations(self, type_name: str):
        return {}


class FakePikalytics:
    def __init__(self, metas):
        self._metas = metas
        self._ladder_entries = []

    def fetch_pokemon(self, format_slug: str, name: str) -> PokemonMeta:
        return self._metas[name]

    def get_ladder_entry(self, species: str):
        return None

    def iter_ladder_entries(self, limit: int | None = None):
        return []


def test_team_analyzer_surfacing_offensive_threats() -> None:
    meta_hatterene = PokemonMeta(
        name="Hatterene",
        usage_percent=10.0,
        common_threats=[ThreatEntry(pokemon="Incineroar", win_rate=0.7)],
        offensive_coverage=["Fairy"],
    )
    meta_amoonguss = PokemonMeta(name="Amoonguss", usage_percent=5.0)

    fake_pikalytics = FakePikalytics(
        {
            "Hatterene": meta_hatterene,
            "Amoonguss": meta_amoonguss,
        }
    )

    team = Team(
        pokemon=[
            PokemonSet(name="Hatterene", species="Hatterene", moves=["Trick Room", "Dazzling Gleam"]),
            PokemonSet(name="Amoonguss", species="Amoonguss", moves=["Spore", "Giga Drain"]),
        ]
    )

    analyzer = TeamAnalyzer(
        pokeapi_client=FakePokeAPI(),
        pikalytics_client=fake_pikalytics,
    )

    report = analyzer.analyze(team)

    assert any(t.threat == "Incineroar" for t in report.threats)
    assert any("Prep answers" in rec for rec in report.recommendations)
    assert any(
        any("Offensive coverage" in strength for strength in insight.strengths)
        for insight in report.pokemon_insights
    )

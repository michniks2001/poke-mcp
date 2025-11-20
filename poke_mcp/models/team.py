"""Core dataclasses shared across the Pokemon VGC analyzer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(slots=True)
class PokemonSet:
    """Represents a single Smogon/VGC style Pokemon set."""

    name: str
    species: Optional[str] = None
    item: Optional[str] = None
    ability: Optional[str] = None
    tera_type: Optional[str] = None
    nature: Optional[str] = None
    evs: Dict[str, int] = field(default_factory=dict)
    ivs: Dict[str, int] = field(default_factory=dict)
    moves: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass(slots=True)
class Team:
    """Collection of Pokemon sets forming a team."""

    format: str = "vgc"
    name: Optional[str] = None
    pokemon: List[PokemonSet] = field(default_factory=list)

    def add_pokemon(self, pokemon: PokemonSet) -> None:
        self.pokemon.append(pokemon)

    def is_empty(self) -> bool:
        return not self.pokemon


@dataclass(slots=True)
class ThreatAssessment:
    """Describes how a meta Pokemon pressures the submitted team."""

    threat: str
    pressure: float
    reasons: List[str] = field(default_factory=list)


@dataclass(slots=True)
class PokemonInsight:
    """Notes about an individual Pokemon in the team."""

    pokemon: str
    role: Optional[str] = None
    strengths: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)


@dataclass(slots=True)
class TeamReport:
    """Aggregated report returned by the analyzer tools."""

    summary: str
    threats: List[ThreatAssessment] = field(default_factory=list)
    pokemon_insights: List[PokemonInsight] = field(default_factory=list)
    coverage_gaps: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    top_weaknesses: List[str] = field(default_factory=list)
    llm_summary: Optional[str] = None

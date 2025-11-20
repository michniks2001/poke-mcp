"""FastMCP server exposing Pokemon VGC analysis tools."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any, Dict

from fastmcp import FastMCP

from .analysis import TeamAnalyzer
from .clients import PokeAPIClient
from .parsers import parse_team
from .services.analysis_pipeline import AnalysisPipeline
from .vectorstore import LadderVectorStore

try:
    from .llm import GeminiClient
except Exception:  # pragma: no cover
    GeminiClient = None  # type: ignore

app = FastMCP("poke-mcp", version="0.1.0")
_pipeline = AnalysisPipeline(
    analyzer=TeamAnalyzer(),
    vector_store=LadderVectorStore(),
    gemini_client=GeminiClient() if GeminiClient else None,
)
_pokeapi = PokeAPIClient()


@app.tool()
def parse_smogon_team(
    team_text: Annotated[str, "Smogon/Showdown export text"],
) -> Dict[str, Any]:
    """Parse a Smogon-format team and return its structured representation."""

    team = parse_team(team_text)
    return asdict(team)


@app.tool()
def analyze_smogon_team(
    team_text: Annotated[str, "Smogon/Showdown export text"],
) -> Dict[str, Any]:
    """Run the full analyzer pipeline and return the report."""

    team = parse_team(team_text)
    result = _pipeline.analyze_team(team)
    payload = asdict(result["report"])
    payload["vector_context"] = result["vector_context"]
    return payload


@app.tool()
def get_pokemon_data(
    species: Annotated[str, "Species name (e.g., 'Hatterene')"],
) -> str:
    """Get basic typing and stat info for a Pokémon via PokéAPI."""

    try:
        data = _pokeapi.get_pokemon(species)
    except Exception as exc:  # pragma: no cover - network failure
        return f"Error fetching {species}: {exc}"

    stats = {entry["stat"]["name"]: entry["base_stat"] for entry in data.get("stats", [])}
    types = [slot["type"]["name"] for slot in data.get("types", [])]
    abilities = [ability["ability"]["name"] for ability in data.get("abilities", [])]
    return (
        f"Name: {data.get('name', species)}\n"
        f"Types: {', '.join(types) or 'unknown'}\n"
        f"Abilities: {', '.join(abilities) or 'unknown'}\n"
        f"Stats: {stats or 'unknown'}"
    )


@app.tool()
def calculate_type_matchup(
    attacker_type: Annotated[str, "Attacking type"],
    defender_type: Annotated[str, "Defending type"],
) -> str:
    """Return the effectiveness multiplier of an attacking type against a defender type."""

    atk = attacker_type.strip().lower()
    defender = defender_type.strip().lower()
    try:
        relations = _pokeapi.get_type_damage_relations(defender)
    except Exception as exc:  # pragma: no cover - network failure
        return f"Error fetching type data: {exc}"

    def _contains(key: str) -> bool:
        return any(entry.get("name") == atk for entry in relations.get(key, []))

    if _contains("no_damage_from"):
        multiplier = 0.0
    elif _contains("double_damage_from"):
        multiplier = 2.0
    elif _contains("half_damage_from"):
        multiplier = 0.5
    else:
        multiplier = 1.0

    return f"{attacker_type.title()} vs {defender_type.title()} -> {multiplier}x"


def run() -> None:
    """Entry point for `python -m poke_mcp.server` or console script."""

    print("[poke-mcp] Starting MCP server. Press Ctrl+C to stop.")
    app.run()


if __name__ == "__main__":
    run()

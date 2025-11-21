"""FastAPI web server exposing Pokemon VGC analysis tools via REST API."""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .analysis import TeamAnalyzer
from .clients import PokeAPIClient
from .parsers import parse_team
from .services.analysis_pipeline import AnalysisPipeline
from .vectorstore import LadderVectorStore

try:
    from .llm import GeminiClient
except Exception:  # pragma: no cover
    GeminiClient = None  # type: ignore

app = FastAPI(
    title="Poke-MCP Web API",
    description="REST API for Pokemon VGC team analysis",
    version="0.1.0",
)

# Initialize shared services (same as MCP server)
_pipeline = AnalysisPipeline(
    analyzer=TeamAnalyzer(),
    vector_store=LadderVectorStore(),
    gemini_client=GeminiClient() if GeminiClient else None,
)
_pokeapi = PokeAPIClient()

# Mount static files - try multiple possible paths
static_dir = None
possible_static_dirs = [
    Path(__file__).parent.parent / "static",
    Path("static"),
    Path.cwd() / "static",
]
for possible_dir in possible_static_dirs:
    if possible_dir.exists():
        static_dir = possible_dir
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        break
else:
    # Fallback: try current working directory
    static_dir = Path("static")


# Pydantic models for request/response
class TeamTextRequest(BaseModel):
    """Request model for team text endpoints."""

    team_text: str


class ParseTeamResponse(BaseModel):
    """Response model for parsed team."""

    result: Dict[str, Any]


class AnalyzeTeamResponse(BaseModel):
    """Response model for team analysis."""

    result: Dict[str, Any]


class PokemonDataResponse(BaseModel):
    """Response model for Pokemon data."""

    result: str


class TypeMatchupResponse(BaseModel):
    """Response model for type matchup calculation."""

    result: str


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    # Try multiple possible paths
    possible_paths = [
        Path(__file__).parent.parent / "static" / "index.html",
        Path("static") / "index.html",
        Path.cwd() / "static" / "index.html",
    ]
    for index_path in possible_paths:
        if index_path.exists():
            return index_path.read_text(encoding="utf-8")
    return "<html><body><h1>Poke-MCP Web API</h1><p>Static files not found. Please ensure static/index.html exists.</p></body></html>"


@app.post("/api/parse_smogon_team", response_model=ParseTeamResponse)
async def parse_smogon_team(request: TeamTextRequest) -> ParseTeamResponse:
    """Parse a Smogon-format team and return its structured representation."""
    try:
        team = parse_team(request.team_text)
        return ParseTeamResponse(result=asdict(team))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse team: {exc}")


@app.post("/api/analyze_smogon_team", response_model=AnalyzeTeamResponse)
async def analyze_smogon_team(request: TeamTextRequest) -> AnalyzeTeamResponse:
    """Run the full analyzer pipeline and return the report."""
    try:
        team = parse_team(request.team_text)
        result = _pipeline.analyze_team(team)
        payload = asdict(result["report"])
        payload["vector_context"] = result["vector_context"]
        return AnalyzeTeamResponse(result=payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to analyze team: {exc}")


@app.get("/api/get_pokemon_data", response_model=PokemonDataResponse)
async def get_pokemon_data(species: str = Query(..., description="Species name (e.g., 'Hatterene')")) -> PokemonDataResponse:
    """Get basic typing and stat info for a Pokémon via PokéAPI."""
    try:
        data = _pokeapi.get_pokemon(species)
    except Exception as exc:
        return PokemonDataResponse(result=f"Error fetching {species}: {exc}")

    stats = {entry["stat"]["name"]: entry["base_stat"] for entry in data.get("stats", [])}
    types = [slot["type"]["name"] for slot in data.get("types", [])]
    abilities = [ability["ability"]["name"] for ability in data.get("abilities", [])]
    result = (
        f"Name: {data.get('name', species)}\n"
        f"Types: {', '.join(types) or 'unknown'}\n"
        f"Abilities: {', '.join(abilities) or 'unknown'}\n"
        f"Stats: {stats or 'unknown'}"
    )
    return PokemonDataResponse(result=result)


@app.get("/api/calculate_type_matchup", response_model=TypeMatchupResponse)
async def calculate_type_matchup(
    attacker_type: str = Query(..., description="Attacking type"),
    defender_type: str = Query(..., description="Defending type"),
) -> TypeMatchupResponse:
    """Return the effectiveness multiplier of an attacking type against a defender type."""
    atk = attacker_type.strip().lower()
    defender = defender_type.strip().lower()
    try:
        relations = _pokeapi.get_type_damage_relations(defender)
    except Exception as exc:
        return TypeMatchupResponse(result=f"Error fetching type data: {exc}")

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

    result = f"{attacker_type.title()} vs {defender_type.title()} -> {multiplier}x"
    return TypeMatchupResponse(result=result)


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Entry point for running the web server."""
    import uvicorn

    print(f"[poke-mcp-web] Starting web server at http://{host}:{port}")
    print(f"[poke-mcp-web] Press Ctrl+C to stop.")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run()


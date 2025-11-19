"""FastMCP server exposing Pokemon VGC analysis tools."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any, Dict

from fastmcp import FastMCP

from .analysis import TeamAnalyzer
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


def run() -> None:
    """Entry point for `python -m poke_mcp.server` or console script."""

    app.run()

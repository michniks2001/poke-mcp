from dataclasses import asdict

from poke_mcp.models import PokemonSet, Team, TeamReport, ThreatAssessment
from poke_mcp.services.analysis_pipeline import AnalysisPipeline
from poke_mcp.analysis.team_analyzer import PokemonContext


class FakePikalytics:
    def __init__(self) -> None:
        self.synced = False

    def get_ladder_snapshot(self):
        self.synced = True
        return [
            {
                "name": "Incineroar",
                "types": ["fire", "dark"],
                "moves": [{"move": "Flare Blitz"}],
                "items": [{"item": "Safety Goggles"}],
                "team": [{"pokemon": "Rillaboom"}],
                "stats": {"spe": 80},
            }
        ]


class FakeVectorStore:
    def __init__(self) -> None:
        self.synced = False
        self.synced_entries = None

    def sync_with_ladder(self, entries):
        self.synced = True
        self.synced_entries = entries

    def query(self, text: str, n_results: int = 3):
        return [
            {
                "document": "{\"name\": \"Incineroar\", \"types\": [\"fire\", \"dark\"], \"type_context\": \"Resists Grass\"}",
                "metadata": {},
                "distance": 0.1,
            }
        ]


class FakeGemini:
    def summarize_team(self, payload):
        assert payload["vector_context"]
        return "LLM summary"


class FakeAnalyzer:
    def __init__(self) -> None:
        self.pikalytics = FakePikalytics()

    def analyze_with_context(self, team: Team):
        report = TeamReport(
            summary="ok",
            threats=[ThreatAssessment(threat="Incineroar", pressure=0.5, reasons=["Hits Psychic types"])],
        )
        contexts = [PokemonContext(pokemon="Hatterene", types=["psychic"], meta=None)]
        return report, contexts


def test_pipeline_includes_vector_context_and_llm_summary():
    pipeline = AnalysisPipeline(
        analyzer=FakeAnalyzer(),
        vector_store=FakeVectorStore(),
        gemini_client=FakeGemini(),
    )
    team = Team(pokemon=[PokemonSet(name="Hatterene")])
    result = pipeline.analyze_team(team)
    assert result["vector_context"]
    report = result["report"]
    assert report.llm_summary == "LLM summary"
    assert asdict(report)["threats"][0]["threat"] == "Incineroar"

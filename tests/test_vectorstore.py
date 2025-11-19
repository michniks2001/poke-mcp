import json
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from poke_mcp.vectorstore import LadderVectorStore


class DummyEmbedding(embedding_functions.EmbeddingFunction):
    def __init__(self) -> None:
        self._config: dict[str, object] = {}

    @staticmethod
    def name() -> str:  # type: ignore[override]
        return "dummy"

    def __call__(self, input: list[str]) -> list[list[float]]:  # type: ignore[override]
        return [[float(len(text))] for text in input]

    def get_config(self) -> dict[str, object]:  # type: ignore[override]
        return self._config

    @classmethod
    def build_from_config(
        cls, config: dict[str, object]
    ) -> "DummyEmbedding":  # type: ignore[override]
        instance = cls()
        instance._config = config
        return instance


def test_ladder_vector_store_sync_and_query(tmp_path: Path) -> None:
    client = chromadb.Client()
    embedding = DummyEmbedding()
    collection = client.get_or_create_collection(
        name="test-ladder",
        embedding_function=embedding,
    )
    store = LadderVectorStore(
        persist_dir=tmp_path / "vectorstore",
        client=client,
        collection=collection,
        embedding_function=embedding,
    )

    entries = [
        {
            "name": "Incineroar",
            "types": ["fire", "dark"],
            "moves": [{"move": "Flare Blitz"}, {"move": "Darkest Lariat"}],
            "items": [{"item": "Safety Goggles"}],
            "team": [{"pokemon": "Rillaboom"}],
            "stats": {"spe": 80},
        },
        {
            "name": "Sneasler",
            "types": ["fighting", "poison"],
            "moves": [{"move": "Dire Claw"}],
            "items": [{"item": "Air Balloon"}],
            "team": [{"pokemon": "Indeedee-F"}],
            "stats": {"spe": 120},
        },
    ]

    count = store.sync_with_ladder(entries)
    assert count == 2

    results = store.query("fire dark intimidate support", n_results=2)
    assert results
    names = {json.loads(match["document"]) ["name"] for match in results}
    assert "Incineroar" in names
    incin_doc = next(
        json.loads(match["document"]) for match in results if json.loads(match["document"]) ["name"] == "Incineroar"
    )
    assert "Weak to" in incin_doc["type_context"]

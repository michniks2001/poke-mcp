"""ChromaDB-backed store for ladder snapshot documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils import embedding_functions

from ..data.type_chart import TYPE_CHART


class LadderVectorStore:
    """Maintains a local ChromaDB collection for ladder entries."""

    def __init__(
        self,
        *,
        persist_dir: str | Path | None = None,
        collection_name: str = "ladder-meta",
        embedding_model: str = "all-MiniLM-L6-v2",
        client: chromadb.api.client.ClientAPI | None = None,
        collection: Collection | None = None,
        embedding_function: embedding_functions.EmbeddingFunction | None = None,
    ) -> None:
        """Create a vector store.

        Args:
            persist_dir: Directory where ChromaDB files live.
            collection_name: Name of the collection to create or reuse.
            embedding_model: Sentence transformer to embed documents.
            client: Optional preconfigured Chroma client (for testing).
            collection: Optional injected collection (for testing).
            embedding_function: Override default embedding function.
        """
        self.persist_dir = Path(persist_dir or Path.cwd() / "data" / "vectorstore")
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = client or chromadb.PersistentClient(path=str(self.persist_dir))
        self.embedding_function = embedding_function or embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )
        if collection is not None:
            self.collection = collection
        else:
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=self.embedding_function,
            )

    def upsert_entries(self, entries: Iterable[Dict[str, object]]) -> None:
        """Upsert ladder entries into the collection."""

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, object]] = []
        for entry in entries:
            doc = self._build_document(entry)
            if not doc:
                continue
            name = str(entry.get("name") or "").strip()
            if not name:
                continue
            ids.append(name.lower().replace(" ", "-"))
            documents.append(doc)
            type_list = [t for t in entry.get("types", []) if isinstance(t, str)]
            metadatas.append({"types": ",".join(type_list)})
        if ids:
            self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def query(self, text: str, *, n_results: int = 5) -> List[Dict[str, object]]:
        """Retrieve similar ladder documents for the provided text."""

        results = self.collection.query(query_texts=[text], n_results=n_results)
        matches: List[Dict[str, object]] = []
        for idx, doc in enumerate(results.get("documents", [[]])[0]):
            metadata = results.get("metadatas", [[]])[0][idx]
            matches.append(
                {
                    "document": doc,
                    "metadata": metadata or {},
                    "distance": results.get("distances", [[]])[0][idx]
                    if results.get("distances")
                    else None,
                }
            )
        return matches

    def sync_with_ladder(self, entries: Iterable[Dict[str, object]]) -> int:
        """Convenience helper to ingest iterable ladder entries."""

        processed = list(entries)
        if not processed:
            return 0
        self.upsert_entries(processed)
        return len(processed)

    def _build_document(self, entry: Dict[str, object]) -> Optional[str]:
        name = entry.get("name")
        if not isinstance(name, str):
            return None
        types = entry.get("types", []) if isinstance(entry.get("types"), list) else []
        moves = [
            m.get("move")
            for m in entry.get("moves", [])
            if isinstance(m, dict) and m.get("move")
        ]
        items = [
            i.get("item")
            for i in entry.get("items", [])
            if isinstance(i, dict) and i.get("item")
        ]
        teammates = [
            t.get("pokemon")
            for t in entry.get("team", [])
            if isinstance(t, dict) and t.get("pokemon")
        ]
        stats = entry.get("stats", {}) if isinstance(entry.get("stats"), dict) else {}
        speed = stats.get("spe") if isinstance(stats.get("spe"), (int, float)) else None

        type_context = self._describe_types([t for t in types if isinstance(t, str)])
        payload = {
            "name": name,
            "types": types,
            "type_context": type_context,
            "moves": moves,
            "items": items,
            "teammates": teammates,
            "speed": speed,
        }
        return json.dumps(payload)

    def _describe_types(self, types: List[str]) -> str:
        if not types:
            return ""
        strong_against: List[str] = []
        weak_to: List[str] = []
        immune_to: List[str] = []
        for attack, table in TYPE_CHART.items():
            mult = 1.0
            for defender in types:
                if defender in table["zero"]:
                    mult *= 0
                elif defender in table["double"]:
                    mult *= 2
                elif defender in table["half"]:
                    mult *= 0.5
            if mult == 0:
                immune_to.append(attack)
            elif mult < 1:
                strong_against.append(attack)
            elif mult > 1:
                weak_to.append(attack)
        description = []
        if strong_against:
            description.append(f"Resists {', '.join(sorted(set(strong_against)))}")
        if weak_to:
            description.append(f"Weak to {', '.join(sorted(set(weak_to)))}")
        if immune_to:
            description.append(f"Immune to {', '.join(sorted(set(immune_to)))}")
        return "; ".join(description)

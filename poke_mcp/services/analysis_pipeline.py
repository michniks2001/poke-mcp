"""High-level analysis pipeline combining heuristics, vector retrieval, and Gemini."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional

from ..analysis import TeamAnalyzer
from ..clients import PikalyticsClient
from ..data.meta_threats import TYPE_META_THREATS
from ..llm import GeminiClient
from ..models import Team
from ..vectorstore import LadderVectorStore


class AnalysisPipeline:
    """Coordinates deterministic analysis with vector retrieval and Gemini."""

    def __init__(
        self,
        *,
        analyzer: Optional[TeamAnalyzer] = None,
        pikalytics_client: Optional[PikalyticsClient] = None,
        vector_store: Optional[LadderVectorStore] = None,
        gemini_client: Optional[GeminiClient] = None,
        vector_results: int = 5,
        debug_logger: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.analyzer = analyzer or TeamAnalyzer(pikalytics_client=pikalytics_client)
        self.pikalytics = pikalytics_client or self.analyzer.pikalytics
        self.vector_store = vector_store
        self.gemini = gemini_client
        self.vector_results = vector_results
        self._vector_synced = False
        self._debug_logger = debug_logger

    def _debug(self, message: str) -> None:
        if self._debug_logger:
            self._debug_logger(message)

    def analyze_team(self, team: Team) -> Dict[str, Any]:
        report, contexts = self.analyzer.analyze_with_context(team)
        vector_context = self._gather_vector_context(team, contexts, report)
        llm_summary = self._maybe_run_gemini(report, team, contexts, vector_context)
        if llm_summary:
            report.llm_summary = llm_summary
        return {
            "report": report,
            "vector_context": vector_context,
        }

    def _gather_vector_context(
        self, team: Team, contexts, report
    ) -> List[Dict[str, Any]]:
        if not self.vector_store:
            return []
        self._ensure_vectorstore_synced()
        query = self._build_team_query(team, contexts, report)
        self._debug(f"Vector query: {query[:120]}...")
        docs = self.vector_store.query(query, n_results=self.vector_results)
        if not docs:
            return []
        themed = self._build_meta_scouting(report, docs)
        return themed

    def _ensure_vectorstore_synced(self) -> None:
        if self._vector_synced or not self.vector_store or not self.pikalytics:
            return
        entries = self.pikalytics.get_ladder_snapshot()
        if entries:
            self._debug(f"Syncing {len(entries)} ladder entries into vector store")
            self.vector_store.sync_with_ladder(entries)
        self._vector_synced = True

    def _build_team_query(self, team: Team, contexts, report) -> str:
        insight_map = {ins.pokemon: ins for ins in report.pokemon_insights}
        context_map = {ctx.pokemon: ctx for ctx in contexts}
        members: List[str] = []
        for pokemon in team.pokemon:
            ctx = context_map.get(pokemon.name)
            types = "/".join(ctx.types) if ctx and ctx.types else "unknown"
            insight = insight_map.get(pokemon.name)
            role = insight.role if insight and insight.role else "unspecified role"
            moves = ", ".join(pokemon.moves[:4]) or "no moves listed"
            members.append(
                f"{pokemon.name} [{types}] role={role} moves={moves}"
            )
        threat_bits = [
            f"{t.threat}: {'; '.join(t.reasons) if t.reasons else 'general pressure'}"
            for t in report.threats
        ]
        coverage = ", ".join(report.coverage_gaps[:3])
        parts = [" | ".join(members)]
        if threat_bits:
            parts.append("Top threats -> " + " | ".join(threat_bits))
        if coverage:
            parts.append("Coverage gaps -> " + coverage)
        return " || ".join(parts)

    def _build_meta_scouting(
        self, report, docs: List[Dict[str, object]]
    ) -> List[Dict[str, object]]:
        ranked = getattr(report, "top_weaknesses", []) or []
        prioritized = ranked[:2] if ranked else []
        selected_matches: List[Dict[str, object]] = []
        suggested_types: List[str] = []
        for weakness in prioritized:
            threats = TYPE_META_THREATS.get(weakness, [])
            for threat in threats:
                selected_matches.append(
                    {
                        "document": threat["name"],
                        "metadata": {
                            "types": ",".join(threat.get("types", [])),
                            "notes": threat.get("notes"),
                            "weakness": weakness,
                        },
                        "distance": None,
                    }
                )
                suggested_types.append(weakness)
        # if we still don't have matches, fall back to docs (filtered NFEs)
        if not selected_matches:
            for doc in docs:
                parsed = self._parse_doc(doc)
                if not parsed:
                    continue
                if self._is_fully_evolved(parsed["name"]):
                    selected_matches.append(doc)
                if len(selected_matches) >= 3:
                    break
        else:
            # add up to two filtered docs for context
            for doc in docs:
                parsed = self._parse_doc(doc)
                if not parsed or not self._is_fully_evolved(parsed["name"]):
                    continue
                selected_matches.append(doc)
                if len(selected_matches) >= 5:
                    break
        query_text = "Top threats: " + ", ".join(prioritized) if prioritized else "Meta comps"
        return [{"query": query_text, "matches": selected_matches}]

    def _parse_doc(self, doc: Dict[str, object]) -> Optional[Dict[str, Any]]:
        raw = doc.get("document")
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except ValueError:
                return None
        return None

    def _is_fully_evolved(self, name: str) -> bool:
        nfe_keywords = {"bronor", "metang", "magby", "floette", "dolliv", "grovyle", "wingull", "pawmo"}
        slug = name.lower().replace(" ", "").replace("-", "")
        return slug not in nfe_keywords

    def _maybe_run_gemini(
        self,
        report,
        team: Team,
        contexts,
        vector_context: List[Dict[str, Any]],
    ) -> Optional[str]:
        if not self.gemini:
            self._debug("Gemini client unavailable; skipping LLM summary")
            return None
        payload = asdict(report)
        payload["team_moves"] = [
            {
                "pokemon": p.name,
                "moves": p.moves,
                "item": p.item,
                "ability": p.ability,
                "tera_type": p.tera_type,
            }
            for p in team.pokemon
        ]
        payload["vector_context"] = vector_context
        payload["contexts"] = [
            {
                "pokemon": ctx.pokemon,
                "types": ctx.types,
                "offense": getattr(ctx.meta, "offensive_coverage", []),
            }
            for ctx in contexts
        ]
        try:
            self._debug("Invoking Gemini summarize_team")
            summary = self.gemini.summarize_team(payload)
            if summary:
                self._debug("Gemini returned summary")
            else:
                self._debug("Gemini returned empty response")
            return summary
        except Exception as exc:
            self._debug(f"Gemini summarize_team failed: {exc}")
            return None

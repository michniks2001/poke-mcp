"""Command-line interface for running Pokemon VGC team analysis."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from poke_mcp.analysis import TeamAnalyzer
from poke_mcp.parsers import parse_team
from poke_mcp.services.analysis_pipeline import AnalysisPipeline
from poke_mcp.vectorstore import LadderVectorStore

try:  # Optional import for LLM summaries
    from poke_mcp.llm import GeminiClient
except Exception:  # pragma: no cover - Gemini optional
    GeminiClient = None  # type: ignore


def _read_team_text(path: str) -> str:
    if path == "-":
        data = sys.stdin.read()
        if not data.strip():
            raise SystemExit("No team text provided on stdin.")
        return data
    file_path = Path(path)
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}")
    return file_path.read_text(encoding="utf-8")


def _humanize_report(report: dict[str, object], vector_context: list | None = None) -> str:
    lines: list[str] = [str(report.get("summary", "")), ""]

    threats = report.get("threats", []) or []
    if threats:
        lines.append("Threats:")
        for threat in threats:
            lines.append(
                f"  - {threat['threat']} (pressure {threat['pressure']})"
                f" :: {', '.join(threat.get('reasons', []))}"
            )
        lines.append("")

    coverage = report.get("coverage_gaps", []) or []
    if coverage:
        lines.append("Coverage gaps:")
        for gap in coverage:
            lines.append(f"  - {gap}")
        lines.append("")

    recs = report.get("recommendations", []) or []
    if recs:
        lines.append("Recommendations:")
        for rec in recs:
            lines.append(f"  - {rec}")
        lines.append("")

    insights = report.get("pokemon_insights", []) or []
    if insights:
        lines.append("Per-Pokémon insights:")
        for insight in insights:
            role = insight.get("role") or "Unknown role"
            strengths = ", ".join(insight.get("strengths", [])) or "No standout strengths"
            risks = ", ".join(insight.get("risks", [])) or "No major risks"
            lines.append(f"  - {insight['pokemon']}: {role}; strengths: {strengths}; risks: {risks}")

    vectors = vector_context or []
    if vectors:
        lines.append("Meta scouting:")
        for entry in vectors:
            threat = entry.get("threat")
            matches = entry.get("matches") or []
            if not matches:
                continue
            doc = matches[0].get("document")
            if isinstance(doc, str):
                try:
                    info = json.loads(doc)
                    summary = f"{info.get('name')} ({', '.join(info.get('types', []))})"
                    if info.get("type_context"):
                        summary += f" - {info['type_context']}"
                except json.JSONDecodeError:
                    summary = doc
            else:
                summary = str(doc)
            lines.append(f"  - {threat}: {summary}")

    return "\n".join(lines).strip()


def _debug_print(enabled: bool, message: str) -> None:
    if enabled:
        sys.stderr.write(f"[debug] {message}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze Smogon-style VGC teams")
    parser.add_argument(
        "team_file",
        help="Path to Smogon export text or '-' to read from stdin",
    )
    parser.add_argument(
        "--format",
        default="gen9vgc2025regh",
        help="Pikalytics format slug (default: gen9vgc2025regh)",
    )
    parser.add_argument(
        "--team-name",
        help="Optional nickname for the submitted team",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the analyzer report as JSON",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print debug progress information to stderr",
    )
    args = parser.parse_args(argv)

    _debug_print(args.debug, f"Arguments parsed: {args}")
    team_text = _read_team_text(args.team_file)
    _debug_print(args.debug, f"Loaded team text ({len(team_text)} chars)")
    team = parse_team(team_text, name=args.team_name, format_hint="vgc")
    _debug_print(args.debug, f"Parsed team with {len(team.pokemon)} Pokémon")
    llm_client = _maybe_make_gemini_client(debug=args.debug)
    _debug_print(args.debug, f"LLM client available: {bool(llm_client)}")
    vector_store = _maybe_make_vector_store(debug=args.debug)
    _debug_print(args.debug, f"Vector store available: {bool(vector_store)}")
    analyzer = TeamAnalyzer(format_slug=args.format)
    _debug_print(args.debug, f"Initialized analyzer for {args.format}")
    pipeline = AnalysisPipeline(
        analyzer=analyzer,
        vector_store=vector_store,
        gemini_client=llm_client,
        debug_logger=(lambda msg: _debug_print(args.debug, msg)),
    )
    _debug_print(args.debug, "Running analysis pipeline")
    result = pipeline.analyze_team(team)
    _debug_print(args.debug, "Pipeline finished")
    report = result["report"]
    payload = asdict(report)

    if args.json:
        payload["vector_context"] = result["vector_context"]
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(_humanize_report(payload, result["vector_context"]))
        if report.llm_summary:
            print("\nGemini Summary:\n" + report.llm_summary)
    return 0


def _maybe_make_gemini_client(*, debug: bool = False):
    if GeminiClient is None:
        _debug_print(debug, "GeminiClient import unavailable; skipping LLM summaries")
        return None
    try:
        return GeminiClient()
    except Exception as exc:
        _debug_print(debug, f"Failed to initialize Gemini client: {exc}")
        return None


def _maybe_make_vector_store(*, debug: bool = False):
    try:
        return LadderVectorStore()
    except Exception as exc:
        _debug_print(debug, f"Failed to initialize vector store: {exc}")
        return None


if __name__ == "__main__":
    raise SystemExit(main())
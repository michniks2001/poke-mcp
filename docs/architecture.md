# Pokemon VGC MCP Server Architecture

## Goals
- Accept Smogon-style team text and expose MCP tools for parsing, validation, and threat analysis.
- Combine official data (PokéAPI) with metagame usage data (Pikalytics) to surface common threats, coverage gaps, and optimization tips.
- Keep the codebase modular so more data sources or heuristics can be added later.

## High-Level Components
1. **CLI / Entry Point (`main.py`)** – Spins up the MCP server for the host environment.
2. **MCP Server (`poke_mcp.server`)**
   - Registers MCP tools such as `parse_team`, `analyze_team`, and `suggest_adjustments`.
   - Orchestrates requests between parsers, data clients, and analysis services.
3. **Parsers (`poke_mcp.parsers`)**
   - Current parser: `smogon.parse_team` extracts individual Pokémon sets from text.
   - Output: `Team` dataclass containing `PokemonSet` entries.
4. **Data Clients (`poke_mcp.clients`)**
   - `PokeAPIClient`: fetches species, types, abilities, and moves.
   - `PikalyticsClient`: scrapes usage, teammates, threats; includes basic caching and rate limiting safeguards.
5. **Analysis Layer (`poke_mcp.analysis`)**
   - `TeamAnalyzer`: combines parsed team data with external data to produce:
     - Type coverage matrix and defensive/offensive gaps.
     - Common meta threats (top usage Pokémon) that pressure the team.
     - Individual Pokémon notes (e.g., missing speed control, redundant roles).
   - Emits structured `TeamReport` with summary plus actionable recommendations.
6. **Models (`poke_mcp.models`)**
   - Shared dataclasses: `Team`, `PokemonSet`, `ThreatAssessment`, etc.
   - Keeps parsing and analysis layers decoupled.

## Data Flow
```
MCP Tool Call (e.g., analyze_team)
  └── Parses text via `smogon.parse_team`
       └── Builds `Team`
            └── `TeamAnalyzer` enriches with PokéAPI + Pikalytics data
                 └── Outputs structured report + natural language summary
```

## External Integrations
- **PokéAPI**: REST calls using `requests`. Responses cached per session to avoid redundant network usage.
- **Pikalytics**: HTML pages fetched via `requests` + BeautifulSoup scraping. Only essential fields scraped to respect bandwidth.

## MCP Tooling Surface (initial)
1. `parse_team` – Input: Smogon text. Output: JSON `Team` representation.
2. `analyze_team` – Input: Smogon text. Output: `TeamReport` with threats and coverage insights.
3. `suggest_adjustments` – Input: Team JSON/report. Output: prioritized adjustments.

## Next Steps
- Flesh out scoring heuristics inside `TeamAnalyzer`.
- Persist on-disk cache for heavy calls (optional).
- Add unit tests for parsing and threat calculations.

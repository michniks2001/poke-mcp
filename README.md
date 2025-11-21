# poke-mcp

Model Context Protocol server for Pokemon VGC team analysis.

## Installation
```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt  # or pip install -e .[dev]
```

(With `pyproject.toml`, you can also use `pip install .` to pull dependencies.)

## CLI Usage
Analyze a Smogon export from a file:
```bash
python main.py path/to/team.txt
```

Or pipe directly:
```bash
cat team.txt | python main.py - --json
```

Flags:
- `--format`: Pikalytics format slug (default `gen9vgc2025regh`).
- `--team-name`: Optional display name stored in the output.
- `--json`: Emit structured JSON instead of formatted text.

## MCP Server
The FastMCP server exposes four tools:
1. `parse_smogon_team` – returns structured `Team` data.
2. `analyze_smogon_team` – returns full `TeamReport` with threats and insights.
3. `get_pokemon_data` – returns basic typing and stat info for a Pokémon.
4. `calculate_type_matchup` – returns type effectiveness multiplier.

Start the server:
```bash
python -m poke_mcp.server
# or
poke-mcp
```

Once running, connect via any MCP-compatible client (e.g., Claude Desktop) and call the tools with your Smogon text.

## Web Server
A FastAPI web server is available that exposes the same functionality via REST API and includes a simple web interface.

Start the web server:
```bash
python -m poke_mcp.web_server
# or
poke-mcp-web
```

The server will start at `http://127.0.0.1:8000`. Open this URL in your browser to access the web interface.

### API Endpoints
- `POST /api/parse_smogon_team` – Parse a Smogon-format team
  - Request body: `{"team_text": "..."}`
- `POST /api/analyze_smogon_team` – Run full team analysis
  - Request body: `{"team_text": "..."}`
- `GET /api/get_pokemon_data?species=...` – Get Pokémon data
- `GET /api/calculate_type_matchup?attacker_type=...&defender_type=...` – Calculate type matchup

The web interface provides a form to paste team text and buttons to parse or analyze teams, plus utility tools for Pokémon data and type matchups.

## Tests
```bash
pytest
```

## Roadmap
- Enrich TeamAnalyzer with offensive coverage + better recommendations.
- Cache external API responses offline.
- Additional fixtures for Pikalytics scraping and TeamAnalyzer regression tests.

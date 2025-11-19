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
The FastMCP server exposes two tools:
1. `parse_smogon_team` – returns structured `Team` data.
2. `analyze_smogon_team` – returns full `TeamReport` with threats and insights.

Start the server:
```bash
python -m poke_mcp.server
# or
poke-mcp
```

Once running, connect via any MCP-compatible client (e.g., Claude Desktop) and call the tools with your Smogon text.

## Tests
```bash
pytest
```

## Roadmap
- Enrich TeamAnalyzer with offensive coverage + better recommendations.
- Cache external API responses offline.
- Additional fixtures for Pikalytics scraping and TeamAnalyzer regression tests.

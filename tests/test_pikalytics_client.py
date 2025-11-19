"""Unit tests for the Pikalytics client helper methods."""

from __future__ import annotations

from poke_mcp.clients.pikalytics import MoveEntry, PikalyticsClient

SAMPLE_HTML = """
<div class="pokemon-ind-summary-item">
  <div class="pokemon-ind-summary-title">Usage Percent</div>
  <div class="pokemon-ind-summary-text">36%</div>
</div>

<div id="dex_team_wrapper">
  <a class="teammate_entry" data-name="Incineroar">
    <div class="type">fire</div>
    <div style="float:right">27%</div>
  </a>
</div>

<div class="pokedex-category-wrapper">
  <div>Moves</div>
  <div class="pokedex-move-entry-new">
    <span>Flamethrower</span>
    <div style="float:right">40%</div>
  </div>
  <div class="pokedex-move-entry-new">
    <span>Ice Beam</span>
    <div style="float:right">30%</div>
  </div>
</div>

<div class="pokedex-category-wrapper">
  <div>Counters</div>
  <a class="teammate_entry" data-name="Landorus-Therian">
    <div style="float:right">65%</div>
  </a>
</div>
"""


def test_parse_html_extracts_usage_and_offense() -> None:
    client = PikalyticsClient()
    meta = client._parse_html(SAMPLE_HTML, "Dragonite")  # type: ignore[attr-defined]

    assert meta.name == "Dragonite"
    assert meta.usage_percent == 36
    assert meta.teammates[0].pokemon == "Incineroar"
    assert meta.moves == [
        MoveEntry(move="Flamethrower", usage=40.0),
        MoveEntry(move="Ice Beam", usage=30.0),
    ]
    assert set(meta.offensive_coverage) == {"Fire", "Ice"}
    assert meta.common_threats[0].pokemon == "Landorus-Therian"

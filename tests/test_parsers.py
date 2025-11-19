"""Tests for the Smogon parser."""

from poke_mcp.parsers import parse_team

SAMPLE_TEAM = """Hatterene @ Safety Goggles
Ability: Magic Bounce
Tera Type: Fairy
EVs: 252 HP / 4 SpA / 252 SpD
Sassy Nature
IVs: 0 Atk / 0 Spe
- Trick Room
- Reflect
- Dazzling Gleam
- Heal Pulse

Amoonguss @ Leftovers
Ability: Effect Spore
Tera Type: Steel
EVs: 252 HP / 4 SpA / 252 SpD
Sassy Nature
IVs: 0 Atk / 0 Spe
- Foul Play
- Clear Smog
- Rage Powder
- Spore
"""


def test_parse_team_extracts_pokemon_sets() -> None:
    team = parse_team(SAMPLE_TEAM)

    assert len(team.pokemon) == 2
    hatterene = team.pokemon[0]
    assert hatterene.name == "Hatterene"
    assert hatterene.item == "Safety Goggles"
    assert hatterene.evs["HP"] == 252
    assert hatterene.ivs["Atk"] == 0
    assert "Trick Room" in hatterene.moves

    amoonguss = team.pokemon[1]
    assert amoonguss.tera_type == "Steel"
    assert amoonguss.moves[-1] == "Spore"

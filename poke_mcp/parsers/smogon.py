"""Parser for Smogon-style Pokemon team text."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List

from ..models import PokemonSet, Team


def parse_team(raw_text: str, *, name: str | None = None, format_hint: str = "vgc") -> Team:
    """Parse a Smogon-format team export into a Team object."""

    cleaned = raw_text.strip()
    if not cleaned:
        raise ValueError("Team text is empty")

    entries = _split_entries(cleaned)
    team = Team(format=format_hint, name=name)
    for entry in entries:
        pokemon = _parse_entry(entry)
        team.add_pokemon(pokemon)

    return team


def _split_entries(text: str) -> List[str]:
    return [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]


def _parse_entry(chunk: str) -> PokemonSet:
    lines = [line.strip() for line in chunk.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Pokemon entry is empty")

    header = lines[0]
    name, item = _parse_header(header)
    pokemon = PokemonSet(
        name=name,
        species=_infer_species(name),
        item=item,
    )

    for line in lines[1:]:
        if line.startswith("Ability:"):
            pokemon.ability = _value_after_colon(line)
        elif line.startswith("Tera Type:"):
            pokemon.tera_type = _value_after_colon(line)
        elif line.startswith("EVs:"):
            pokemon.evs = _parse_stat_spread(_value_after_colon(line))
        elif line.startswith("IVs:"):
            pokemon.ivs = _parse_stat_spread(_value_after_colon(line))
        elif line.endswith("Nature"):
            pokemon.nature = line.replace("Nature", "").strip()
        elif line.startswith("-"):
            pokemon.moves.append(line.lstrip("- ").strip())
        else:
            pokemon.notes.append(line)

    return pokemon


def _parse_header(line: str) -> tuple[str, str | None]:
    if "@" not in line:
        return line.strip(), None
    name_part, item_part = line.split("@", 1)
    return name_part.strip(), item_part.strip()


def _parse_stat_spread(spread: str) -> Dict[str, int]:
    stats: Dict[str, int] = {}
    for token in _split_stat_tokens(spread):
        value, stat = token
        stats[stat] = value
    return stats


def _split_stat_tokens(spread: str) -> Iterable[tuple[int, str]]:
    for raw in spread.split("/"):
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split()
        if len(parts) < 2:
            continue
        try:
            value = int(parts[0])
        except ValueError:
            continue
        stat = parts[1].upper()
        normalized = _normalize_stat(stat)
        if normalized:
            yield value, normalized


def _normalize_stat(stat: str) -> str | None:
    stat = stat.replace("SP.", "SP").replace("SP", "Sp")
    mapping = {
        "HP": "HP",
        "ATK": "Atk",
        "DEF": "Def",
        "SPA": "SpA",
        "SPD": "SpD",
        "SPE": "Spe",
    }
    key = stat.upper()
    return mapping.get(key)


def _value_after_colon(line: str) -> str:
    return line.split(":", 1)[1].strip()


def _infer_species(name: str) -> str:
    match = re.search(r"\(([^)]*)\)", name)
    if match:
        candidate = match.group(1).strip()
        if candidate and candidate.upper() not in {"M", "F"}:
            return candidate
    cleaned = re.sub(r"\([^)]*\)", "", name).strip()
    return cleaned or name.strip()

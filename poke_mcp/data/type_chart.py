"""Static type chart utilities for Pokemon battle calculations."""

from __future__ import annotations

from typing import Iterable

TYPE_CHART: dict[str, dict[str, tuple[str, ...]]] = {
    "normal": {"double": (), "half": ("rock", "steel"), "zero": ("ghost",)},
    "fire": {
        "double": ("grass", "ice", "bug", "steel"),
        "half": ("fire", "water", "rock", "dragon"),
        "zero": (),
    },
    "water": {
        "double": ("fire", "ground", "rock"),
        "half": ("water", "grass", "dragon"),
        "zero": (),
    },
    "electric": {
        "double": ("water", "flying"),
        "half": ("electric", "grass", "dragon"),
        "zero": ("ground",),
    },
    "grass": {
        "double": ("water", "ground", "rock"),
        "half": ("fire", "grass", "poison", "flying", "bug", "dragon", "steel"),
        "zero": (),
    },
    "ice": {
        "double": ("grass", "ground", "flying", "dragon"),
        "half": ("fire", "water", "ice", "steel"),
        "zero": (),
    },
    "fighting": {
        "double": ("normal", "ice", "rock", "dark", "steel"),
        "half": ("poison", "flying", "psychic", "bug", "fairy"),
        "zero": ("ghost",),
    },
    "poison": {
        "double": ("grass", "fairy"),
        "half": ("poison", "ground", "rock", "ghost"),
        "zero": ("steel",),
    },
    "ground": {
        "double": ("fire", "electric", "poison", "rock", "steel"),
        "half": ("grass", "bug"),
        "zero": ("flying",),
    },
    "flying": {
        "double": ("grass", "fighting", "bug"),
        "half": ("electric", "rock", "steel"),
        "zero": (),
    },
    "psychic": {
        "double": ("fighting", "poison"),
        "half": ("psychic", "steel"),
        "zero": ("dark",),
    },
    "bug": {
        "double": ("grass", "psychic", "dark"),
        "half": ("fire", "fighting", "poison", "flying", "ghost", "steel", "fairy"),
        "zero": (),
    },
    "rock": {
        "double": ("fire", "ice", "flying", "bug"),
        "half": ("fighting", "ground", "steel"),
        "zero": (),
    },
    "ghost": {
        "double": ("psychic", "ghost"),
        "half": ("dark",),
        "zero": ("normal",),
    },
    "dragon": {
        "double": ("dragon",),
        "half": ("steel",),
        "zero": ("fairy",),
    },
    "dark": {
        "double": ("psychic", "ghost"),
        "half": ("fighting", "dark", "fairy"),
        "zero": (),
    },
    "steel": {
        "double": ("ice", "rock", "fairy"),
        "half": ("fire", "water", "electric", "steel"),
        "zero": (),
    },
    "fairy": {
        "double": ("fighting", "dragon", "dark"),
        "half": ("fire", "poison", "steel"),
        "zero": (),
    },
}


def damage_multiplier(attack_type: str, defender_types: Iterable[str]) -> float:
    """Compute damage multiplier for an attack hitting defender types."""

    attack = attack_type.lower()
    chart = TYPE_CHART.get(attack)
    if chart is None:
        return 1.0

    multiplier = 1.0
    for defender in defender_types:
        d = defender.lower()
        if d in chart["zero"]:
            multiplier *= 0.0
        elif d in chart["double"]:
            multiplier *= 2.0
        elif d in chart["half"]:
            multiplier *= 0.5
        else:
            multiplier *= 1.0
    return multiplier

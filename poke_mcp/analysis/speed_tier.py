"""Speed tier calculation engine for VGC analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..models import PokemonSet


@dataclass
class SpeedTier:
    """Represents a Pokemon's speed in various conditions."""

    pokemon_name: str
    base_speed: int
    raw_speed: int  # After EVs/IVs/Nature
    tailwind_speed: Optional[int] = None
    booster_speed: Optional[int] = None
    priority_moves: List[str] = None
    minus_priority_moves: List[str] = None


# Nature multipliers for Speed
NATURE_MULTIPLIERS = {
    "timid": 1.1,
    "jolly": 1.1,
    "hasty": 1.1,
    "naive": 1.1,
    "brave": 0.9,
    "quiet": 0.9,
    "relaxed": 0.9,
    "sassy": 0.9,
}

# Priority move tiers
PRIORITY_MOVES = {
    "+3": ["fake out"],
    "+2": ["extreme speed"],
    "+1": [
        "sucker punch",
        "aqua jet",
        "ice shard",
        "bullet punch",
        "mach punch",
        "vacuum wave",
        "quick attack",
        "shadow sneak",
        "accelerock",
        "first impression",
    ],
    "0": [],  # Normal priority
    "-1": ["whirlwind", "roar", "circle throw", "dragon tail"],
    "-5": ["trick room"],
    "-6": ["focus punch"],
}

# Items that affect speed
SPEED_ITEMS = {
    "choice scarf": 1.5,
    "iron ball": 0.5,
    "macho brace": 0.5,
}

# Abilities that affect speed
SPEED_ABILITIES = {
    "unburden": 2.0,  # After item is consumed
    "swift swim": 2.0,  # In rain
    "chlorophyll": 2.0,  # In sun
    "sand rush": 2.0,  # In sand
    "slush rush": 2.0,  # In hail/snow
    "surge surfer": 2.0,  # In electric terrain
    "quick feet": 1.5,  # When statused
}


class SpeedTierEngine:
    """Calculates speed tiers for Pokemon in various battle conditions."""

    def __init__(self, pokeapi_client=None):
        self.pokeapi = pokeapi_client
        self._base_stat_cache: Dict[str, int] = {}

    def calculate_speed_tier(
        self, pokemon: PokemonSet, base_stats: Optional[Dict[str, int]] = None
    ) -> SpeedTier:
        """Calculate speed tier for a Pokemon."""
        # Get base speed stat
        base_speed = self._get_base_speed(pokemon, base_stats)

        # Calculate raw speed (Level 50 formula)
        raw_speed = self._calculate_stat(
            base_speed,
            pokemon.evs.get("spe", 0),
            pokemon.ivs.get("spe", 31),
            pokemon.nature,
        )

        # Apply item multipliers
        item_multiplier = 1.0
        if pokemon.item:
            item_lower = pokemon.item.lower()
            item_multiplier = SPEED_ITEMS.get(item_lower, 1.0)

        raw_speed = int(raw_speed * item_multiplier)

        # Calculate Tailwind speed (doubles)
        tailwind_speed = raw_speed * 2

        # Calculate Booster Energy speed (if applicable)
        booster_speed = None
        if pokemon.item and "booster energy" in pokemon.item.lower():
            # Booster Energy gives +50% to highest stat if it's Speed
            # For now, assume it's speed if nature is speed-boosting
            if pokemon.nature and pokemon.nature.lower() in ["timid", "jolly", "hasty", "naive"]:
                booster_speed = int(raw_speed * 1.5)

        # Identify priority moves
        priority_moves = []
        minus_priority_moves = []
        for move in pokemon.moves:
            move_lower = move.lower()
            for priority, moves in PRIORITY_MOVES.items():
                if move_lower in moves:
                    if priority.startswith("+"):
                        priority_moves.append(move)
                    elif priority.startswith("-"):
                        minus_priority_moves.append(move)
                    break

        return SpeedTier(
            pokemon_name=pokemon.name,
            base_speed=base_speed,
            raw_speed=raw_speed,
            tailwind_speed=tailwind_speed,
            booster_speed=booster_speed,
            priority_moves=priority_moves,
            minus_priority_moves=minus_priority_moves,
        )

    def _get_base_speed(
        self, pokemon: PokemonSet, base_stats: Optional[Dict[str, int]] = None
    ) -> int:
        """Get base speed stat for a Pokemon."""
        if base_stats and "speed" in base_stats:
            return base_stats["speed"]

        species = pokemon.species or pokemon.name
        if species in self._base_stat_cache:
            return self._base_stat_cache[species]

        # Try to get from PokeAPI
        if self.pokeapi:
            try:
                data = self.pokeapi.get_pokemon(species)
                stats = data.get("stats", [])
                for stat in stats:
                    if stat.get("stat", {}).get("name") == "speed":
                        base_speed = stat.get("base_stat", 50)
                        self._base_stat_cache[species] = base_speed
                        return base_speed
            except Exception:
                pass

        # Fallback
        return 50

    @staticmethod
    def _calculate_stat(
        base: int, evs: int, ivs: int, nature: Optional[str] = None
    ) -> int:
        """Calculate stat at Level 50 (VGC format)."""
        # Level 50 formula: ((2 * Base + IV + EV/4) * Level/100 + 5) * Nature
        # Simplified for Level 50: ((2 * Base + IV + EV/4) + 5) * Nature
        stat = ((2 * base + ivs + evs // 4) + 5)
        
        # Apply nature multiplier
        if nature:
            nature_lower = nature.lower()
            multiplier = NATURE_MULTIPLIERS.get(nature_lower, 1.0)
            stat = int(stat * multiplier)
        
        return stat

    def compare_speeds(
        self, tier1: SpeedTier, tier2: SpeedTier, conditions: Dict[str, bool] = None
    ) -> Dict[str, bool]:
        """Compare two speed tiers under various conditions."""
        conditions = conditions or {}
        
        results = {}
        
        # Raw speed comparison
        results["raw"] = tier1.raw_speed > tier2.raw_speed
        
        # Tailwind comparison
        if conditions.get("tailwind"):
            results["tailwind"] = (
                tier1.tailwind_speed or tier1.raw_speed * 2
            ) > (tier2.tailwind_speed or tier2.raw_speed * 2)
        
        # Booster Energy comparison
        if conditions.get("booster"):
            speed1 = tier1.booster_speed or tier1.raw_speed
            speed2 = tier2.booster_speed or tier2.raw_speed
            results["booster"] = speed1 > speed2
        
        # Priority comparison
        has_priority1 = len(tier1.priority_moves) > 0
        has_priority2 = len(tier2.priority_moves) > 0
        
        if has_priority1 and not has_priority2:
            results["priority"] = True
        elif has_priority2 and not has_priority1:
            results["priority"] = False
        elif has_priority1 and has_priority2:
            # Compare priority levels (simplified)
            results["priority"] = len(tier1.priority_moves) >= len(tier2.priority_moves)
        else:
            results["priority"] = None  # Neither has priority
        
        return results

    def get_speed_control_availability(self, team: List[SpeedTier], pokemon_list: Optional[List] = None) -> Dict[str, bool]:
        """Check what speed control options are available."""
        # If pokemon_list is provided, check moves from there
        if pokemon_list:
            has_tailwind = any(
                "tailwind" in move.lower()
                for pokemon in pokemon_list
                for move in pokemon.moves
            )
            has_trick_room = any(
                "trick room" in move.lower() or "trick-room" in move.lower()
                for pokemon in pokemon_list
                for move in pokemon.moves
            )
            has_speed_reduction = any(
                move.lower() in ["icy wind", "electroweb", "thunder wave"]
                for pokemon in pokemon_list
                for move in pokemon.moves
            )
        else:
            # Fallback - can't check moves from SpeedTier alone
            has_tailwind = False
            has_trick_room = False
            has_speed_reduction = False
        
        has_priority = any(len(tier.priority_moves) > 0 for tier in team)
        
        return {
            "tailwind": has_tailwind,
            "trick_room": has_trick_room,
            "priority": has_priority,
            "speed_reduction": has_speed_reduction,
        }


"""Damage calculation module for VGC analysis using standard Pokemon damage formula."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class DamageResult:
    """Result of a damage calculation."""

    min_damage: int
    max_damage: int
    min_percent: float
    max_percent: float
    average_damage: int
    average_percent: float
    ko_chance: str  # "guaranteed", "likely", "possible", "unlikely", "none"


# Type effectiveness multipliers
TYPE_EFFECTIVENESS = {
    "normal": {"rock": 0.5, "ghost": 0.0, "steel": 0.5},
    "fire": {"fire": 0.5, "water": 0.5, "grass": 2.0, "ice": 2.0, "bug": 2.0, "rock": 0.5, "dragon": 0.5, "steel": 2.0},
    "water": {"fire": 2.0, "water": 0.5, "grass": 0.5, "ground": 2.0, "rock": 2.0, "dragon": 0.5},
    "electric": {"water": 2.0, "electric": 0.5, "grass": 0.5, "ground": 0.0, "flying": 2.0, "dragon": 0.5},
    "grass": {"fire": 0.5, "water": 2.0, "grass": 0.5, "poison": 0.5, "ground": 2.0, "flying": 0.5, "bug": 0.5, "rock": 2.0, "dragon": 0.5, "steel": 0.5},
    "ice": {"fire": 0.5, "water": 0.5, "grass": 2.0, "ice": 0.5, "ground": 2.0, "flying": 2.0, "dragon": 2.0, "steel": 0.5},
    "fighting": {"normal": 2.0, "ice": 2.0, "poison": 0.5, "flying": 0.5, "psychic": 0.5, "bug": 0.5, "rock": 2.0, "ghost": 0.0, "dark": 2.0, "steel": 2.0, "fairy": 0.5},
    "poison": {"grass": 2.0, "poison": 0.5, "ground": 0.5, "rock": 0.5, "ghost": 0.5, "steel": 0.0, "fairy": 2.0},
    "ground": {"fire": 2.0, "electric": 2.0, "grass": 0.5, "poison": 2.0, "flying": 0.0, "bug": 0.5, "rock": 2.0, "steel": 2.0},
    "flying": {"electric": 0.5, "grass": 2.0, "fighting": 2.0, "bug": 2.0, "rock": 0.5, "steel": 0.5},
    "psychic": {"fighting": 2.0, "poison": 2.0, "psychic": 0.5, "dark": 0.0, "steel": 0.5},
    "bug": {"fire": 0.5, "grass": 2.0, "fighting": 0.5, "poison": 0.5, "flying": 0.5, "psychic": 2.0, "ghost": 0.5, "dark": 2.0, "steel": 0.5, "fairy": 0.5},
    "rock": {"fire": 2.0, "ice": 2.0, "fighting": 0.5, "ground": 0.5, "flying": 2.0, "bug": 2.0, "steel": 0.5},
    "ghost": {"normal": 0.0, "psychic": 2.0, "ghost": 2.0, "dark": 0.5},
    "dragon": {"dragon": 2.0, "steel": 0.5, "fairy": 0.0},
    "dark": {"fighting": 0.5, "psychic": 2.0, "ghost": 2.0, "dark": 0.5, "fairy": 0.5},
    "steel": {"fire": 0.5, "water": 0.5, "electric": 0.5, "ice": 2.0, "rock": 2.0, "steel": 0.5, "fairy": 2.0},
    "fairy": {"fire": 0.5, "fighting": 2.0, "poison": 0.5, "dragon": 2.0, "dark": 2.0, "steel": 0.5},
}


class DamageCalculator:
    """Calculates damage using the standard Pokemon damage formula."""

    def calculate_damage(
        self,
        attacker_atk: int,
        defender_def: int,
        base_power: int,
        attacker_level: int = 50,
        type_effectiveness: float = 1.0,
        stab: bool = False,
        item_multiplier: float = 1.0,
        ability_multiplier: float = 1.0,
        weather_multiplier: float = 1.0,
        terrain_multiplier: float = 1.0,
        critical: bool = False,
        defender_hp: int = 100,
    ) -> DamageResult:
        """
        Calculate damage using the standard formula.
        
        Formula: ((((2 * Level / 5 + 2) * Power * A/D) / 50) + 2) * modifiers
        """
        # Base damage calculation
        level_factor = (2 * attacker_level) / 5 + 2
        base_damage = (level_factor * base_power * attacker_atk) / defender_def
        base_damage = (base_damage / 50) + 2
        
        # Apply modifiers
        modifiers = 1.0
        
        # STAB (Same Type Attack Bonus)
        if stab:
            modifiers *= 1.5
        
        # Type effectiveness
        modifiers *= type_effectiveness
        
        # Item multiplier (e.g., Choice Band, Life Orb)
        modifiers *= item_multiplier
        
        # Ability multiplier (e.g., Adaptability, Technician)
        modifiers *= ability_multiplier
        
        # Weather multiplier
        modifiers *= weather_multiplier
        
        # Terrain multiplier
        modifiers *= terrain_multiplier
        
        # Critical hit (1.5x in Gen 9)
        if critical:
            modifiers *= 1.5
        
        # Random factor (0.85 to 1.0)
        min_damage = int(base_damage * modifiers * 0.85)
        max_damage = int(base_damage * modifiers * 1.0)
        average_damage = int(base_damage * modifiers * 0.925)
        
        # Calculate percentages
        min_percent = (min_damage / defender_hp) * 100
        max_percent = (max_damage / defender_hp) * 100
        average_percent = (average_damage / defender_hp) * 100
        
        # Determine KO chance
        if min_damage >= defender_hp:
            ko_chance = "guaranteed"
        elif max_damage >= defender_hp:
            ko_chance = "likely"
        elif average_damage >= defender_hp * 0.75:
            ko_chance = "possible"
        elif average_damage >= defender_hp * 0.5:
            ko_chance = "unlikely"
        else:
            ko_chance = "none"
        
        return DamageResult(
            min_damage=min_damage,
            max_damage=max_damage,
            min_percent=min_percent,
            max_percent=max_percent,
            average_damage=average_damage,
            average_percent=average_percent,
            ko_chance=ko_chance,
        )

    def get_type_effectiveness(
        self, attack_type: str, defender_types: List[str]
    ) -> float:
        """Calculate type effectiveness multiplier."""
        attack_type = attack_type.lower()
        defender_types = [t.lower() for t in defender_types]
        
        multiplier = 1.0
        for defender_type in defender_types:
            effectiveness = TYPE_EFFECTIVENESS.get(attack_type, {})
            type_mult = effectiveness.get(defender_type, 1.0)
            multiplier *= type_mult
        
        return multiplier

    def calculate_move_damage(
        self,
        move_name: str,
        move_type: str,
        base_power: int,
        attacker: Dict,
        defender: Dict,
        conditions: Optional[Dict] = None,
    ) -> DamageResult:
        """
        Calculate damage for a specific move.
        
        Args:
            move_name: Name of the move
            move_type: Type of the move
            base_power: Base power of the move
            attacker: Dict with 'atk' or 'spa', 'types', 'item', 'ability', 'level'
            defender: Dict with 'def' or 'spd', 'types', 'hp', 'level'
            conditions: Optional dict with 'weather', 'terrain', 'critical', etc.
        """
        conditions = conditions or {}
        
        # Determine if physical or special
        is_physical = move_type.lower() in [
            "normal", "fighting", "flying", "poison", "ground",
            "rock", "bug", "ghost", "steel", "dragon", "dark", "fairy"
        ] or base_power == 0  # Status moves
        
        if is_physical:
            attacker_stat = attacker.get("atk", 100)
            defender_stat = defender.get("def", 100)
        else:
            attacker_stat = attacker.get("spa", 100)
            defender_stat = defender.get("spd", 100)
        
        # Check for STAB
        attacker_types = [t.lower() for t in attacker.get("types", [])]
        stab = move_type.lower() in attacker_types
        
        # Type effectiveness
        defender_types = [t.lower() for t in defender.get("types", [])]
        type_effectiveness = self.get_type_effectiveness(move_type, defender_types)
        
        # Item multiplier
        item = attacker.get("item", "").lower()
        item_multiplier = 1.0
        if "choice band" in item and is_physical:
            item_multiplier = 1.5
        elif "choice specs" in item and not is_physical:
            item_multiplier = 1.5
        elif "life orb" in item:
            item_multiplier = 1.3
        
        # Ability multiplier (simplified)
        ability = attacker.get("ability", "").lower()
        ability_multiplier = 1.0
        if ability == "adaptability" and stab:
            ability_multiplier = 2.0 / 1.5  # Adaptability is 2x, but we already applied 1.5x STAB
        elif ability == "technician" and base_power <= 60:
            ability_multiplier = 1.5
        
        # Weather multiplier
        weather = conditions.get("weather", "").lower()
        weather_multiplier = 1.0
        if weather == "sun" and move_type == "fire":
            weather_multiplier = 1.5
        elif weather == "rain" and move_type == "water":
            weather_multiplier = 1.5
        
        # Terrain multiplier
        terrain = conditions.get("terrain", "").lower()
        terrain_multiplier = 1.0
        if terrain == "electric" and move_type == "electric":
            terrain_multiplier = 1.3
        
        return self.calculate_damage(
            attacker_atk=attacker_stat,
            defender_def=defender_stat,
            base_power=base_power,
            attacker_level=attacker.get("level", 50),
            type_effectiveness=type_effectiveness,
            stab=stab,
            item_multiplier=item_multiplier,
            ability_multiplier=ability_multiplier,
            weather_multiplier=weather_multiplier,
            terrain_multiplier=terrain_multiplier,
            critical=conditions.get("critical", False),
            defender_hp=defender.get("hp", 100),
        )


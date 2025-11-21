"""Strategy detection for VGC teams using rule-based heuristics and pattern matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from ..models import Strategy, Team

# Import PokemonContext from team_analyzer (no circular dependency since
# team_analyzer only imports StrategyDetector at runtime, not module level)
from .team_analyzer import PokemonContext


# Speed Control Moves
TRICK_ROOM_MOVES = {"trick room", "trick-room"}
TAILWIND_MOVES = {"tailwind"}
SPEED_REDUCTION_MOVES = {"icy wind", "electroweb", "thunder wave", "bleakwind storm"}

# Weather Moves and Abilities
SUN_MOVES = {"sunny day"}
SUN_ABILITIES = {"drought", "desolate land"}
RAIN_MOVES = {"rain dance"}
RAIN_ABILITIES = {"drizzle", "primordial sea"}
HAIL_MOVES = {"hail"}
SNOW_ABILITIES = {"snow warning"}
HAIL_ABILITIES = {"snow warning"}

# Terrain Moves and Abilities
ELECTRIC_TERRAIN_MOVES = {"electric terrain"}
ELECTRIC_TERRAIN_ABILITIES = {"electric surge"}
PSYCHIC_TERRAIN_MOVES = {"psychic terrain"}
PSYCHIC_TERRAIN_ABILITIES = {"psychic surge"}
GRASSY_TERRAIN_MOVES = {"grassy terrain"}
GRASSY_TERRAIN_ABILITIES = {"grassy surge"}
MISTY_TERRAIN_MOVES = {"misty terrain"}
MISTY_TERRAIN_ABILITIES = {"misty surge"}

# Setup Moves
SETUP_MOVES = {
    "swords dance",
    "nasty plot",
    "shell smash",
    "calm mind",
    "dragon dance",
    "quiver dance",
    "bulk up",
    "shift gear",
    "coil",
    "work up",
    "tail glow",
    "agility",
    "rock polish",
}

# Priority Moves
PRIORITY_MOVES = {
    "fake out",
    "extreme speed",
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
}

# Redirection Moves
REDIRECTION_MOVES = {"rage powder", "follow me"}

# Stall/Defensive Indicators
STALL_MOVES = {"protect", "substitute", "recover", "roost", "soft-boiled", "wish", "heal bell"}
ENTRY_HAZARD_MOVES = {"stealth rock", "spikes", "toxic spikes", "sticky web"}

# Speed Natures (negative speed)
NEGATIVE_SPEED_NATURES = {"brave", "quiet", "relaxed", "sassy"}


class StrategyDetector:
    """Detects team strategies using rule-based heuristics and pattern matching."""

    def __init__(self) -> None:
        pass

    def detect_strategies(
        self, team: Team, contexts: List[PokemonContext]
    ) -> List[Strategy]:
        """Detect all strategies present in the team."""
        strategies: List[Strategy] = []

        # Speed Control Archetypes
        strategies.extend(self._detect_speed_control_archetypes(team, contexts))

        # Weather Archetypes
        strategies.extend(self._detect_weather_archetypes(team, contexts))

        # Terrain Archetypes
        strategies.extend(self._detect_terrain_archetypes(team, contexts))

        # Win Conditions
        strategies.extend(self._detect_win_conditions(team, contexts))

        # Composition Patterns
        strategies.extend(self._detect_composition_patterns(team, contexts))

        # Sort by confidence (highest first)
        strategies.sort(key=lambda s: s.confidence, reverse=True)

        # Return top strategies (limit to avoid overwhelming output)
        return strategies[:8]

    def _detect_speed_control_archetypes(
        self, team: Team, contexts: List[PokemonContext]
    ) -> List[Strategy]:
        """Detect speed control archetypes: Trick Room, Tailwind, etc."""
        strategies: List[Strategy] = []
        context_map = {ctx.pokemon: ctx for ctx in contexts}

        # Trick Room Detection
        trick_room_count = 0
        slow_pokemon_count = 0
        trick_room_users: List[str] = []
        slow_pokemon: List[str] = []

        for pokemon in team.pokemon:
            moves_lower = {m.lower() for m in pokemon.moves}
            if any(move in TRICK_ROOM_MOVES for move in moves_lower):
                trick_room_count += 1
                trick_room_users.append(pokemon.name)

            # Check for slow Pokemon (0 Spe IVs, negative speed nature)
            is_slow = False
            if pokemon.nature and pokemon.nature.lower() in NEGATIVE_SPEED_NATURES:
                is_slow = True
            if pokemon.ivs.get("spe", 31) == 0:
                is_slow = True

            if is_slow:
                slow_pokemon_count += 1
                slow_pokemon.append(pokemon.name)

        if trick_room_count > 0:
            confidence = min(1.0, 0.4 + (trick_room_count * 0.2) + (slow_pokemon_count * 0.1))
            details = [f"{trick_room_count} Pokémon with Trick Room"]
            if slow_pokemon:
                details.append(f"{len(slow_pokemon)} slow Pokémon: {', '.join(slow_pokemon[:3])}")
            if len(slow_pokemon) >= 3:
                confidence = min(1.0, confidence + 0.2)
                details.append("Team optimized for Trick Room with multiple slow Pokémon")

            strategies.append(
                Strategy(
                    name="Trick Room",
                    category="archetype",
                    confidence=confidence,
                    summary="Trick Room team that reverses speed order to favor slow, bulky attackers",
                    details=details,
                )
            )

        # Tailwind Detection
        tailwind_count = 0
        fast_pokemon_count = 0
        tailwind_users: List[str] = []

        for pokemon in team.pokemon:
            moves_lower = {m.lower() for m in pokemon.moves}
            if any(move in TAILWIND_MOVES for move in moves_lower):
                tailwind_count += 1
                tailwind_users.append(pokemon.name)

            # Check for fast Pokemon (positive speed nature, high speed EVs)
            nature = pokemon.nature.lower() if pokemon.nature else ""
            speed_evs = pokemon.evs.get("spe", 0)
            if nature in {"timid", "jolly", "hasty", "naive"} or speed_evs >= 200:
                fast_pokemon_count += 1

        if tailwind_count > 0:
            confidence = min(1.0, 0.5 + (tailwind_count * 0.2) + (fast_pokemon_count * 0.05))
            details = [f"{tailwind_count} Pokémon with Tailwind"]
            if fast_pokemon_count >= 3:
                confidence = min(1.0, confidence + 0.1)
                details.append("Team includes multiple fast Pokémon to benefit from Tailwind")

            strategies.append(
                Strategy(
                    name="Tailwind",
                    category="archetype",
                    confidence=confidence,
                    summary="Tailwind team that doubles speed for fast offensive pressure",
                    details=details,
                )
            )

        # Speed Reduction Detection
        speed_reduction_count = 0
        for pokemon in team.pokemon:
            moves_lower = {m.lower() for m in pokemon.moves}
            if any(move in SPEED_REDUCTION_MOVES for move in moves_lower):
                speed_reduction_count += 1

        if speed_reduction_count >= 2:
            strategies.append(
                Strategy(
                    name="Speed Control (Reduction)",
                    category="archetype",
                    confidence=0.6,
                    summary="Team uses speed reduction moves (Icy Wind, Electroweb, etc.) for speed control",
                    details=[f"{speed_reduction_count} Pokémon with speed reduction moves"],
                )
            )

        return strategies

    def _detect_weather_archetypes(
        self, team: Team, contexts: List[PokemonContext]
    ) -> List[Strategy]:
        """Detect weather-based archetypes: Sun, Rain, Snow/Hail."""
        strategies: List[Strategy] = []

        # Sun Detection
        sun_setters = 0
        sun_abusers = 0
        sun_setters_list: List[str] = []
        sun_abusers_list: List[str] = []

        for pokemon in team.pokemon:
            moves_lower = {m.lower() for m in pokemon.moves}
            ability_lower = pokemon.ability.lower() if pokemon.ability else ""

            if ability_lower in SUN_ABILITIES or any(move in SUN_MOVES for move in moves_lower):
                sun_setters += 1
                sun_setters_list.append(pokemon.name)

            # Check for Fire-type or Solar Beam users
            ctx = next((c for c in contexts if c.pokemon == pokemon.name), None)
            if ctx:
                types_lower = {t.lower() for t in ctx.types}
                if "fire" in types_lower:
                    sun_abusers += 1
                    sun_abusers_list.append(pokemon.name)
                elif "solar beam" in moves_lower or "solar blade" in moves_lower:
                    sun_abusers += 1
                    sun_abusers_list.append(pokemon.name)

        if sun_setters > 0:
            confidence = min(1.0, 0.5 + (sun_setters * 0.2) + (sun_abusers * 0.1))
            details = [f"{sun_setters} sun setter(s): {', '.join(sun_setters_list)}"]
            if sun_abusers > 0:
                details.append(f"{sun_abusers} Pokémon benefit from sun: {', '.join(sun_abusers_list[:3])}")

            strategies.append(
                Strategy(
                    name="Sun Team",
                    category="archetype",
                    confidence=confidence,
                    summary="Sun team that boosts Fire moves and enables Solar Beam/Blade",
                    details=details,
                )
            )

        # Rain Detection
        rain_setters = 0
        rain_abusers = 0
        rain_setters_list: List[str] = []
        rain_abusers_list: List[str] = []

        for pokemon in team.pokemon:
            moves_lower = {m.lower() for m in pokemon.moves}
            ability_lower = pokemon.ability.lower() if pokemon.ability else ""

            if ability_lower in RAIN_ABILITIES or any(move in RAIN_MOVES for move in moves_lower):
                rain_setters += 1
                rain_setters_list.append(pokemon.name)

            # Check for Water-type or Thunder users
            ctx = next((c for c in contexts if c.pokemon == pokemon.name), None)
            if ctx:
                types_lower = {t.lower() for t in ctx.types}
                if "water" in types_lower:
                    rain_abusers += 1
                    rain_abusers_list.append(pokemon.name)
                elif "thunder" in moves_lower:
                    rain_abusers += 1
                    rain_abusers_list.append(pokemon.name)

        if rain_setters > 0:
            confidence = min(1.0, 0.5 + (rain_setters * 0.2) + (rain_abusers * 0.1))
            details = [f"{rain_setters} rain setter(s): {', '.join(rain_setters_list)}"]
            if rain_abusers > 0:
                details.append(f"{rain_abusers} Pokémon benefit from rain: {', '.join(rain_abusers_list[:3])}")

            strategies.append(
                Strategy(
                    name="Rain Team",
                    category="archetype",
                    confidence=confidence,
                    summary="Rain team that boosts Water moves and enables 100% accurate Thunder",
                    details=details,
                )
            )

        # Snow/Hail Detection
        snow_setters = 0
        snow_abusers = 0
        snow_setters_list: List[str] = []
        snow_abusers_list: List[str] = []

        for pokemon in team.pokemon:
            moves_lower = {m.lower() for m in pokemon.moves}
            ability_lower = pokemon.ability.lower() if pokemon.ability else ""

            if ability_lower in SNOW_ABILITIES or any(move in HAIL_MOVES for move in moves_lower):
                snow_setters += 1
                snow_setters_list.append(pokemon.name)

            # Check for Ice-type
            ctx = next((c for c in contexts if c.pokemon == pokemon.name), None)
            if ctx:
                types_lower = {t.lower() for t in ctx.types}
                if "ice" in types_lower:
                    snow_abusers += 1
                    snow_abusers_list.append(pokemon.name)

        if snow_setters > 0:
            confidence = min(1.0, 0.5 + (snow_setters * 0.2) + (snow_abusers * 0.1))
            details = [f"{snow_setters} snow/hail setter(s): {', '.join(snow_setters_list)}"]
            if snow_abusers > 0:
                details.append(f"{snow_abusers} Ice-type Pokémon: {', '.join(snow_abusers_list[:3])}")

            strategies.append(
                Strategy(
                    name="Snow/Hail Team",
                    category="archetype",
                    confidence=confidence,
                    summary="Snow/Hail team that provides chip damage and Ice-type benefits",
                    details=details,
                )
            )

        return strategies

    def _detect_terrain_archetypes(
        self, team: Team, contexts: List[PokemonContext]
    ) -> List[Strategy]:
        """Detect terrain-based archetypes."""
        strategies: List[Strategy] = []

        # Electric Terrain
        electric_terrain_setters = 0
        electric_terrain_setters_list: List[str] = []

        for pokemon in team.pokemon:
            moves_lower = {m.lower() for m in pokemon.moves}
            ability_lower = pokemon.ability.lower() if pokemon.ability else ""

            if ability_lower in ELECTRIC_TERRAIN_ABILITIES or any(
                move in ELECTRIC_TERRAIN_MOVES for move in moves_lower
            ):
                electric_terrain_setters += 1
                electric_terrain_setters_list.append(pokemon.name)

        if electric_terrain_setters > 0:
            strategies.append(
                Strategy(
                    name="Electric Terrain",
                    category="archetype",
                    confidence=0.7,
                    summary="Electric Terrain team that prevents sleep and boosts Electric moves",
                    details=[f"{electric_terrain_setters} setter(s): {', '.join(electric_terrain_setters_list)}"],
                )
            )

        # Psychic Terrain
        psychic_terrain_setters = 0
        psychic_terrain_setters_list: List[str] = []

        for pokemon in team.pokemon:
            moves_lower = {m.lower() for m in pokemon.moves}
            ability_lower = pokemon.ability.lower() if pokemon.ability else ""

            if ability_lower in PSYCHIC_TERRAIN_ABILITIES or any(
                move in PSYCHIC_TERRAIN_MOVES for move in moves_lower
            ):
                psychic_terrain_setters += 1
                psychic_terrain_setters_list.append(pokemon.name)

        if psychic_terrain_setters > 0:
            strategies.append(
                Strategy(
                    name="Psychic Terrain",
                    category="archetype",
                    confidence=0.7,
                    summary="Psychic Terrain team that prevents priority moves and boosts Psychic moves",
                    details=[f"{psychic_terrain_setters} setter(s): {', '.join(psychic_terrain_setters_list)}"],
                )
            )

        # Grassy Terrain
        grassy_terrain_setters = 0
        grassy_terrain_setters_list: List[str] = []

        for pokemon in team.pokemon:
            moves_lower = {m.lower() for m in pokemon.moves}
            ability_lower = pokemon.ability.lower() if pokemon.ability else ""

            if ability_lower in GRASSY_TERRAIN_ABILITIES or any(
                move in GRASSY_TERRAIN_MOVES for move in moves_lower
            ):
                grassy_terrain_setters += 1
                grassy_terrain_setters_list.append(pokemon.name)

        if grassy_terrain_setters > 0:
            strategies.append(
                Strategy(
                    name="Grassy Terrain",
                    category="archetype",
                    confidence=0.7,
                    summary="Grassy Terrain team that provides healing and boosts Grass moves",
                    details=[f"{grassy_terrain_setters} setter(s): {', '.join(grassy_terrain_setters_list)}"],
                )
            )

        return strategies

    def _detect_win_conditions(
        self, team: Team, contexts: List[PokemonContext]
    ) -> List[Strategy]:
        """Detect win conditions: setup sweeper, priority spam, redirection support, etc."""
        strategies: List[Strategy] = []
        context_map = {ctx.pokemon: ctx for ctx in contexts}

        # Setup Sweeper Detection
        setup_sweepers = 0
        setup_sweepers_list: List[str] = []

        for pokemon in team.pokemon:
            moves_lower = {m.lower() for m in pokemon.moves}
            has_setup = any(move in SETUP_MOVES for move in moves_lower)

            # Check for offensive EVs
            atk_evs = pokemon.evs.get("atk", 0)
            spa_evs = pokemon.evs.get("spa", 0)
            is_offensive = max(atk_evs, spa_evs) >= 200

            if has_setup and is_offensive:
                setup_sweepers += 1
                setup_sweepers_list.append(pokemon.name)

        if setup_sweepers > 0:
            confidence = min(1.0, 0.6 + (setup_sweepers * 0.15))
            strategies.append(
                Strategy(
                    name="Setup Sweeper",
                    category="win_condition",
                    confidence=confidence,
                    summary="Team relies on setup moves (Swords Dance, Nasty Plot, etc.) to sweep",
                    details=[f"{setup_sweepers} setup sweeper(s): {', '.join(setup_sweepers_list)}"],
                )
            )

        # Priority Spam Detection
        priority_users = 0
        priority_users_list: List[str] = []

        for pokemon in team.pokemon:
            moves_lower = {m.lower() for m in pokemon.moves}
            has_priority = any(move in PRIORITY_MOVES for move in moves_lower)
            if has_priority:
                priority_users += 1
                priority_users_list.append(pokemon.name)

        if priority_users >= 3:
            strategies.append(
                Strategy(
                    name="Priority Spam",
                    category="win_condition",
                    confidence=0.7,
                    summary="Team uses multiple priority moves to control turn order",
                    details=[f"{priority_users} Pokémon with priority moves: {', '.join(priority_users_list[:4])}"],
                )
            )

        # Redirection Support Detection
        redirection_users = 0
        redirection_users_list: List[str] = []

        for pokemon in team.pokemon:
            moves_lower = {m.lower() for m in pokemon.moves}
            has_redirection = any(move in REDIRECTION_MOVES for move in moves_lower)
            if has_redirection:
                redirection_users += 1
                redirection_users_list.append(pokemon.name)

        if redirection_users > 0:
            strategies.append(
                Strategy(
                    name="Redirection Support",
                    category="win_condition",
                    confidence=0.8,
                    summary="Team uses redirection (Rage Powder/Follow Me) to protect setup or attackers",
                    details=[f"{redirection_users} Pokémon with redirection: {', '.join(redirection_users_list)}"],
                )
            )

        return strategies

    def _detect_composition_patterns(
        self, team: Team, contexts: List[PokemonContext]
    ) -> List[Strategy]:
        """Detect team composition patterns: balance, hyper offense, stall, bulky offense."""
        strategies: List[Strategy] = []

        # Count roles and characteristics
        attackers = 0
        support = 0
        defensive = 0
        stall_indicators = 0

        for pokemon in team.pokemon:
            moves_lower = {m.lower() for m in pokemon.moves}
            hp_evs = pokemon.evs.get("hp", 0)
            atk_evs = pokemon.evs.get("atk", 0)
            spa_evs = pokemon.evs.get("spa", 0)
            def_evs = pokemon.evs.get("def", 0)
            spd_evs = pokemon.evs.get("spd", 0)

            # Check for attacker
            if max(atk_evs, spa_evs) >= 200:
                attackers += 1

            # Check for support
            if any(move in {"reflect", "light screen", "will-o-wisp", "thunder wave"} for move in moves_lower):
                support += 1

            # Check for defensive
            if hp_evs >= 200 and (def_evs >= 100 or spd_evs >= 100):
                defensive += 1

            # Check for stall indicators
            if any(move in STALL_MOVES for move in moves_lower):
                stall_indicators += 1

        # Hyper Offense: Many attackers, few defensive
        if attackers >= 4 and defensive <= 1:
            strategies.append(
                Strategy(
                    name="Hyper Offense",
                    category="composition",
                    confidence=0.8,
                    summary="Hyper offensive team focused on overwhelming opponents quickly",
                    details=[
                        f"{attackers} offensive Pokémon",
                        f"{defensive} defensive Pokémon",
                        "Focuses on fast, powerful attacks",
                    ],
                )
            )

        # Balance: Mix of roles
        elif attackers >= 2 and support >= 1 and defensive >= 1:
            strategies.append(
                Strategy(
                    name="Balance",
                    category="composition",
                    confidence=0.75,
                    summary="Balanced team with mix of offense, defense, and support",
                    details=[
                        f"{attackers} offensive Pokémon",
                        f"{support} support Pokémon",
                        f"{defensive} defensive Pokémon",
                    ],
                )
            )

        # Stall: Many defensive/stall moves
        elif stall_indicators >= 3 or (defensive >= 3 and attackers <= 2):
            strategies.append(
                Strategy(
                    name="Stall",
                    category="composition",
                    confidence=0.7,
                    summary="Stall team that wins through attrition and defensive play",
                    details=[
                        f"{defensive} defensive Pokémon",
                        f"{stall_indicators} Pokémon with stall moves",
                        "Focuses on outlasting opponents",
                    ],
                )
            )

        # Bulky Offense: Mix of bulk and offense
        elif attackers >= 2 and defensive >= 2:
            strategies.append(
                Strategy(
                    name="Bulky Offense",
                    category="composition",
                    confidence=0.7,
                    summary="Bulky offensive team that combines power with durability",
                    details=[
                        f"{attackers} offensive Pokémon",
                        f"{defensive} defensive Pokémon",
                        "Balances power and bulk",
                    ],
                )
            )

        return strategies


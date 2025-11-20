"""Team analysis logic combining PokéAPI typings and heuristic scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

from ..clients import PikalyticsClient, PokeAPIClient
from ..clients.pikalytics import PokemonMeta
from ..data.type_chart import damage_multiplier
from ..models import PokemonInsight, Team, TeamReport, ThreatAssessment


TYPE_ORDER = [
    "normal",
    "fire",
    "water",
    "electric",
    "grass",
    "ice",
    "fighting",
    "poison",
    "ground",
    "flying",
    "psychic",
    "bug",
    "rock",
    "ghost",
    "dragon",
    "dark",
    "steel",
    "fairy",
]

SPEED_CONTROL_MOVES = {
    "trick room",
    "tailwind",
    "icy wind",
    "bleakwind storm",
    "thunder wave",
    "electroweb",
    "trick-room",
}

SUPPORT_AILMENTS = {
    "burn",
    "paralysis",
    "poison",
    "sleep",
    "confusion",
    "freeze",
}

SUPPORT_MOVES = {
    "reflect",
    "light screen",
    "will-o-wisp",
    "rage powder",
    "follow me",
    "snarl",
    "parting shot",
    "fake out",
}

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
    "curse",
}

RELEVANT_OFFENSIVE_TYPES = {
    "fire",
    "water",
    "electric",
    "ice",
    "ground",
    "fighting",
    "fairy",
    "dragon",
    "ghost",
    "dark",
}

COMMON_COVERAGE_TYPES = list(RELEVANT_OFFENSIVE_TYPES) + ["steel", "grass"]

TYPE_COVERAGE_HINTS: Dict[str, str] = {
    "normal": "Add Fighting coverage",
    "steel": "Bring Ground or Fire coverage",
    "rock": "Lean on Water or Grass coverage",
    "fire": "Lean on Water coverage",
    "water": "Bring Electric or Grass coverage",
    "electric": "Add Ground coverage",
    "flying": "Rock or Electric coverage",
    "ground": "Water or Grass coverage",
    "fairy": "Steel or Poison coverage",
}

RESIST_SUGGESTIONS: Dict[str, str] = {
    "fire": "Add a Water-, Rock-, or Dragon-type pivot to soak Fire hits.",
    "water": "Consider a Grass- or Water-resistant core to handle Water attackers.",
    "electric": "Ground-types or Lightning Rod users help patch the Electric gap.",
    "ice": "Bulky Water or Steel-types can sponge Ice attacks.",
    "ground": "Levitate users or Flying-types relieve Ground pressure.",
    "fighting": "Fairy- or Psychic-types deter Fighting spam.",
    "fairy": "Steel- or Poison-types provide reliable Fairy counterplay.",
    "dragon": "Fairy-types or Ice coverage answer Dragon threats.",
    "ghost": "Dark-types or Normal immunities cover Ghost hits.",
    "dark": "Fairy- or Fighting-types mitigate Dark pressure.",
}


@dataclass
class PokemonContext:
    pokemon: str
    types: List[str]
    meta: Optional[PokemonMeta]
    move_data: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class TeamAnalyzer:
    """Provides lightweight heuristics for VGC team feedback."""

    def __init__(
        self,
        *,
        pokeapi_client: Optional[PokeAPIClient] = None,
        pikalytics_client: Optional[PikalyticsClient] = None,
        format_slug: str = "gen9vgc2025regh",
        ladder_threat_limit: int = 40,
    ) -> None:
        self.pokeapi = pokeapi_client or PokeAPIClient()
        self.pikalytics = pikalytics_client or PikalyticsClient()
        self.format_slug = format_slug
        self.ladder_threat_limit = ladder_threat_limit
        self.move_cache: Dict[str, Dict[str, Any]] = {}

    def analyze(self, team: Team) -> TeamReport:
        report, _ = self.analyze_with_context(team)
        return report

    def analyze_with_context(self, team: Team) -> tuple[TeamReport, List[PokemonContext]]:
        if team.is_empty():
            raise ValueError("Team is empty; cannot analyze")

        contexts = self._build_context(team)
        has_speed_control = self._team_has_speed_control(team)
        defense_report = self._evaluate_defensive_profile(contexts)
        offense_report = self._evaluate_offensive_coverage(contexts)
        defensive_threats = self._build_threat_assessments(
            defense_report["weak_counts"], len(team.pokemon)
        )
        offensive_threats = self._build_offensive_threats(
            contexts, len(team.pokemon)
        )
        ladder_threats = self._evaluate_ladder_threats(team, contexts)
        combined_threats = sorted(
            defensive_threats + offensive_threats + ladder_threats,
            key=lambda threat: threat.pressure,
            reverse=True,
        )[:5]
        insights = self._build_pokemon_insights(team, contexts)
        recommendations = self._build_recommendations(
            team, defense_report, offensive_threats, contexts
        )

        ranked_weaknesses: List[str] = defense_report.get("ranked_types", [])[:3]
        summary_bits = [
            f"Detected {len(team.pokemon)} Pokémon",
            f"Top weakness: {defense_report['top_weakness']}" if defense_report["top_weakness"] else "Balanced type chart",
            "Speed control present" if has_speed_control else "No obvious speed control",
        ]
        summary = ". ".join(summary_bits)

        report = TeamReport(
            summary=summary,
            threats=combined_threats,
            pokemon_insights=insights,
            coverage_gaps=defense_report["gap_messages"],
            recommendations=recommendations,
            top_weaknesses=ranked_weaknesses,
        )
        return report, contexts

    # ------------------------------------------------------------------
    # Context building
    # ------------------------------------------------------------------
    def _build_context(self, team: Team) -> List[PokemonContext]:
        contexts: List[PokemonContext] = []
        for pokemon in team.pokemon:
            species = pokemon.species or pokemon.name
            types: List[str] = []
            meta: Optional[PokemonMeta] = None
            move_data: Dict[str, Dict[str, Any]] = {}
            types = self._resolve_types(species)
            try:
                meta = self.pikalytics.fetch_pokemon(self.format_slug, species)
            except Exception:  # pragma: no cover - network failures
                meta = None
            for move in pokemon.moves:
                slug = move.strip().lower()
                if not slug:
                    continue
                cached = self.move_cache.get(slug)
                if cached:
                    move_data[slug] = cached
                    continue
                try:
                    data = self.pokeapi.get_move_data(move)
                except Exception:
                    data = self._fallback_move_data(move)
                self.move_cache[slug] = data
                move_data[slug] = data
            contexts.append(
                PokemonContext(
                    pokemon=pokemon.name,
                    types=types,
                    meta=meta,
                    move_data=move_data,
                )
            )
        return contexts

    def _resolve_types(self, species: str) -> List[str]:
        candidates: List[str] = []
        cleaned = species.strip()
        if cleaned:
            candidates.append(cleaned)
        if "(" in cleaned and ")" in cleaned:
            inner = cleaned.split("(", 1)[1].split(")", 1)[0].strip()
            if inner:
                candidates.append(inner)
        if "-" in cleaned:
            base = cleaned.split("-", 1)[0].strip()
            if base:
                candidates.append(base)
        if " " in cleaned:
            tail = cleaned.split()[-1].strip()
            if tail:
                candidates.append(tail)

        seen: Set[str] = set()
        for candidate in candidates:
            cand = candidate.lower()
            if cand in seen:
                continue
            seen.add(cand)
            try:
                return self.pokeapi.get_pokemon_types(candidate)
            except Exception:  # pragma: no cover - fallback path
                continue
        return []

    # ------------------------------------------------------------------
    # Defensive coverage
    # ------------------------------------------------------------------
    def _evaluate_defensive_profile(self, contexts: List[PokemonContext]) -> Dict[str, any]:
        weak_counts: Dict[str, int] = {}
        resist_counts: Dict[str, int] = {}
        gap_details: List[tuple[int, str]] = []
        recommendations: List[str] = []
        ranked_pairs: List[tuple[str, int]] = []
        for attack_type in TYPE_ORDER:
            weak = 0
            resist = 0
            for ctx in contexts:
                multiplier = self._type_multiplier(ctx.types, attack_type)
                if multiplier > 1.5:
                    weak += 1
                elif multiplier < 1:
                    resist += 1
            weak_counts[attack_type] = weak
            resist_counts[attack_type] = resist
            ranked_pairs.append((attack_type, weak))
            if attack_type in RELEVANT_OFFENSIVE_TYPES:
                if weak >= 3:
                    gap_details.append(
                        (weak, f"{attack_type.title()} offense pressures {weak} team members.")
                    )
                if resist == 0:
                    severity = max(1, weak)
                    gap_details.append(
                        (severity, f"No reliable resist for {attack_type.title()} attacks detected.")
                    )
                    suggestion = RESIST_SUGGESTIONS.get(attack_type)
                    if suggestion:
                        recommendations.append(suggestion)
        gap_messages = [
            msg for _, msg in sorted(gap_details, key=lambda item: item[0], reverse=True)[:3]
        ]
        ranked_types = [
            t for t, count in sorted(ranked_pairs, key=lambda kv: kv[1], reverse=True)
            if count > 0 and t in RELEVANT_OFFENSIVE_TYPES
        ]
        top_weakness = ranked_types[0] if ranked_types else None
        return {
            "weak_counts": weak_counts,
            "resist_counts": resist_counts,
            "gap_messages": gap_messages,
            "recommendations": list(dict.fromkeys(recommendations)),
            "top_weakness": top_weakness,
            "ranked_types": ranked_types,
        }

    def _type_multiplier(self, defender_types: Iterable[str], attack_type: str) -> float:
        if not defender_types:
            return 1.0
        multiplier = 1.0
        attack = attack_type.lower()
        for defender in defender_types:
            try:
                relations = self.pokeapi.get_type_damage_relations(defender)
            except Exception:  # pragma: no cover - network failures
                relations = {}
            multiplier *= self._lookup_multiplier(relations, attack)
        return multiplier

    @staticmethod
    def _lookup_multiplier(relations: Dict[str, List[Dict[str, str]]], attack: str) -> float:
        def _has(relation_name: str) -> bool:
            return any(entry.get("name") == attack for entry in relations.get(relation_name, []))

        if _has("no_damage_from"):
            return 0.0
        if _has("double_damage_from"):
            return 2.0
        if _has("half_damage_from"):
            return 0.5
        return 1.0

    # ------------------------------------------------------------------
    # Threats & insights
    # ------------------------------------------------------------------
    def _build_threat_assessments(
        self, weak_counts: Dict[str, int], team_size: int
    ) -> List[ThreatAssessment]:
        assessments: List[ThreatAssessment] = []
        if not weak_counts:
            return assessments
        for attack_type, count in sorted(weak_counts.items(), key=lambda kv: kv[1], reverse=True):
            if count == 0:
                continue
            pressure = round(count / team_size, 2)
            reason = f"{count} Pokémon weak to {attack_type} attacks"
            assessments.append(
                ThreatAssessment(
                    threat=f"{attack_type.title()}-type attackers",
                    pressure=pressure,
                    reasons=[reason],
                )
            )
        return assessments[:5]

    def _build_offensive_threats(
        self, contexts: List[PokemonContext], team_size: int
    ) -> List[ThreatAssessment]:
        """Aggregate offensive threats using Pikalytics matchup metadata."""

        aggregated: Dict[str, Dict[str, object]] = {}
        for ctx in contexts:
            meta = ctx.meta
            if not meta:
                continue
            for threat in meta.common_threats:
                entry = aggregated.setdefault(
                    threat.pokemon,
                    {"targets": set(), "win_rates": []},
                )
                entry["targets"].add(ctx.pokemon)
                entry["win_rates"].append(threat.win_rate)

        assessments: List[ThreatAssessment] = []
        for threat_name, data in aggregated.items():
            targets: Set[str] = data["targets"]  # type: ignore[assignment]
            # type: ignore[assignment]
            win_rates: List[float] = data["win_rates"]
            if not targets:
                continue
            avg_rate = sum(win_rates) / len(win_rates)
            target_pressure = len(targets) / max(1, team_size)
            pressure = round(min(0.99, max(avg_rate, target_pressure)), 2)
            if pressure < 0.4:
                continue
            reasons = [
                f"Threatens {len(targets)} teammate(s): {', '.join(sorted(targets))}",
                f"Historical win rate ≈ {int(avg_rate * 100)}%",
            ]
            assessments.append(
                ThreatAssessment(
                    threat=threat_name,
                    pressure=pressure,
                    reasons=reasons,
                )
            )

        return sorted(assessments, key=lambda a: a.pressure, reverse=True)[:5]

    def _evaluate_ladder_threats(
        self, team: Team, contexts: List[PokemonContext]
    ) -> List[ThreatAssessment]:
        ladder_entries = self.pikalytics.iter_ladder_entries(
            self.ladder_threat_limit)
        if not ladder_entries:
            return []

        ctx_by_name = {ctx.pokemon: ctx for ctx in contexts}
        team_map = {p.name: p for p in team.pokemon}
        base_speed_cache: Dict[str, Optional[int]] = {}

        assessments: List[ThreatAssessment] = []
        for entry in ladder_entries:
            threat_name = str(entry.get("name") or "").strip()
            if not threat_name:
                continue
            entry_types = [t.lower() for t in entry.get(
                "types", []) if isinstance(t, str)]
            move_types = {
                (m.get("type") or "").lower()
                for m in entry.get("moves", [])
                if isinstance(m, dict) and m.get("type")
            }
            if not entry_types or not move_types:
                continue

            weak_targets: List[str] = []
            resist_targets: List[str] = []
            speed_targets: List[str] = []
            threat_speed = self._entry_speed(entry)
            can_threaten: List[str] = []

            for pokemon in team.pokemon:
                ctx = ctx_by_name.get(pokemon.name)
                if not ctx:
                    continue

                for move_slug, move_data in ctx.move_data.items():
                    move_type = move_data.get("type")
                    base_power = move_data.get("base_power")

                    if (
                        not move_type
                        or not isinstance(base_power, (int, float))
                        or base_power <= 0
                    ):
                        continue

                    mult = damage_multiplier(move_type, entry_types)
                    if mult >= 2.0:
                        can_threaten.append(pokemon.name)
                        break

            for pokemon in team.pokemon:
                ctx = ctx_by_name.get(pokemon.name)
                if not ctx:
                    continue
                # coverage check
                if ctx.types and any(
                    damage_multiplier(move_type, ctx.types) > 1.5 for move_type in move_types
                ):
                    weak_targets.append(pokemon.name)

                # resistance/immunity check
                coverage_types = {
                    (md.get("type") or "").lower()
                    for md in ctx.move_data.values()
                    if isinstance(md.get("base_power"), (int, float))
                    and md.get("base_power") >= 50
                }
                if coverage_types and all(
                    damage_multiplier(cov, entry_types) <= 1.0 for cov in coverage_types
                ):
                    resist_targets.append(pokemon.name)

                # speed check
                if threat_speed is not None:
                    own_speed = base_speed_cache.get(pokemon.name)
                    if own_speed is None:
                        own_speed = self._get_base_speed(pokemon)
                        base_speed_cache[pokemon.name] = own_speed
                    if (
                        own_speed is not None
                        and threat_speed - own_speed >= 10
                        and self._infer_role(pokemon, ctx) != "Speed control"
                    ):
                        speed_targets.append(pokemon.name)

            if not weak_targets and not resist_targets and not speed_targets:
                continue

            pressure = round(
                (
                    len(weak_targets)
                    + 0.5 * len(resist_targets)
                    + 0.5 * len(speed_targets)
                )
                / max(1, len(team.pokemon)),
                2,
            )
            reasons: List[str] = []
            if weak_targets:
                reasons.append(
                    f"Coverage hits {len(weak_targets)} member(s): {', '.join(sorted(weak_targets))}"
                )
            if resist_targets:
                reasons.append(
                    f"Resists common offenses from {', '.join(sorted(resist_targets))}"
                )
            if speed_targets:
                reasons.append(
                    f"Outspeeds {', '.join(sorted(speed_targets))}"
                )

            if not can_threaten and weak_targets:
                reasons.append(
                    f"Team lacks super-effective answers against {', '.join(entry_types)}"
                )
                pressure = round(min(0.99, pressure + 0.3), 2)
            else:
                pressure = min(0.99, pressure)

            assessments.append(
                ThreatAssessment(
                    threat=threat_name,
                    pressure=pressure,
                    reasons=reasons,
                )
            )

        return sorted(assessments, key=lambda a: a.pressure, reverse=True)[:5]

    def _build_pokemon_insights(
        self, team: Team, contexts: List[PokemonContext]
    ) -> List[PokemonInsight]:
        insights: List[PokemonInsight] = []
        context_map = {ctx.pokemon: ctx for ctx in contexts}
        for pokemon in team.pokemon:
            ctx = context_map.get(pokemon.name)
            role = self._infer_role(pokemon, ctx)
            strengths: List[str] = []
            risks: List[str] = []
            if ctx and ctx.meta and ctx.meta.usage_percent:
                strengths.append(
                    f"Seen in {ctx.meta.usage_percent:.1f}% of {
                        self.format_slug} teams"
                )
            has_ground_move = False
            if ctx and ctx.move_data:
                actual_coverage = set()
                for move_slug, move_data in ctx.move_data.items():
                    move_type = (move_data.get("type") or "").lower()
                    base_power = move_data.get("base_power")
                    damage_class = (move_data.get("damage_class") or "").lower()
                    if (
                        move_type
                        and isinstance(base_power, (int, float))
                        and base_power >= 50
                        and damage_class != "status"
                    ):
                        actual_coverage.add(move_type.title())
                        if move_type == "ground":
                            has_ground_move = True

                if actual_coverage:
                    strengths.append(
                        f"This set provides {', '.join(sorted(actual_coverage))} coverage"
                    )

            if (
                not has_ground_move
                and (role in {"Primary attacker", "Setup sweeper"})
                and self._is_physical_attacker(pokemon)
            ):
                risks.append(
                    "No ground coverage (common in VGC for hitting Steels/Electrics)"
                )
            if (
                pokemon.tera_type
                and ctx
                and ctx.types
                and pokemon.tera_type.lower() not in ctx.types
            ):
                strengths.append(
                    f"Tera {pokemon.tera_type} offers matchup flexibility")
            if role is None:
                risks.append("Role unclear from listed moves")
            insights.append(
                PokemonInsight(
                    pokemon=pokemon.name,
                    role=role,
                    strengths=strengths,
                    risks=risks,
                )
            )
        return insights

    def _infer_role(self, pokemon, context: Optional[PokemonContext] = None) -> Optional[str]:
        move_data = context.move_data if context else {}
        types = {t.lower() for t in (context.types if context else [])}
        has_speed_control = False
        has_support = False
        has_setup = False
        stab_powerful = 0
        has_high_power_stab = False
        offensive_move_seen = False

        for move in pokemon.moves:
            slug = move.strip().lower()
            if not slug:
                continue
            data = move_data.get(slug)
            if not data:
                continue
            move_type = (data.get("type") or "").lower()
            damage_class = (data.get("damage_class") or "").lower()
            base_power = data.get("base_power")
            stat_changes = data.get("stat_changes") or []
            meta = data.get("meta") or {}
            ailment = (meta.get("ailment") or "").lower()

            if slug in SPEED_CONTROL_MOVES:
                has_speed_control = True

            boosts_offense = slug in SETUP_MOVES or any(
                (change.get("stat") or "").lower() in {"attack", "special-attack", "speed"}
                and (change.get("change") or 0) > 0
                for change in stat_changes
            )

            if damage_class == "status":
                if boosts_offense:
                    has_setup = True
                else:
                    if slug in SUPPORT_MOVES or ailment in SUPPORT_AILMENTS:
                        has_support = True
                continue

            if ailment == "paralysis":
                has_speed_control = True
            if slug in SUPPORT_MOVES or ailment in SUPPORT_AILMENTS:
                has_support = True

            if not isinstance(base_power, (int, float)) or base_power <= 0:
                continue

            offensive_move_seen = True
            is_stab = bool(types) and move_type in types
            if is_stab and base_power >= 100:
                has_high_power_stab = True
            if is_stab and base_power >= 75:
                stab_powerful += 1
            if not is_stab and base_power >= 120:
                has_high_power_stab = True

        is_primary_attacker = offensive_move_seen and (
            has_high_power_stab
            or stab_powerful >= 2
            or self._ev_indicates_attacker(pokemon)
        )

        if has_speed_control:
            return "Speed control"
        if has_setup:
            return "Setup sweeper"
        if has_support:
            return "Utility support"
        if is_primary_attacker:
            return "Primary attacker"
        return None

    @staticmethod
    def _fallback_move_data(move_name: str) -> Dict[str, Any]:
        return {
            "name": move_name,
            "type": None,
            "damage_class": None,
            "priority": 0,
            "base_power": None,
            "meta": {},
            "stat_changes": [],
        }

    def _get_base_speed(self, pokemon) -> Optional[int]:
        species = pokemon.species or pokemon.name
        entry = self.pikalytics.get_ladder_entry(species)
        if not entry:
            return None
        stats = entry.get("stats", {})
        if isinstance(stats, dict):
            speed = stats.get("spe")
            if isinstance(speed, (int, float)):
                return int(speed)
        return None

    def _entry_speed(self, entry: Dict[str, object]) -> Optional[int]:
        stats = entry.get("stats", {})
        if isinstance(stats, dict):
            speed = stats.get("spe")
            if isinstance(speed, (int, float)):
                return int(speed)
        return None

    def _build_recommendations(
        self,
        team: Team,
        defense_report: Dict[str, object],
        offensive_threats: List[ThreatAssessment],
        contexts: List[PokemonContext],
    ) -> List[str]:
        recommendations: List[str] = list(
            defense_report.get("recommendations", []))
        context_map = {ctx.pokemon: ctx for ctx in contexts}
        if offensive_threats:
            top = offensive_threats[0]
            recommendations.append(
                f"Prep answers for {top.threat} which pressures multiple teammates."
            )

        has_primary_attacker = any(
            (
                self._infer_role(pokemon, context_map.get(pokemon.name))
                in {"Primary attacker", "Setup sweeper"}
            )
            or self._ev_indicates_attacker(pokemon)
            for pokemon in team.pokemon
        )
        if not has_primary_attacker:
            recommendations.append(
                "Team lacks a defined primary attacker; consider adding a sweeper."
            )

        offense_report = self._evaluate_offensive_coverage(contexts)

        if offense_report["gaps"]:
            prioritized = [
                t for t in offense_report["gaps"]
                if t in COMMON_COVERAGE_TYPES
            ] or offense_report["gaps"]
            selected = prioritized[:3]
            gap_descriptions = [
                f"{t.title()} ({TYPE_COVERAGE_HINTS.get(t, 'Add coverage')})"
                for t in selected
            ]
            if gap_descriptions:
                if len(gap_descriptions) == 1:
                    gap_msg = gap_descriptions[0]
                else:
                    gap_msg = ", ".join(gap_descriptions[:-1]) + f" and {gap_descriptions[-1]}"
                recommendations.append(
                    f"Team struggles to hit {gap_msg} super-effectively. Adjust coverage accordingly."
                )

        if offense_report["weak_coverage"]:
            prioritized = [
                t for t in offense_report["weak_coverage"]
                if t in COMMON_COVERAGE_TYPES
            ] or offense_report["weak_coverage"]
            selected = prioritized[:2]
            weak_msg = " and ".join(t.title() for t in selected)
            recommendations.append(
                f"Only one team member covers {weak_msg}. Add redundancy before tournaments."
            )

        return list(dict.fromkeys(recommendations))[:5]

    def _evaluate_offensive_coverage(self, contexts: List[PokemonContext]) -> Dict[str, Any]:
        """Analyze what types the team can effectively hit."""

        coverage_by_type: Dict[str, List[str]] = {t: [] for t in TYPE_ORDER}
        for ctx in contexts:
            for move_slug, move_data in ctx.move_data.items():
                move_type = move_data.get("type")
                base_power = move_data.get("base_power")
                damage_class = (move_data.get("damage_class") or "").lower()

                if (
                    not move_type
                    or damage_class == "status"
                    or not isinstance(base_power, (int, float))
                    or base_power < 50
                ):
                    continue

                for defender_type in TYPE_ORDER:
                    mult = damage_multiplier(move_type, [defender_type])

                    if mult > 1.0:
                        move_name = move_data.get("name") or move_slug
                        coverage_by_type[defender_type].append(
                            f"{ctx.pokemon} ({move_name})"
                        )

        gaps = [t for t, users in coverage_by_type.items() if not users]

        weak_coverage = [
            t for t, users in coverage_by_type.items()
            if len(users) == 1
        ]

        return {
            "coverage_by_type": coverage_by_type,
            "gaps": gaps,
            "weak_coverage": weak_coverage,
        }

    @staticmethod
    def _ev_indicates_attacker(pokemon) -> bool:
        offense_ev = max(pokemon.evs.get("atk", 0), pokemon.evs.get("spa", 0))
        secondary_ev = min(pokemon.evs.get("atk", 0), pokemon.evs.get("spa", 0))
        hp_ev = pokemon.evs.get("hp", 0)
        return offense_ev >= 160 and (hp_ev <= 200 or secondary_ev >= 80)

    @staticmethod
    def _is_physical_attacker(pokemon) -> bool:
        atk_ev = pokemon.evs.get("atk", 0)
        spa_ev = pokemon.evs.get("spa", 0)
        return atk_ev > spa_ev and atk_ev >= 100

    def _team_has_speed_control(self, team: Team) -> bool:
        for pokemon in team.pokemon:
            for move in pokemon.moves:
                if move.strip().lower() in SPEED_CONTROL_MOVES:
                    return True
        return False

"""Team analysis logic combining PokéAPI typings and heuristic scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set

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


@dataclass
class PokemonContext:
    pokemon: str
    types: List[str]
    meta: Optional[PokemonMeta]


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

    def analyze(self, team: Team) -> TeamReport:
        report, _ = self.analyze_with_context(team)
        return report

    def analyze_with_context(self, team: Team) -> tuple[TeamReport, List[PokemonContext]]:
        if team.is_empty():
            raise ValueError("Team is empty; cannot analyze")

        contexts = self._build_context(team)
        defense_report = self._evaluate_defensive_profile(contexts)
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

        summary_bits = [
            f"Detected {len(team.pokemon)} Pokémon",
            f"Top weakness: {defense_report['top_weakness']}" if defense_report["top_weakness"] else "Balanced type chart",
            f"Speed control present" if any("Speed control" in (ins.role or "") for ins in insights) else "No obvious speed control",
        ]
        summary = ". ".join(summary_bits)

        report = TeamReport(
            summary=summary,
            threats=combined_threats,
            pokemon_insights=insights,
            coverage_gaps=defense_report["gap_messages"],
            recommendations=recommendations,
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
            try:
                types = self.pokeapi.get_pokemon_types(species)
            except Exception:  # pragma: no cover - network failures
                types = []
            try:
                meta = self.pikalytics.fetch_pokemon(self.format_slug, species)
            except Exception:  # pragma: no cover - network failures
                meta = None
            contexts.append(PokemonContext(pokemon=pokemon.name, types=types, meta=meta))
        return contexts

    # ------------------------------------------------------------------
    # Defensive coverage
    # ------------------------------------------------------------------
    def _evaluate_defensive_profile(self, contexts: List[PokemonContext]) -> Dict[str, any]:
        weak_counts: Dict[str, int] = {}
        resist_counts: Dict[str, int] = {}
        gap_messages: List[str] = []
        recommendations: List[str] = []
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
            if weak >= 3:
                gap_messages.append(
                    f"{attack_type.title()} offense pressures {weak} team members."
                )
                recommendations.append(
                    f"Consider a {attack_type.title()} resist or immunity to ease this load."
                )
            if resist == 0:
                gap_messages.append(
                    f"No reliable resist for {attack_type.title()} attacks detected."
                )
        top_weakness = max(weak_counts.items(), key=lambda kv: kv[1])[0] if weak_counts else None
        return {
            "weak_counts": weak_counts,
            "resist_counts": resist_counts,
            "gap_messages": gap_messages,
            "recommendations": list(dict.fromkeys(recommendations)),
            "top_weakness": top_weakness,
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
            win_rates: List[float] = data["win_rates"]  # type: ignore[assignment]
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
        ladder_entries = self.pikalytics.iter_ladder_entries(self.ladder_threat_limit)
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
            entry_types = [t.lower() for t in entry.get("types", []) if isinstance(t, str)]
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
                coverage_types = [
                    c.lower() for c in (ctx.meta.offensive_coverage if ctx.meta else [])
                ]
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
                        and self._infer_role(pokemon) != "Speed control"
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
            assessments.append(
                ThreatAssessment(
                    threat=threat_name,
                    pressure=min(0.99, pressure),
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
            role = self._infer_role(pokemon)
            strengths: List[str] = []
            risks: List[str] = []
            if ctx and ctx.meta and ctx.meta.usage_percent:
                strengths.append(
                    f"Seen in {ctx.meta.usage_percent:.1f}% of {self.format_slug} teams"
                )
            if ctx and ctx.meta and ctx.meta.offensive_coverage:
                strengths.append(
                    "Offensive coverage: "
                    + ", ".join(ctx.meta.offensive_coverage)
                )
            if (
                pokemon.tera_type
                and ctx
                and ctx.types
                and pokemon.tera_type.lower() not in ctx.types
            ):
                strengths.append(f"Tera {pokemon.tera_type} offers matchup flexibility")
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

    def _infer_role(self, pokemon) -> Optional[str]:
        move_set = {move.lower() for move in pokemon.moves}
        if move_set & SPEED_CONTROL_MOVES:
            return "Speed control"
        if move_set & SUPPORT_MOVES:
            return "Utility support"
        if any(move.lower() in {"dragon claw", "armor cannon", "play rough"} for move in pokemon.moves):
            return "Primary attacker"
        return None

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
        recommendations: List[str] = list(defense_report.get("recommendations", []))
        if offensive_threats:
            top = offensive_threats[0]
            recommendations.append(
                f"Prep answers for {top.threat} which pressures multiple teammates."
            )

        has_primary_attacker = any(
            self._infer_role(pokemon) == "Primary attacker" for pokemon in team.pokemon
        )
        if not has_primary_attacker:
            recommendations.append(
                "Team lacks a defined primary attacker; consider adding a sweeper."
            )

        return list(dict.fromkeys(recommendations))

# Offensive Threat Analysis Integration Guide

## Overview

You now have two main sources for offensive threat data:

1. **Pikalytics "Common Threats" Section** — Pokémon that beat this Pokémon
2. **Move Coverage Inference** — Determine what types this Pokémon can hit

## Data Sources for Offensive Analysis

### 1. Pikalytics Matchup Data

Each Pokémon page on Pikalytics shows what it struggles against. You need to scrape:

**HTML Structure to target:**
```html
<!-- Look for sections with threat/matchup identifiers -->
<div class="threat-matchup">
  <a href="/pokedex/...">Incineroar</a>
  <span class="win-rate">65%</span>  <!-- How often this beats the Pokemon -->
</div>
```

**What to capture:**
- Threat Pokémon name
- Win rate (as percentage or decimal)
- This tells you: "Incineroar beats this Pokémon 65% of the time"

### 2. Move Coverage Detection

From the moves list you're already scraping, infer offensive coverage:

**High-impact offensive moves by type:**
- **Fire**: Flamethrower, Fire Punch, Will-O-Wisp
- **Water**: Aqua Jet, Hydro Pump, Surf
- **Electric**: Thunderbolt, Thunder, Thunder Wave
- **Psychic**: Psychic, Psyshock
- **Ground**: Earthquake, Earth Power (critical for VGC)
- **Ice**: Ice Beam, Ice Punch, Ice Spinner
- **Fighting**: Close Combat, Focus Blast, Superpower
- **Fairy**: Play Rough, Dazzling Gleam
- **Dark**: Knock Off, Dark Pulse
- **Dragon**: Dragon Claw, Draco Meteor
- **Rock**: Stone Edge, Power Gem

**Why this matters:**
If your team has 5 Pokémon weak to Ground, but an opposing Incineroar has Earthquake... that's a problem. The analyzer finds this.

## How the Analysis Works

### Step 1: Parse Team
```python
team = parse_team(team_text)  # Your existing parser
```

### Step 2: Fetch Metagame Data
```python
analyzer = TeamAnalyzer(format_slug="gen9vgc2025regh")

# For each Pokémon, fetch from Pikalytics
for pokemon in team.pokemon:
    meta = pikalytics_client.fetch_pokemon(format_slug, pokemon.species)
    # meta.common_threats → list of ThreatEntry (Pokemon that beat it)
    # meta.offensive_coverage → list of types this Pokemon can hit
    # meta.moves → move names with usage %
```

### Step 3: Cross-Reference
```python
# For each team member, check what in the meta beats it
pokemon_meta = contexts["Hatterene"]
for threat in pokemon_meta.common_threats:
    # threat.pokemon = "Incineroar"
    # threat.win_rate = 0.65
    
    # If Incineroar is common in meta and beats Hatterene...
    if threat.win_rate >= 0.6:
        add_to_threats("Incineroar threatens Hatterene")
```

### Step 4: Identify Team Weaknesses
```python
# Count how many team members are weak to common threats
offensive_threats = []

for meta_pokemon in top_meta_pokemon:
    # Get what types/Pokémon commonly use
    threats_to_team = count_vulnerable_members(meta_pokemon, team)
    
    if threats_to_team >= 3:
        offensive_threats.append({
            "threat": meta_pokemon,
            "weak_members": threats_to_team,
            "pressure": threats_to_team / 6
        })
```

## Example Analysis Output

For your Hatterene team:

```
Offensive Threats Detected:
1. Incineroar (pressure: 0.83) — Threatens Hatterene, Amoonguss, Armarouge
   Reason: Common Fire-type STAB in 45% of meta teams, learns Fire Punch
   
2. Landorus-I (pressure: 0.67) — Threatens Armarouge, Dragonite
   Reason: Learns Earthquake, present in 28% of meta, outspeeds Tornadus

Defensive Gaps Already Identified:
- Fire-type offense pressures 3 members
- Ground-type offense pressures 4 members
```

## Integration Checklist

- [ ] Update `pikalytics.py` to parse threat sections (HTML structure may vary)
- [ ] Implement `_parse_common_threats()` to extract matchup data
- [ ] Add `_infer_offensive_coverage()` to map moves → types
- [ ] Update `PokemonMeta` dataclass with `common_threats` and `offensive_coverage` fields
- [ ] Enhance `TeamAnalyzer._evaluate_offensive_threats()` to cross-reference
- [ ] Test scraping on live Pikalytics pages (format_slug affects URLs)
- [ ] Add rate-limiting between requests (respect their server)

## Scraping Tips

**Before scraping Pikalytics directly:**
1. Check their robots.txt: `https://www.pikalytics.com/robots.txt`
2. Add delays between requests: `time.sleep(1.5)` minimum
3. Use a descriptive User-Agent header
4. Consider caching responses locally (15-min TTL suggested)

**If HTML structure changes:**
- Use browser DevTools (F12) to inspect elements
- Right-click element → Inspect
- Look for `id`, `class`, or data attributes
- Update CSS selectors in BeautifulSoup `.find()` calls

## Alternative Approaches

If scraping Pikalytics proves fragile:

1. **Smogon Stats API** — Less VGC-specific but more stable
2. **Manual Dataset** — Curate top 20 metagame Pokémon + threats
3. **Damage Calculator** — Use PokéAPI + damage formulas to compute matchups
4. **Tournament Results** — Parse Limitless VGC or VGC Stats APIs for real team data

## Testing

```python
# Test with your example team
team_text = """
Hatterene @ Safety Goggles
Ability: Magic Bounce
...
"""

analyzer = TeamAnalyzer()
team = parse_team(team_text)
report = analyzer.analyze(team)

# Check threats list
print(report.threats)
# Should show Incineroar, Landorus, and other meta threats
```

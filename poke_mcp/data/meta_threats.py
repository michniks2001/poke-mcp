"""Pre-curated meta threats keyed by attacking type."""

TYPE_META_THREATS = {
    "fighting": [
        {
            "name": "Sneasler",
            "types": ["fighting", "poison"],
            "notes": "Unburden sweeper that punishes bulky cores",
        },
        {
            "name": "Iron Hands",
            "types": ["fighting", "electric"],
            "notes": "Slow tank that overwhelms defensive teams",
        },
        {
            "name": "Terrakion",
            "types": ["rock", "fighting"],
            "notes": "Fast Close Combat user that shreds neutral targets",
        },
    ],
    "fairy": [
        {
            "name": "Flutter Mane",
            "types": ["ghost", "fairy"],
            "notes": "Specs sets delete Dragons and Darks",
        },
        {
            "name": "Iron Valiant",
            "types": ["fairy", "fighting"],
            "notes": "Mixed coverage with Booster Energy",
        },
    ],
    "fire": [
        {
            "name": "Chi-Yu",
            "types": ["fire", "dark"],
            "notes": "Beads of Ruin breaks even resists",
        },
        {
            "name": "Incineroar",
            "types": ["fire", "dark"],
            "notes": "Intimidate pivot that grinds teams down",
        },
    ],
    "water": [
        {
            "name": "Walking Wake",
            "types": ["water", "dragon"],
            "notes": "Sun-boosted waves overwhelm Fire/Ground cores",
        },
        {
            "name": "Palafin",
            "types": ["water"],
            "notes": "Hero form Jet Punch sweeps weakened teams",
        },
    ],
    "electric": [
        {
            "name": "Regieleki",
            "types": ["electric"],
            "notes": "Fast Volt Switch pressure",
        },
        {
            "name": "Raging Bolt",
            "types": ["electric", "dragon"],
            "notes": "Thunderclap punishes speed control",
        },
    ],
    "ice": [
        {
            "name": "Chien-Pao",
            "types": ["dark", "ice"],
            "notes": "Sword of Ruin amplifies Ice Spinner",
        },
        {
            "name": "Iron Bundle",
            "types": ["ice", "water"],
            "notes": "Blazing fast Freeze-Dry coverage",
        },
    ],
    "ground": [
        {
            "name": "Landorus-Therian",
            "types": ["ground", "flying"],
            "notes": "Intimidate + Earthquake staple",
        },
        {
            "name": "Great Tusk",
            "types": ["ground", "fighting"],
            "notes": "Rapid Spin utility with Headlong Rush",
        },
    ],
    "dragon": [
        {
            "name": "Gouging Fire",
            "types": ["dragon", "fire"],
            "notes": "Protosynthesis-boosted Dragon Claw",
        },
        {
            "name": "Roaring Moon",
            "types": ["dragon", "dark"],
            "notes": "Acrobatics sweeper once Booster pops",
        },
    ],
    "ghost": [
        {
            "name": "Gholdengo",
            "types": ["steel", "ghost"],
            "notes": "Make It Rain pressures neutral targets",
        },
        {
            "name": "Flutter Mane",
            "types": ["ghost", "fairy"],
            "notes": "Ghost STAB ignores Fake Out",
        },
    ],
    "dark": [
        {
            "name": "Kingambit",
            "types": ["dark", "steel"],
            "notes": "Supreme Overlord endgames",
        },
        {
            "name": "Chi-Yu",
            "types": ["fire", "dark"],
            "notes": "Dark Pulse punishes Psychics",
        },
    ],
}

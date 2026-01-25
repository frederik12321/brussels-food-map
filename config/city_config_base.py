"""
Base City Configuration for Local Food Map

This module defines the base structure for city-specific configurations.
To adapt this project for a new city:
1. Copy this file to config/your_city_config.py
2. Fill in your city's specific data
3. Update src/city_context.py to import from your config

The scoring algorithm will automatically use your city's context data.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class District:
    """A district/neighborhood in the city."""
    lat: float
    lng: float
    tier: str  # e.g., "tourist_heavy", "local_foodie", "diaspora_hub", "underexplored"
    cuisine_affinity: List[str] = field(default_factory=list)
    radius: float = 0.5  # km


@dataclass
class LocalStreet:
    """A street known for good local food."""
    name: str
    lat: float
    lng: float
    radius: float = 0.15  # km


@dataclass
class DiasporaHub:
    """A diaspora community hub with associated cuisines."""
    name: str
    commune: str  # District name
    lat: float
    lng: float
    cuisines: List[str] = field(default_factory=list)


@dataclass
class CityConfig:
    """
    Complete configuration for a city's food map.

    This defines all the local context needed for the reranking algorithm:
    - Geographic center and bounds
    - Districts/neighborhoods with their characteristics
    - Local food streets
    - Tourist trap zones
    - Diaspora communities
    - Local guide recognition (Michelin, local guides, etc.)
    - Chain restaurant patterns
    - Non-restaurant exclusions
    """

    # Basic city info
    city_name: str
    country: str
    center_lat: float
    center_lng: float
    default_zoom: int = 13

    # Tourist epicenter (where the tourist trap penalty is strongest)
    tourist_epicenter: Tuple[float, float] = (0, 0)
    tourist_epicenter_name: str = "City Center"

    # Districts/neighborhoods/communes
    districts: Dict[str, District] = field(default_factory=dict)

    # Special neighborhoods within districts (more granular)
    neighborhoods: Dict[str, District] = field(default_factory=dict)

    # Local food streets (bonus for restaurants on these streets)
    local_streets: List[LocalStreet] = field(default_factory=list)

    # Tier weights for scoring
    tier_weights: Dict[str, float] = field(default_factory=lambda: {
        "tourist_heavy": -0.15,
        "tourist_trap": -0.20,
        "eu_bubble": -0.05,  # For cities with expat bubbles
        "mixed": 0.0,
        "diaspora_hub": 0.10,
        "local_foodie": 0.08,
        "underexplored": 0.12,
    })

    # Diaspora authenticity mapping
    # Maps cuisine -> list of districts where that cuisine is historically authentic
    diaspora_authenticity: Dict[str, List[DiasporaHub]] = field(default_factory=dict)

    # Local authentic cuisines (e.g., Belgian in Brussels, Lyonnaise in Lyon)
    local_cuisines: List[str] = field(default_factory=list)
    local_cuisine_bonus: float = 0.03

    # Chain restaurant patterns (regex patterns)
    chain_patterns: List[str] = field(default_factory=list)

    # Non-restaurant shops to exclude (e.g., chocolate shops in Brussels)
    non_restaurant_patterns: List[str] = field(default_factory=list)

    # Michelin starred restaurants (name pattern -> star count)
    michelin_stars: Dict[str, int] = field(default_factory=dict)

    # Bib Gourmand restaurants (name patterns)
    bib_gourmand: List[str] = field(default_factory=list)

    # Local food guides (name -> recognized)
    local_guides: Dict[str, List[str]] = field(default_factory=dict)

    # Cuisine specificity mapping (regional cuisines get bonus over generic)
    # e.g., "Sichuan" > "Chinese", "Neapolitan" > "Italian"
    cuisine_specificity: Dict[str, float] = field(default_factory=dict)

    # Reddit/local forum subreddit for community endorsements
    reddit_subreddit: Optional[str] = None

    # Time zone for opening hours parsing
    timezone: str = "UTC"


# Default global cuisine specificity (can be overridden per city)
DEFAULT_CUISINE_SPECIFICITY = {
    # Asian specificity
    "Sichuan": 1.0, "Szechuan": 1.0, "Cantonese": 0.9, "Hunan": 1.0,
    "Taiwanese": 0.9, "Shanghainese": 1.0, "Dim Sum": 0.8, "Pekinese": 0.9, "Hakka": 1.0,
    # Japanese specificity
    "Ramen": 0.8, "Izakaya": 0.9, "Kaiseki": 1.0, "Omakase": 1.0,
    "Yakitori": 0.9, "Tonkatsu": 0.9, "Okonomiyaki": 1.0,
    # Korean
    "Korean BBQ": 0.8, "Hansik": 1.0,
    # Indian specificity
    "South Indian": 0.9, "Punjabi": 0.9, "Gujarati": 1.0, "Bengali": 1.0,
    "Kerala": 1.0, "Chettinad": 1.0, "Hyderabadi": 0.9,
    # Italian specificity
    "Neapolitan": 0.9, "Sicilian": 1.0, "Tuscan": 0.9, "Roman": 0.9,
    "Venetian": 1.0, "Sardinian": 1.0, "Piedmontese": 1.0, "Emilian": 1.0,
    # Spanish
    "Basque": 1.0, "Catalan": 0.9, "Galician": 1.0, "Andalusian": 0.9,
    # French
    "Lyonnaise": 0.9, "Provençal": 0.9, "Alsatian": 0.9, "Breton": 0.9,
    "Burgundian": 1.0, "Savoyard": 0.9,
    # Mexican
    "Oaxacan": 1.0, "Yucatecan": 1.0, "Jalisciense": 1.0,
    # Middle Eastern
    "Levantine": 0.8, "Palestinian": 1.0, "Yemeni": 1.0, "Kurdish": 1.0,
    # African
    "Ethiopian": 0.8, "Eritrean": 0.9, "Senegalese": 1.0, "Ivorian": 1.0,
    "Cameroonian": 1.0, "Ghanaian": 1.0, "Nigerian": 0.9,
    # Generic cuisines (no bonus)
    "Chinese": 0, "Japanese": 0, "Italian": 0, "French": 0, "Indian": 0,
    "Thai": 0, "Vietnamese": 0, "Mexican": 0, "American": 0,
    "Mediterranean": 0, "Asian": 0, "European": 0, "International": 0, "Fusion": 0,
}

# Default chain patterns (international chains)
DEFAULT_CHAIN_PATTERNS = [
    r"mcdonald", r"burger king", r"kfc", r"subway", r"domino",
    r"pizza hut", r"starbucks", r"five guys", r"wagamama",
    r"nando", r"pizza express", r"vapiano",
]

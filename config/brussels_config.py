"""
Brussels City Configuration

This is the reference implementation showing how to configure a city
for the Local Food Map project. Brussels has rich diaspora communities,
tourist trap zones, and local foodie neighborhoods.

Use this as a template for your own city!
"""

from city_config_base import (
    CityConfig, District, LocalStreet, DiasporaHub,
    DEFAULT_CUISINE_SPECIFICITY, DEFAULT_CHAIN_PATTERNS
)


# Brussels-specific configuration
BRUSSELS_CONFIG = CityConfig(
    city_name="Brussels",
    country="Belgium",
    center_lat=50.8503,
    center_lng=4.3517,
    default_zoom=13,

    # Grand Place is the tourist epicenter
    tourist_epicenter=(50.8467, 4.3525),
    tourist_epicenter_name="Grand Place",

    # The 19 Brussels communes
    districts={
        "Anderlecht": District(lat=50.8333, lng=4.3072, tier="underexplored"),
        "Auderghem": District(lat=50.8167, lng=4.4333, tier="local_foodie"),
        "Berchem-Sainte-Agathe": District(lat=50.8667, lng=4.2917, tier="underexplored"),
        "Bruxelles": District(lat=50.8503, lng=4.3517, tier="tourist_heavy"),
        "Etterbeek": District(lat=50.8333, lng=4.3833, tier="eu_bubble"),
        "Evere": District(lat=50.8667, lng=4.4000, tier="underexplored"),
        "Forest": District(lat=50.8103, lng=4.3242, tier="underexplored"),
        "Ganshoren": District(lat=50.8750, lng=4.3083, tier="underexplored"),
        "Ixelles": District(lat=50.8275, lng=4.3697, tier="mixed"),
        "Jette": District(lat=50.8792, lng=4.3250, tier="underexplored"),
        "Koekelberg": District(lat=50.8625, lng=4.3292, tier="underexplored"),
        "Molenbeek-Saint-Jean": District(lat=50.8547, lng=4.3286, tier="diaspora_hub"),
        "Saint-Gilles": District(lat=50.8261, lng=4.3456, tier="diaspora_hub"),
        "Saint-Josse-ten-Noode": District(lat=50.8553, lng=4.3703, tier="diaspora_hub"),
        "Schaerbeek": District(lat=50.8653, lng=4.3778, tier="diaspora_hub"),
        "Uccle": District(lat=50.8000, lng=4.3333, tier="local_foodie"),
        "Watermael-Boitsfort": District(lat=50.7958, lng=4.4125, tier="local_foodie"),
        "Woluwe-Saint-Lambert": District(lat=50.8417, lng=4.4333, tier="local_foodie"),
        "Woluwe-Saint-Pierre": District(lat=50.8333, lng=4.4500, tier="local_foodie"),
    },

    # Special neighborhoods with more granular classification
    neighborhoods={
        "Matongé": District(
            lat=50.8295, lng=4.3680, tier="local_foodie",
            cuisine_affinity=["Congolese", "African"], radius=0.3
        ),
        "Châtelain": District(
            lat=50.8235, lng=4.3600, tier="local_foodie",
            cuisine_affinity=["French", "Belgian", "Brunch"]
        ),
        "Sainte-Catherine": District(
            lat=50.8511, lng=4.3461, tier="local_foodie",
            cuisine_affinity=["Seafood", "Belgian"]
        ),
        "Marolles": District(
            lat=50.8389, lng=4.3444, tier="local_foodie",
            cuisine_affinity=["Belgian"]
        ),
        "Rue des Bouchers": District(
            lat=50.8478, lng=4.3544, tier="tourist_trap",
            cuisine_affinity=[]
        ),
        "Grand Place": District(
            lat=50.8467, lng=4.3525, tier="tourist_trap",
            cuisine_affinity=[]
        ),
        "European Quarter": District(
            lat=50.8427, lng=4.3827, tier="eu_bubble",
            cuisine_affinity=[]
        ),
        "Flagey": District(
            lat=50.8275, lng=4.3720, tier="local_foodie",
            cuisine_affinity=["Belgian", "Brunch"]
        ),
        "Parvis Saint-Gilles": District(
            lat=50.8270, lng=4.3465, tier="local_foodie",
            cuisine_affinity=["French", "Belgian"]
        ),
        "Dansaert": District(
            lat=50.8505, lng=4.3430, tier="local_foodie",
            cuisine_affinity=["Belgian", "French"]
        ),
    },

    # Local food streets (diaspora hubs and local favorites)
    local_streets=[
        # Maghreb hubs
        LocalStreet("Chaussée de Gand", 50.8570, 4.3320, 0.30),
        LocalStreet("Rue de Brabant", 50.8555, 4.3595, 0.25),
        LocalStreet("Foodmet/Clemenceau", 50.8400, 4.3180, 0.25),
        # Turkish "Little Anatolia"
        LocalStreet("Chaussée de Haecht", 50.8570, 4.3680, 0.30),
        # Congolese Matongé
        LocalStreet("Chaussée de Wavre (Matongé)", 50.8300, 4.3690, 0.15),
        LocalStreet("Galerie d'Ixelles", 50.8295, 4.3680, 0.08),
        # Traditional Belgian
        LocalStreet("Rue de Flandre", 50.8530, 4.3450, 0.15),
        LocalStreet("Parvis de Saint-Gilles", 50.8265, 4.3470, 0.12),
    ],

    # Belgian local cuisines
    local_cuisines=["Belgian", "Flemish", "Walloon"],
    local_cuisine_bonus=0.03,

    # Belgian chain patterns
    chain_patterns=DEFAULT_CHAIN_PATTERNS + [
        r"quick", r"panos", r"exki", r"le pain quotidien",
        r"paul", r"class'croute", r"bavet", r"balls & glory",
        r"ellis gourmet", r"manhattn", r"delitraiteur", r"o'tacos",
    ],

    # Belgian chocolate shops (not restaurants)
    non_restaurant_patterns=[
        r"\bcorné\b", r"\bneuhaus\b", r"\bgodiva\b", r"\bleonidas\b",
        r"\bpierre marcolini\b", r"\bmarcolini\b", r"\bgaller\b", r"\bwittamer\b",
        r"\bchocolatier\b", r"\bchocolate shop\b", r"\bpralines\b",
    ],

    # Michelin starred restaurants in Brussels (2024/2025)
    michelin_stars={
        "bozar restaurant": 2,
        "comme chez soi": 2,
        "villa in the sky": 2,
        "chalet de la forêt": 2,
        "barge": 1,
        "da mimmo": 1,
        "eliane": 1,
        "humus x hortense": 1,
        "kamo": 1,
        "la canne en ville": 1,
        "villa lorraine": 1,
        "le pigeon noir": 1,
        "menssa": 1,
        "senzanome": 1,
    },

    # Bib Gourmand restaurants
    bib_gourmand=[
        "crab club", "humphrey", "kolya", "les brigittines",
        "maison du luxembourg", "notos", "orphyse chaussette",
        "pablo's", "tero", "wine in the city",
    ],

    # Local guides (Gault&Millau for Belgium)
    local_guides={
        "gault_millau": [
            "le chalet de la forêt", "bon-bon", "la villa lorraine",
            "comme chez soi", "sea grill", "san sablon",
        ],
    },

    # Reddit subreddit for community endorsements
    reddit_subreddit="brussels",

    # Timezone
    timezone="Europe/Brussels",

    # Use default cuisine specificity + any Brussels-specific additions
    cuisine_specificity=DEFAULT_CUISINE_SPECIFICITY,
)

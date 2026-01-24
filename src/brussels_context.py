"""
Brussels-Specific Context Data

Contains commune boundaries, classifications, and cultural mapping
for Brussels-specific restaurant reranking.
"""

import math

# Grand Place coordinates (tourist epicenter)
GRAND_PLACE = (50.8467, 4.3525)

# Place Schuman (EU bubble center)
PLACE_SCHUMAN = (50.8427, 4.3827)

# Brussels 19 communes with approximate center coordinates
COMMUNES = {
    "Anderlecht": {"lat": 50.8333, "lng": 4.3072, "tier": "underexplored"},
    "Auderghem": {"lat": 50.8167, "lng": 4.4333, "tier": "local_foodie"},
    "Berchem-Sainte-Agathe": {"lat": 50.8667, "lng": 4.2917, "tier": "underexplored"},
    "Bruxelles": {"lat": 50.8503, "lng": 4.3517, "tier": "tourist_heavy"},  # City center
    "Etterbeek": {"lat": 50.8333, "lng": 4.3833, "tier": "eu_bubble"},
    "Evere": {"lat": 50.8667, "lng": 4.4000, "tier": "underexplored"},
    "Forest": {"lat": 50.8103, "lng": 4.3242, "tier": "underexplored"},
    "Ganshoren": {"lat": 50.8750, "lng": 4.3083, "tier": "underexplored"},
    "Ixelles": {"lat": 50.8275, "lng": 4.3697, "tier": "mixed"},  # Has both Matongé and Châtelain
    "Jette": {"lat": 50.8792, "lng": 4.3250, "tier": "underexplored"},
    "Koekelberg": {"lat": 50.8625, "lng": 4.3292, "tier": "underexplored"},
    "Molenbeek-Saint-Jean": {"lat": 50.8547, "lng": 4.3286, "tier": "diaspora_hub"},
    "Saint-Gilles": {"lat": 50.8261, "lng": 4.3456, "tier": "diaspora_hub"},
    "Saint-Josse-ten-Noode": {"lat": 50.8553, "lng": 4.3703, "tier": "diaspora_hub"},
    "Schaerbeek": {"lat": 50.8653, "lng": 4.3778, "tier": "diaspora_hub"},
    "Uccle": {"lat": 50.8000, "lng": 4.3333, "tier": "local_foodie"},
    "Watermael-Boitsfort": {"lat": 50.7958, "lng": 4.4125, "tier": "local_foodie"},
    "Woluwe-Saint-Lambert": {"lat": 50.8417, "lng": 4.4333, "tier": "local_foodie"},
    "Woluwe-Saint-Pierre": {"lat": 50.8333, "lng": 4.4500, "tier": "local_foodie"},
}

# Special neighborhoods within communes
NEIGHBORHOODS = {
    "Matongé": {"commune": "Ixelles", "lat": 50.8280, "lng": 4.3680, "tier": "local_foodie", "cuisine_affinity": ["Congolese", "African"]},
    "Châtelain": {"commune": "Ixelles", "lat": 50.8245, "lng": 4.3625, "tier": "local_foodie", "cuisine_affinity": ["French", "Belgian", "Brunch"]},
    "Sainte-Catherine": {"commune": "Bruxelles", "lat": 50.8511, "lng": 4.3461, "tier": "local_foodie", "cuisine_affinity": ["Seafood", "Belgian"]},
    "Marolles": {"commune": "Bruxelles", "lat": 50.8389, "lng": 4.3444, "tier": "local_foodie", "cuisine_affinity": ["Belgian"]},
    "Saint-Boniface": {"commune": "Ixelles", "lat": 50.8308, "lng": 4.3672, "tier": "local_foodie", "cuisine_affinity": ["Belgian", "French"]},
    "Rue des Bouchers": {"commune": "Bruxelles", "lat": 50.8478, "lng": 4.3544, "tier": "tourist_trap", "cuisine_affinity": []},
    "Grand Place": {"commune": "Bruxelles", "lat": 50.8467, "lng": 4.3525, "tier": "tourist_trap", "cuisine_affinity": []},
    "European Quarter": {"commune": "Etterbeek", "lat": 50.8427, "lng": 4.3827, "tier": "eu_bubble", "cuisine_affinity": []},
    "Gare du Nord": {"commune": "Schaerbeek", "lat": 50.8597, "lng": 4.3614, "tier": "mixed", "cuisine_affinity": ["Turkish", "Middle Eastern"]},
    "Flagey": {"commune": "Ixelles", "lat": 50.8275, "lng": 4.3720, "tier": "local_foodie", "cuisine_affinity": ["Belgian", "Brunch"]},
    "Parvis Saint-Gilles": {"commune": "Saint-Gilles", "lat": 50.8270, "lng": 4.3465, "tier": "local_foodie", "cuisine_affinity": ["French", "Belgian"]},
    "Dansaert": {"commune": "Bruxelles", "lat": 50.8505, "lng": 4.3430, "tier": "local_foodie", "cuisine_affinity": ["Belgian", "French"]},
    "Sablon": {"commune": "Bruxelles", "lat": 50.8420, "lng": 4.3550, "tier": "mixed", "cuisine_affinity": ["French", "Belgian"]},
}

# Local streets known for good food (not on tourist maps)
# These are streets where locals go - bonus for restaurants on these streets
LOCAL_FOOD_STREETS = [
    # Saint-Gilles hidden gems
    {"name": "Rue de Moscou", "lat": 50.8265, "lng": 4.3445, "radius": 0.15},
    {"name": "Rue Vanderschrick", "lat": 50.8245, "lng": 4.3435, "radius": 0.15},
    {"name": "Rue du Fort", "lat": 50.8255, "lng": 4.3490, "radius": 0.15},
    {"name": "Chaussée de Charleroi", "lat": 50.8300, "lng": 4.3520, "radius": 0.20},

    # Ixelles local spots
    {"name": "Rue Lesbroussart", "lat": 50.8265, "lng": 4.3755, "radius": 0.15},
    {"name": "Rue du Page", "lat": 50.8235, "lng": 4.3580, "radius": 0.15},
    {"name": "Rue Américaine", "lat": 50.8231, "lng": 4.3591, "radius": 0.12},
    {"name": "Rue de la Paix", "lat": 50.8295, "lng": 4.3665, "radius": 0.12},

    # Schaerbeek local
    {"name": "Rue Josaphat", "lat": 50.8580, "lng": 4.3780, "radius": 0.20},
    {"name": "Place Colignon", "lat": 50.8625, "lng": 4.3720, "radius": 0.15},

    # Forest hidden
    {"name": "Rue du Dries", "lat": 50.8130, "lng": 4.3220, "radius": 0.15},

    # Anderlecht local
    {"name": "Rue Wayez", "lat": 50.8395, "lng": 4.3095, "radius": 0.15},

    # Jette local
    {"name": "Rue Léon Théodor", "lat": 50.8780, "lng": 4.3280, "radius": 0.15},

    # Saint-Josse authentic
    {"name": "Chaussée de Haecht", "lat": 50.8570, "lng": 4.3680, "radius": 0.20},
]

# Commune tier weights for scoring
TIER_WEIGHTS = {
    "tourist_heavy": -0.15,      # Penalty for tourist traps
    "tourist_trap": -0.20,       # Strong penalty
    "diaspora_hub": 0.15,        # Bonus for authentic diaspora areas
    "local_foodie": 0.10,        # Bonus for quality local areas
    "underexplored": 0.12,       # Boost visibility of underrepresented communes
    "eu_bubble": -0.05,          # Slight penalty for EU bubble
    "mixed": 0.0,                # Neutral
}

# Diaspora cuisine-commune authenticity matrix
# Higher score = stronger authenticity signal
DIASPORA_AUTHENTICITY = {
    "Congolese": {"Ixelles": 0.9, "Saint-Gilles": 0.6, "Schaerbeek": 0.4},
    "African": {"Ixelles": 0.8, "Saint-Gilles": 0.6, "Schaerbeek": 0.5, "Molenbeek-Saint-Jean": 0.4},
    "Moroccan": {"Molenbeek-Saint-Jean": 0.9, "Saint-Gilles": 0.8, "Saint-Josse-ten-Noode": 0.7, "Schaerbeek": 0.7},
    "Turkish": {"Saint-Josse-ten-Noode": 0.9, "Schaerbeek": 0.8, "Molenbeek-Saint-Jean": 0.6},
    "Middle Eastern": {"Saint-Josse-ten-Noode": 0.8, "Schaerbeek": 0.7, "Molenbeek-Saint-Jean": 0.6},
    "Lebanese": {"Saint-Josse-ten-Noode": 0.7, "Ixelles": 0.6, "Saint-Gilles": 0.5},
    "Ethiopian": {"Bruxelles": 0.7, "Ixelles": 0.6},  # Near Sainte-Catherine
    "Portuguese": {"Saint-Gilles": 0.8, "Ixelles": 0.6},
    "Vietnamese": {"Bruxelles": 0.6, "Ixelles": 0.5},
    "Chinese": {"Bruxelles": 0.5, "Ixelles": 0.4},
    "Indian": {"Ixelles": 0.5, "Saint-Gilles": 0.4},
}

# Belgian traditional cuisine authenticity
BELGIAN_AUTHENTICITY = {
    "Belgian": {"Anderlecht": 0.9, "Schaerbeek": 0.8, "Forest": 0.8, "Bruxelles": 0.5},
    "Seafood": {"Bruxelles": 0.8},  # Sainte-Catherine area
    "French": {"Ixelles": 0.7, "Uccle": 0.7, "Saint-Gilles": 0.6},
}

# Known chain restaurants in Belgium
CHAIN_PATTERNS = [
    r"mcdonald", r"burger king", r"quick", r"kfc", r"subway", r"domino",
    r"pizza hut", r"starbucks", r"panos", r"exki", r"le pain quotidien",
    r"paul", r"class'croute", r"pizza express", r"vapiano", r"wagamama",
    r"nando", r"five guys", r"pitaya", r"sushi shop", r"planet sushi",
    r"bavet", r"balls & glory", r"ellis gourmet", r"manhattn",
    r"delitraiteur", r"o'tacos", r"frituur", r"fritland",
]

# Michelin starred restaurants (Brussels Capital Region)
# Updated for 2024/2025 official Michelin Guide
MICHELIN_STARS = {
    # 2 stars - Exceptional cooking, worth a detour
    "bozar restaurant": 2,
    "karen torosyan": 2,  # Chef at Bozar
    "comme chez soi": 2,
    # Note: "la paix" pattern needs exact match - handled specially below
    "villa in the sky": 2,
    "chalet de la forêt": 2,
    # 1 star - High-quality cooking, worth a stop
    "barge": 1,
    "da mimmo": 1,
    "eliane": 1,
    "humus x hortense": 1,  # Also Green Star
    "humus hortense": 1,
    "kamo": 1,
    "la canne en ville": 1,
    "canne en ville": 1,
    "villa lorraine": 1,
    "le pigeon noir": 1,
    "pigeon noir": 1,
    "menssa": 1,
    "senzanome": 1,
}

# Bib Gourmand (Michelin - good quality, good value)
# Updated for 2024/2025 official Michelin Guide
BIB_GOURMAND = [
    # New additions 2025
    "au repos de la montagne",
    "repos de la montagne",
    "babam",
    "lune siamoise",
    # Confirmed 2024/2025
    "anju",
    "appel thaï",
    "appel thai",
    "car bon",
    "de maurice à olivier",
    "maurice à olivier",
    "french kiss",
    "jb",
    "jb sushi",
    "kline",
    "la branche d'olivier",
    "branche d'olivier",
    "la charcuterie",
    "l'épicerie nomad",
    "epicerie nomad",
    "le tournant",
    "tournant",
    "le variétés",
    "variétés",
    "les potes en toque",
    "potes en toque",
    "maza'j",
    "mazaj",
    "nénu",
    "nenu",
    "osteria bolognese",
    "saint boniface",
    "selecto",
    "le selecto",
    "st. kilda",
    "st kilda",
    "strofilia",
    "villa singha",
    "yokatomo",
    "yoka tomo",
]

# Gault & Millau recognized restaurants (15+ points)
# Updated for Gault&Millau Belux Guide 2026
# Note: This list is separate from Michelin - restaurants can have both
GAULT_MILLAU = [
    # 17.5/20 - The Absolute Top
    "bozar restaurant",
    "karen torosyan",
    "comme chez soi",
    # Note: "la paix" handled specially in function (17.5/20)
    # 17/20 - Excellent
    "villa in the sky",
    "villa lorraine",
    "menssa",
    "eliane",
    # 16-16.5/20 - Excellent Tables
    "humus x hortense",
    "humus hortense",
    "kamo",
    "senzanome",
    # 15-15.5/20 - Notable High Scorers
    "barge",
    "la canne en ville",
    "canne en ville",
    "chalet de la forêt",
    "le chalet de la forêt",
    "le stirwen",
    "stirwen",
    "chaga",
    # Special Award Winners 2026
    "quartz",  # Young Chef of the Year
    "kartouche",  # Discovery of the Year
    "pénar",  # Price/Pleasure of the Year
    "penar",
    "mobi",  # H!P of the Year
    # H!P Selection (trendy/gourmet concepts)
    "aster",
    "nona pizza",
    "nona pasta",
    "old boy",
    "fernand obb",
    "bombay bbq",
    "ramen nobu",
    # Classic Brussels establishments (traditionally recognized)
    "sea grill",
    "san daniele",
    "les brigittines",
    "la quincaillerie",
    "toucan sur mer",
    "toucan brasserie",
    "la truffe noire",
    "l'ecailler du palais",
    "humphrey",
    "brinz'l",
    "le clan des belges",
    "kolya",
    "fin de siècle",
    "nuetnigenough",
    "nüetnigenough",
    "in 't spinnekopke",
    "la roue d'or",
    "viva m'boma",
    "belga queen",
    "wine bar sablon",
    "wine bar des marolles",
]


import re

def _matches_pattern(name_lower, pattern):
    """Check if pattern matches as a whole word or at word boundaries."""
    # Escape special regex characters in pattern
    escaped = re.escape(pattern)
    # Match pattern at word boundaries (start/end of string or non-alphanumeric)
    regex = r'(^|[^a-z])' + escaped + r'($|[^a-z])'
    return bool(re.search(regex, name_lower))


def has_michelin_recognition(name):
    """Check if restaurant has Michelin stars. Returns star count or 0."""
    if not name:
        return 0
    name_lower = name.lower()

    # Special case: "La Paix" must be exact match (not "Glacier De La Paix")
    if name_lower == "la paix":
        return 2

    for pattern, stars in MICHELIN_STARS.items():
        if _matches_pattern(name_lower, pattern):
            return stars
    return 0


def has_gault_millau(name):
    """Check if restaurant is Gault & Millau recognized."""
    if not name:
        return False
    name_lower = name.lower()

    # Special case: "La Paix" must be exact match
    if name_lower == "la paix":
        return True

    for pattern in GAULT_MILLAU:
        if _matches_pattern(name_lower, pattern):
            return True
    return False


def has_bib_gourmand(name):
    """Check if restaurant has Michelin Bib Gourmand."""
    if not name:
        return False
    name_lower = name.lower()
    for pattern in BIB_GOURMAND:
        if _matches_pattern(name_lower, pattern):
            return True
    return False


# Tourist trap indicators in review text
TOURIST_KEYWORDS = [
    "tourist", "touristique", "toerist",
    "near grand place", "près de la grand place",
    "walking tour", "visite guidée",
    "guide recommended", "recommandé par le guide",
    "trap", "piège", "overpriced", "trop cher",
    "avoid", "éviter", "vermijd",
]

# Authenticity indicators
AUTHENTICITY_KEYWORDS = {
    "general": ["authentic", "authentique", "echt", "local", "traditionnel", "traditional"],
    "belgian": ["stoofvlees", "waterzooi", "moules", "mosselen", "frites", "carbonade", "vol-au-vent"],
    "congolese": ["moambe", "saka saka", "fufu", "madesu", "pondu", "chikwanga", "liboke"],
    "moroccan": ["tajine", "couscous", "pastilla", "harira", "mechoui", "kefta"],
    "turkish": ["pide", "lahmacun", "iskender", "döner", "kebab", "köfte", "mantı"],
    "ethiopian": ["injera", "doro wat", "tibs", "kitfo"],
}


def haversine_distance(lat1, lng1, lat2, lng2):
    """Calculate distance between two points in km."""
    R = 6371  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def get_commune(lat, lng):
    """Determine which commune a location is in (approximate, by nearest center)."""
    min_dist = float('inf')
    nearest_commune = "Bruxelles"

    for commune, data in COMMUNES.items():
        dist = haversine_distance(lat, lng, data["lat"], data["lng"])
        if dist < min_dist:
            min_dist = dist
            nearest_commune = commune

    return nearest_commune


def get_neighborhood(lat, lng):
    """Check if location is in a special neighborhood."""
    for name, data in NEIGHBORHOODS.items():
        dist = haversine_distance(lat, lng, data["lat"], data["lng"])
        # Neighborhoods are small, use 0.5km radius
        if dist < 0.5:
            return name, data
    return None, None


def distance_to_grand_place(lat, lng):
    """Calculate distance to Grand Place in km."""
    return haversine_distance(lat, lng, GRAND_PLACE[0], GRAND_PLACE[1])


def distance_to_eu_quarter(lat, lng):
    """Calculate distance to Place Schuman (EU quarter) in km."""
    return haversine_distance(lat, lng, PLACE_SCHUMAN[0], PLACE_SCHUMAN[1])


def is_on_local_street(lat, lng):
    """Check if restaurant is on a known local food street."""
    for street in LOCAL_FOOD_STREETS:
        dist = haversine_distance(lat, lng, street["lat"], street["lng"])
        if dist <= street["radius"]:
            return True, street["name"]
    return False, None


def scarcity_quality_score(rating, review_count):
    """
    Calculate scarcity as quality signal.

    High rating + relatively few reviews = exclusive/local spot
    that doesn't rely on tourist traffic.

    Sweet spot: 4.5+ rating with 50-300 reviews
    (enough to be reliable, not enough to be overhyped)
    """
    if rating < 4.3 or review_count < 35:
        return 0  # Need minimum quality and reliability

    # Best signal: high rating, moderate reviews (locals know, tourists don't)
    if rating >= 4.5 and 50 <= review_count <= 300:
        return 1.0
    elif rating >= 4.5 and 35 <= review_count < 50:
        return 0.7  # Good but needs more validation
    elif rating >= 4.5 and 300 < review_count <= 600:
        return 0.6  # Still good, getting popular
    elif rating >= 4.3 and 50 <= review_count <= 300:
        return 0.5  # Solid local spot

    return 0

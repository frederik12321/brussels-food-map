"""
Brussels-Specific Context Data

Contains commune boundaries, classifications, and cultural mapping
for Brussels-specific restaurant reranking.
"""

import math
import re
import unicodedata


# ============================================================================
# AUTHENTICITY MARKERS - Automatic detection of cultural identity signals
# ============================================================================

# Diacritics that are UNIQUE to specific cuisines (not in French)
# These are strong authenticity signals
UNIQUE_DIACRITICS_BY_CUISINE = {
    "Turkish": set("şğıİ"),  # Ş, Ğ, ı (dotless i), İ (dotted I) - UNIQUE to Turkish
    "Vietnamese": set("ăđơưảãạằẳẵắặầẩẫấậẻẽẹềểễếệỉĩịỏõọồổỗốộờởỡớợủũụừửữứựỳỷỹỵ"),
    "Polish": set("ąćęłńśźż"),  # ł, ą, ę are unique
    "Romanian": set("șț"),  # ș, ț with comma below (different from Turkish ş)
}

# Diacritics that COULD be French but combined with other signals suggest authenticity
AMBIGUOUS_DIACRITICS = {
    "Turkish": set("öü"),  # Also in German/French, but with ş/ğ suggests Turkish
    "Portuguese": set("ãõ"),  # ã, õ are relatively unique to Portuguese
}

# All unique diacritics combined
AUTHENTICITY_DIACRITICS = set()
for chars in UNIQUE_DIACRITICS_BY_CUISINE.values():
    AUTHENTICITY_DIACRITICS.update(chars)
for chars in AMBIGUOUS_DIACRITICS.values():
    AUTHENTICITY_DIACRITICS.update(chars)

# Flag emojis mapped to cuisines
FLAG_EMOJI_CUISINES = {
    "🇹🇷": "Turkish",
    "🇧🇷": "Brazilian",
    "🇬🇷": "Greek",
    "🇨🇳": "Chinese",
    "🇮🇹": "Italian",
    "🇮🇳": "Indian",
    "🇯🇵": "Japanese",
    "🇰🇷": "Korean",
    "🇻🇳": "Vietnamese",
    "🇹🇭": "Thai",
    "🇱🇧": "Lebanese",
    "🇲🇦": "Moroccan",
    "🇵🇹": "Portuguese",
    "🇪🇸": "Spanish",
    "🇵🇱": "Polish",
    "🇷🇴": "Romanian",
    "🇷🇺": "Russian",
    "🇺🇦": "Ukrainian",
    "🇵🇰": "Pakistani",
    "🇧🇩": "Bangladeshi",
    "🇪🇹": "Ethiopian",
    "🇨🇩": "Congolese",
    "🇸🇳": "Senegalese",
    "🇵🇪": "Peruvian",
    "🇲🇽": "Mexican",
    "🇦🇷": "Argentinian",
}


def has_authenticity_diacritics(name):
    """
    Check if restaurant name contains non-French diacritics that signal cultural identity.

    Returns: (bool, set of matched diacritics, likely cuisine)

    Examples:
        "YÖRÜK ÇADIRI" -> (True, {'Ö', 'Ü', 'Ç'}, "Turkish")  # Note: Ç with cedilla below
        "Phở & Bánh Mì" -> (True, {'ở', 'á', 'ì'}, "Vietnamese")
        "Café de Flore" -> (False, set(), None)  # French é is baseline
        "GÜLER PIDE" -> (True, {'Ü'}, "Turkish")  # Ü with context suggests Turkish
    """
    if not name:
        return False, set(), None

    # Normalize to NFC to handle composed vs decomposed unicode
    name_normalized = unicodedata.normalize('NFC', name)

    found_diacritics = set()
    found_unique = set()  # Diacritics that are definitely not French

    for char in name_normalized:
        char_lower = char.lower()
        if char_lower in AUTHENTICITY_DIACRITICS or char in AUTHENTICITY_DIACRITICS:
            found_diacritics.add(char)
            # Check if it's a unique (non-ambiguous) diacritic
            for cuisine_chars in UNIQUE_DIACRITICS_BY_CUISINE.values():
                if char_lower in cuisine_chars or char in cuisine_chars:
                    found_unique.add(char)

    if not found_diacritics:
        return False, set(), None

    # Try to identify the likely cuisine based on which diacritics were found
    likely_cuisine = None
    best_match_count = 0

    # First check unique diacritics
    for cuisine, cuisine_diacritics in UNIQUE_DIACRITICS_BY_CUISINE.items():
        found_lower = {c.lower() for c in found_diacritics}
        match_count = len(found_lower & cuisine_diacritics)
        if match_count > best_match_count:
            best_match_count = match_count
            likely_cuisine = cuisine

    # If no unique match, check ambiguous
    if not likely_cuisine:
        for cuisine, cuisine_diacritics in AMBIGUOUS_DIACRITICS.items():
            found_lower = {c.lower() for c in found_diacritics}
            match_count = len(found_lower & cuisine_diacritics)
            if match_count > best_match_count:
                best_match_count = match_count
                likely_cuisine = cuisine

    return True, found_diacritics, likely_cuisine


def has_flag_emoji(name):
    """
    Check if restaurant name contains a country flag emoji.

    Returns: (bool, flag emoji if found, associated cuisine)

    Examples:
        "Brazil Grill 🇧🇷" -> (True, "🇧🇷", "Brazilian")
        "Pellas 🇬🇷" -> (True, "🇬🇷", "Greek")
        "Restaurant Normal" -> (False, None, None)
    """
    if not name:
        return False, None, None

    for flag, cuisine in FLAG_EMOJI_CUISINES.items():
        if flag in name:
            return True, flag, cuisine

    return False, None, None


def get_authenticity_markers(name):
    """
    Get all automatic authenticity markers for a restaurant name.

    Returns dict with:
        - has_diacritics: bool
        - diacritics_found: set
        - diacritics_cuisine: str or None
        - has_flag: bool
        - flag_emoji: str or None
        - flag_cuisine: str or None
        - authenticity_signal_score: float (0-1, higher = more signals)
    """
    has_diacr, diacr_found, diacr_cuisine = has_authenticity_diacritics(name)
    has_fl, flag_emoji, flag_cuisine = has_flag_emoji(name)

    # Calculate a simple signal score
    signal_score = 0.0
    if has_diacr:
        signal_score += 0.5
    if has_fl:
        signal_score += 0.5

    return {
        "has_diacritics": has_diacr,
        "diacritics_found": diacr_found,
        "diacritics_cuisine": diacr_cuisine,
        "has_flag": has_fl,
        "flag_emoji": flag_emoji,
        "flag_cuisine": flag_cuisine,
        "authenticity_signal_score": signal_score,
    }

# Grand Place coordinates (tourist epicenter)
GRAND_PLACE = (50.8467, 4.3525)

# Place Schuman (EU bubble center)
PLACE_SCHUMAN = (50.8427, 4.3827)

# Brussels Capital Region approximate bounding box
# These bounds include all 19 communes with a small margin
BRUSSELS_BOUNDS = {
    "lat_min": 50.76,   # Southern edge (Watermael-Boitsfort)
    "lat_max": 50.91,   # Northern edge (Evere/Schaerbeek)
    "lng_min": 4.26,    # Western edge (Berchem-Sainte-Agathe)
    "lng_max": 4.48,    # Eastern edge (Woluwe-Saint-Pierre)
}

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
# Note: Default radius is 0.5km (set in get_neighborhood function)
# Matongé uses a tighter 0.3km radius to avoid overlapping with Châtelain
NEIGHBORHOODS = {
    "Matongé": {"commune": "Ixelles", "lat": 50.8295, "lng": 4.3680, "tier": "local_foodie", "cuisine_affinity": ["Congolese", "African"], "radius": 0.3},
    "Châtelain": {"commune": "Ixelles", "lat": 50.8235, "lng": 4.3600, "tier": "local_foodie", "cuisine_affinity": ["French", "Belgian", "Brunch"]},
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
# Updated with 2026 diaspora commercial hub data (street-level precision)
LOCAL_FOOD_STREETS = [
    # === MAGHREB COMMERCIAL HUBS ===
    # Chaussée de Gand (Molenbeek) - major Maghreb commercial axis from Place Sainctelette
    {"name": "Chaussée de Gand", "lat": 50.8570, "lng": 4.3320, "radius": 0.30},
    # Rue de Brabant (Schaerbeek/Gare du Nord) - massive Maghreb commercial hub
    {"name": "Rue de Brabant", "lat": 50.8555, "lng": 4.3595, "radius": 0.25},
    # Clemenceau/Abattoirs area (Anderlecht) - Foodmet market + surrounding streets
    {"name": "Foodmet/Clemenceau", "lat": 50.8400, "lng": 4.3180, "radius": 0.25},
    # Cureghem (Anderlecht) - Maghreb residential hub
    {"name": "Cureghem", "lat": 50.8380, "lng": 4.3180, "radius": 0.25},

    # === TURKISH "LITTLE ANATOLIA" (Saint-Josse → Schaerbeek) ===
    # Chaussée de Haecht from metro Saint-Josse to Place de la Reine
    {"name": "Chaussée de Haecht", "lat": 50.8570, "lng": 4.3680, "radius": 0.30},
    # Rue de la Poste / Place Madou area
    {"name": "Place Madou Turkish Quarter", "lat": 50.8520, "lng": 4.3700, "radius": 0.15},
    # Fatih Mosque surroundings (Rue des Palais/Koningstraat)
    {"name": "Fatih Mosque Area", "lat": 50.8590, "lng": 4.3650, "radius": 0.15},

    # === MATONGÉ (Congolese/African hub in Ixelles) ===
    # Tight triangle: Chaussée de Wavre, Galerie d'Ixelles, Rue de la Longue Vie
    # Centered north of Châtelain, around Porte de Namur metro
    {"name": "Chaussée de Wavre (Matongé)", "lat": 50.8300, "lng": 4.3690, "radius": 0.15},
    {"name": "Galerie d'Ixelles", "lat": 50.8295, "lng": 4.3680, "radius": 0.08},
    {"name": "Rue Longue Vie", "lat": 50.8290, "lng": 4.3700, "radius": 0.10},
    # Porte de Namur extension (tight radius)
    {"name": "Porte de Namur", "lat": 50.8335, "lng": 4.3670, "radius": 0.12},

    # === POLISH/EASTERN EUROPEAN (Saint-Gilles/Forest) ===
    # Barrière de Saint-Gilles - Polish grocery stores (Sklep Polski)
    {"name": "Barrière de Saint-Gilles", "lat": 50.8225, "lng": 4.3445, "radius": 0.18},
    # Rue de Bosnie area
    {"name": "Rue de Bosnie", "lat": 50.8235, "lng": 4.3420, "radius": 0.12},
    # Forest - Romanian/Polish residential
    {"name": "Rue du Dries", "lat": 50.8130, "lng": 4.3220, "radius": 0.15},

    # === ROMANIAN (Anderlecht/Koekelberg) ===
    # Scattered residential - main commercial near Simonis/Osseghem
    {"name": "Osseghem Romanian Quarter", "lat": 50.8650, "lng": 4.3300, "radius": 0.20},

    # === EURO-EXPAT HUBS ===
    # Place du Châtelain (Wednesday market, wine bars, French brasseries)
    {"name": "Place du Châtelain", "lat": 50.8245, "lng": 4.3625, "radius": 0.15},
    # Schuman/EU Quarter
    {"name": "Place Schuman", "lat": 50.8427, "lng": 4.3827, "radius": 0.20},
    # Place du Luxembourg (young EU staffers)
    {"name": "Place du Luxembourg", "lat": 50.8380, "lng": 4.3715, "radius": 0.15},

    # === SYRIAN/IRAQI (post-2015 arrivals) ===
    # Chaussée de Louvain near Place Madou
    {"name": "Chaussée de Louvain", "lat": 50.8545, "lng": 4.3750, "radius": 0.20},

    # === SOUTH ASIAN (Indian/Pakistani/Bangladeshi) ===
    # Rue de l'Argonne (near Porte de Namur)
    {"name": "Rue de l'Argonne", "lat": 50.8340, "lng": 4.3640, "radius": 0.12},
    # Boulevard Jamar (Gare du Midi area)
    {"name": "Boulevard Jamar", "lat": 50.8360, "lng": 4.3350, "radius": 0.15},

    # === PORTUGUESE/BRAZILIAN ===
    # Porte de Hal area (Portuguese)
    {"name": "Porte de Hal", "lat": 50.8365, "lng": 4.3480, "radius": 0.15},
    # Place Flagey (Brazilian/Portuguese young professionals)
    {"name": "Place Flagey", "lat": 50.8275, "lng": 4.3720, "radius": 0.18},

    # === SAINT-GILLES LOCAL SPOTS ===
    {"name": "Rue de Moscou", "lat": 50.8265, "lng": 4.3445, "radius": 0.15},
    {"name": "Rue Vanderschrick", "lat": 50.8245, "lng": 4.3435, "radius": 0.15},
    {"name": "Rue du Fort", "lat": 50.8255, "lng": 4.3490, "radius": 0.15},
    {"name": "Chaussée de Charleroi", "lat": 50.8300, "lng": 4.3520, "radius": 0.20},
    {"name": "Parvis de Saint-Gilles", "lat": 50.8270, "lng": 4.3465, "radius": 0.15},

    # === IXELLES LOCAL SPOTS ===
    {"name": "Rue Lesbroussart", "lat": 50.8265, "lng": 4.3755, "radius": 0.15},
    {"name": "Rue du Page", "lat": 50.8235, "lng": 4.3580, "radius": 0.15},
    {"name": "Rue Américaine", "lat": 50.8231, "lng": 4.3591, "radius": 0.12},
    {"name": "Rue de la Paix", "lat": 50.8295, "lng": 4.3665, "radius": 0.12},

    # === SCHAERBEEK LOCAL ===
    {"name": "Rue Josaphat", "lat": 50.8580, "lng": 4.3780, "radius": 0.20},
    {"name": "Place Colignon", "lat": 50.8625, "lng": 4.3720, "radius": 0.15},

    # === ANDERLECHT LOCAL ===
    {"name": "Rue Wayez", "lat": 50.8395, "lng": 4.3095, "radius": 0.15},

    # === JETTE LOCAL ===
    {"name": "Rue Léon Théodor", "lat": 50.8780, "lng": 4.3280, "radius": 0.15},
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

# Diaspora cuisine-commune authenticity matrix (2026 data)
# Based on demographic research: Brussels is 75% foreign origin, no majority group.
#
# KEY ZONES:
# - "Poor Crescent" (Croissant Pauvre): Molenbeek, Saint-Josse, Anderlecht (Cureghem),
#   Lower Schaerbeek - Maghreb, Turkish, Romanian, West African
# - "Rich Southeast": Uccle, Woluwe-St-Pierre, Woluwe-St-Lambert, Auderghem -
#   French, Eurocrats, wealthy Belgians
# - "Mix/Transition": Ixelles, Saint-Gilles, Forest - French young pros, Portuguese,
#   Polish, Brazilian, gentrifying
#
# Higher score = stronger authenticity signal for that cuisine in that commune
DIASPORA_AUTHENTICITY = {
    # === MAGHREB COMMUNITY (Morocco & Tunisia) ===
    # 3rd/4th generation, from 1964 labor agreements
    # Commercial hubs: Rue de Brabant (Schaerbeek), Chaussée de Gand (Molenbeek)
    "Moroccan": {
        "Molenbeek-Saint-Jean": 1.0,  # Heart of Maghreb community
        "Anderlecht": 0.9,            # Cureghem is a major hub
        "Saint-Gilles": 0.85,         # Strong presence
        "Schaerbeek": 0.85,           # Rue de Brabant area
        "Saint-Josse-ten-Noode": 0.8,
    },
    "Tunisian": {
        "Molenbeek-Saint-Jean": 0.9,
        "Anderlecht": 0.85,
        "Saint-Gilles": 0.8,
        "Schaerbeek": 0.75,
    },
    "North African": {
        "Molenbeek-Saint-Jean": 0.95,
        "Anderlecht": 0.9,
        "Saint-Gilles": 0.8,
        "Schaerbeek": 0.8,
        "Saint-Josse-ten-Noode": 0.75,
    },

    # === TURKISH COMMUNITY ===
    # 1964 labor agreements, strong internal cohesion
    # Saint-Josse = "Little Anatolia", Chaussée de Haecht (Schaerbeek)
    "Turkish": {
        "Saint-Josse-ten-Noode": 1.0,  # "Little Anatolia" - highest density
        "Schaerbeek": 0.9,             # Chaussée de Haecht area
        "Molenbeek-Saint-Jean": 0.7,
    },

    # === SUB-SAHARAN AFRICAN COMMUNITY (DR Congo) ===
    # Colonial history link, Matongé is cultural heart (but gentrifying)
    # Residents pushed to Molenbeek and Anderlecht
    "Congolese": {
        "Ixelles": 1.0,               # Matongé = historic heart
        "Molenbeek-Saint-Jean": 0.7,  # Growing due to gentrification push
        "Anderlecht": 0.7,            # Growing community
        "Saint-Gilles": 0.6,
        "Schaerbeek": 0.5,
    },
    "African": {
        "Ixelles": 0.9,               # Matongé
        "Molenbeek-Saint-Jean": 0.75,
        "Anderlecht": 0.7,
        "Saint-Gilles": 0.65,
        "Schaerbeek": 0.6,
    },
    "West African": {
        "Ixelles": 0.85,
        "Molenbeek-Saint-Jean": 0.8,
        "Anderlecht": 0.75,
        "Saint-Gilles": 0.65,
    },

    # === EASTERN EUROPEAN WAVE (Romania, Poland, Bulgaria) ===
    # Romanians = 2nd largest foreign nationality since 2007
    # Poles in Saint-Gilles and Forest (specialized grocery stores)
    "Romanian": {
        "Saint-Gilles": 0.8,
        "Forest": 0.75,
        "Anderlecht": 0.7,
        "Schaerbeek": 0.65,
    },
    "Polish": {
        "Saint-Gilles": 0.85,         # Sklep Polski grocery stores
        "Forest": 0.8,
        "Anderlecht": 0.65,
    },
    "Eastern European": {
        "Saint-Gilles": 0.8,
        "Forest": 0.75,
        "Anderlecht": 0.7,
    },

    # === EMERGING COMMUNITIES (2015-2026) ===
    # Syrians & Iraqis: post-2015 refugee crisis, entrepreneurial
    "Syrian": {
        "Saint-Josse-ten-Noode": 0.9,
        "Saint-Gilles": 0.85,
        "Schaerbeek": 0.75,
    },
    "Iraqi": {
        "Saint-Josse-ten-Noode": 0.85,
        "Schaerbeek": 0.75,
    },
    # Brazilians: growing community around Barrière (Saint-Gilles)
    "Brazilian": {
        "Saint-Gilles": 0.9,          # Barrière area
        "Ixelles": 0.65,
        "Forest": 0.6,
    },

    # === OTHER ESTABLISHED COMMUNITIES ===
    "Middle Eastern": {
        "Saint-Josse-ten-Noode": 0.9,
        "Schaerbeek": 0.8,
        "Molenbeek-Saint-Jean": 0.7,
    },
    "Lebanese": {
        "Saint-Josse-ten-Noode": 0.8,
        "Ixelles": 0.65,
        "Saint-Gilles": 0.6,
    },
    "Ethiopian": {
        "Bruxelles": 0.75,            # Near Sainte-Catherine
        "Ixelles": 0.7,
        "Saint-Gilles": 0.5,
    },
    "Portuguese": {
        "Saint-Gilles": 0.9,          # Historic community
        "Ixelles": 0.7,
        "Forest": 0.65,
    },
    "Vietnamese": {
        "Bruxelles": 0.7,
        "Ixelles": 0.6,
    },
    "Chinese": {
        "Bruxelles": 0.6,
        "Ixelles": 0.5,
    },
    "Indian": {
        "Ixelles": 0.6,
        "Saint-Gilles": 0.5,
        "Etterbeek": 0.45,            # Some near EU quarter
    },
    "Pakistani": {
        "Saint-Josse-ten-Noode": 0.7,
        "Schaerbeek": 0.6,
        "Anderlecht": 0.6,  # Gare du Midi area - validated: Mithu da Dhaba
    },
    "Greek": {
        "Saint-Gilles": 0.8,  # Gare du Midi area (Rue de Mérode/Suède) - the "Old Greek" neighborhood
        "Ixelles": 0.5,
    },
    # Note: Italian and Spanish removed - they are mainstream European cuisines,
    # not diaspora communities in the same sense as immigrant communities.
    # The diaspora bonus is meant for immigrant communities where location
    # signals authenticity (Moroccan in Molenbeek, Turkish in Saint-Josse, etc.)
}

# Belgian traditional cuisine authenticity
BELGIAN_AUTHENTICITY = {
    "Belgian": {"Anderlecht": 0.9, "Schaerbeek": 0.8, "Forest": 0.8, "Bruxelles": 0.5},
    "Seafood": {"Bruxelles": 0.8},  # Sainte-Catherine area
    "French": {"Ixelles": 0.7, "Uccle": 0.7, "Saint-Gilles": 0.6},
}

# Friterie authenticity by commune
# Working-class communes where locals know quality frites
# Data shows: friteries in these areas score 24% higher than tourist areas
FRITERIE_AUTHENTICITY = {
    "Jette": 1.0,                  # Highest scoring friteries
    "Evere": 0.95,
    "Berchem-Sainte-Agathe": 0.95,
    "Anderlecht": 0.9,
    "Forest": 0.9,
    "Schaerbeek": 0.85,
    "Ganshoren": 0.85,
    "Molenbeek-Saint-Jean": 0.8,
    "Koekelberg": 0.8,
    "Saint-Gilles": 0.6,           # Gentrifying
    "Ixelles": 0.5,                # Gentrified
    "Bruxelles": 0.3,              # Tourist areas - penalty
}

# Curated list of authentic Bruxellois establishments
# These are places where locals go - not tourist traps
# Normalized names (lowercase, stripped) for matching
BRUXELLOIS_INSTITUTIONS = {
    # === HIDDEN GEMS - No tourist would stumble here ===
    "potverdoemmeke": 1.0,        # Schaerbeek, menu in dialect
    "potes en toque": 1.0,        # Ganshoren, residential farmhouse
    "friture rene": 1.0,          # Anderlecht, locals only
    "friture rené": 1.0,          # Accent variant
    "petits bouchons": 1.0,       # Uccle, where chefs go after service
    "zinneke": 1.0,               # Evere (Het Zinneke), slow-food crowd
    "fernand obb": 1.0,           # Saint-Gilles, counter service, locals queuing
    "porteuse d'eau": 1.0,        # Saint-Gilles, hidden in Art Nouveau block
    "volle gas": 1.0,             # Ixelles, Place Fernand Cocq, neighborhood spot

    # === INSTITUTIONS - Famous but still authentic ===
    # Some tourists, but quality maintained and locals still go
    "fin de siecle": 0.9,         # Guidebooks found it, but cash-only keeps it honest
    "fin de siècle": 0.9,         # Accent variant
    "brigittines": 0.9,           # Serious kitchen, earned reputation
    "maison antoine": 0.9,        # Famous queues but still the real thing
    "noordzee": 0.9,              # Standing room seafood, quality held
    "mer du nord": 0.9,           # French name variant

    # === CLASSIC BRUXELLOIS ===
    "spinnekopke": 0.9,           # Traditional Brussels cuisine
    "vismet": 0.9,                # Seafood institution
    "kelderke": 0.9,              # Grand Place but authentic
    "taverne du passage": 0.85,   # Galeries, touristic but classic
    "stekerlapatte": 0.9,         # Saint-Gilles classic
}

# Street-level diaspora mapping (2026 detailed data)
# Maps cuisines to specific commercial streets/areas where authentic restaurants cluster
# This is informational - shows cultural geography without scoring impact
DIASPORA_STREETS = {
    "Moroccan": [
        {"name": "Chaussée de Gand", "commune": "Molenbeek-Saint-Jean", "lat": 50.8570, "lng": 4.3320},
        {"name": "Rue de Brabant", "commune": "Schaerbeek", "lat": 50.8555, "lng": 4.3595},
        {"name": "Foodmet/Clemenceau", "commune": "Anderlecht", "lat": 50.8400, "lng": 4.3180},
        {"name": "Cureghem", "commune": "Anderlecht", "lat": 50.8380, "lng": 4.3180},
    ],
    "Tunisian": [
        {"name": "Chaussée de Gand", "commune": "Molenbeek-Saint-Jean", "lat": 50.8570, "lng": 4.3320},
        {"name": "Rue de Brabant", "commune": "Schaerbeek", "lat": 50.8555, "lng": 4.3595},
    ],
    "North African": [
        {"name": "Chaussée de Gand", "commune": "Molenbeek-Saint-Jean", "lat": 50.8570, "lng": 4.3320},
        {"name": "Rue de Brabant", "commune": "Schaerbeek", "lat": 50.8555, "lng": 4.3595},
        {"name": "Cureghem", "commune": "Anderlecht", "lat": 50.8380, "lng": 4.3180},
    ],
    "Turkish": [
        {"name": "Chaussée de Haecht", "commune": "Saint-Josse-ten-Noode", "lat": 50.8570, "lng": 4.3680},
        {"name": "Place Madou area", "commune": "Saint-Josse-ten-Noode", "lat": 50.8520, "lng": 4.3700},
        {"name": "Fatih Mosque area", "commune": "Schaerbeek", "lat": 50.8590, "lng": 4.3650},
    ],
    "Congolese": [
        {"name": "Matongé (Chaussée de Wavre)", "commune": "Ixelles", "lat": 50.8285, "lng": 4.3685},
        {"name": "Galerie d'Ixelles", "commune": "Ixelles", "lat": 50.8280, "lng": 4.3680},
        {"name": "Rue Longue Vie", "commune": "Ixelles", "lat": 50.8275, "lng": 4.3695},
    ],
    "African": [
        {"name": "Matongé", "commune": "Ixelles", "lat": 50.8285, "lng": 4.3685},
        {"name": "Porte de Namur", "commune": "Ixelles", "lat": 50.8335, "lng": 4.3655},
    ],
    "Polish": [
        {"name": "Barrière de Saint-Gilles", "commune": "Saint-Gilles", "lat": 50.8225, "lng": 4.3445},
        {"name": "Rue de Bosnie", "commune": "Saint-Gilles", "lat": 50.8235, "lng": 4.3420},
    ],
    "Romanian": [
        {"name": "Osseghem area", "commune": "Koekelberg", "lat": 50.8650, "lng": 4.3300},
        {"name": "Anderlecht", "commune": "Anderlecht", "lat": 50.8333, "lng": 4.3072},
    ],
    "Syrian": [
        {"name": "Chaussée de Louvain", "commune": "Saint-Josse-ten-Noode", "lat": 50.8545, "lng": 4.3750},
        {"name": "Place Madou area", "commune": "Saint-Josse-ten-Noode", "lat": 50.8520, "lng": 4.3700},
    ],
    "Iraqi": [
        {"name": "Chaussée de Louvain", "commune": "Saint-Josse-ten-Noode", "lat": 50.8545, "lng": 4.3750},
    ],
    "Brazilian": [
        {"name": "Barrière de Saint-Gilles", "commune": "Saint-Gilles", "lat": 50.8225, "lng": 4.3445},
        {"name": "Place Flagey", "commune": "Ixelles", "lat": 50.8275, "lng": 4.3720},
    ],
    "Portuguese": [
        {"name": "Porte de Hal", "commune": "Saint-Gilles", "lat": 50.8365, "lng": 4.3480},
        {"name": "Place Flagey", "commune": "Ixelles", "lat": 50.8275, "lng": 4.3720},
    ],
    "Indian": [
        {"name": "Rue de l'Argonne", "commune": "Ixelles", "lat": 50.8340, "lng": 4.3640},
        {"name": "Boulevard Jamar (Gare du Midi)", "commune": "Anderlecht", "lat": 50.8360, "lng": 4.3350},
    ],
    "Pakistani": [
        {"name": "Rue de l'Argonne", "commune": "Ixelles", "lat": 50.8340, "lng": 4.3640},
        {"name": "Boulevard Jamar (Gare du Midi)", "commune": "Anderlecht", "lat": 50.8360, "lng": 4.3350},
    ],
    "Lebanese": [
        {"name": "Ixelles (various)", "commune": "Ixelles", "lat": 50.8275, "lng": 4.3697},
        {"name": "Saint-Gilles", "commune": "Saint-Gilles", "lat": 50.8261, "lng": 4.3456},
    ],
    "Ethiopian": [
        {"name": "Sainte-Catherine", "commune": "Bruxelles", "lat": 50.8511, "lng": 4.3461},
        {"name": "Matongé area", "commune": "Ixelles", "lat": 50.8285, "lng": 4.3685},
    ],
    "Greek": [
        {"name": "Gare du Midi area (Rue de Mérode/Suède)", "commune": "Saint-Gilles", "lat": 50.8365, "lng": 4.3360},
        {"name": "Ixelles", "commune": "Ixelles", "lat": 50.8275, "lng": 4.3697},
    ],
    # Note: Italian and Spanish removed - mainstream European cuisines
}

# Proust Factor: Cuisine Specificity Mapping
# Regional/specific cuisines are more authentic than generic categories
# "Sichuan" > "Chinese", "Neapolitan" > "Italian", etc.
# Returns bonus multiplier (0 = generic, 1.0 = highly specific)
CUISINE_SPECIFICITY = {
    # Asian specificity
    "Sichuan": 1.0,
    "Szechuan": 1.0,
    "Cantonese": 0.9,
    "Hunan": 1.0,
    "Taiwanese": 0.9,
    "Shanghainese": 1.0,
    "Dim Sum": 0.8,
    "Pekinese": 0.9,
    "Hakka": 1.0,
    # Japanese specificity
    "Ramen": 0.8,
    "Izakaya": 0.9,
    "Kaiseki": 1.0,
    "Omakase": 1.0,
    "Yakitori": 0.9,
    "Tonkatsu": 0.9,
    "Okonomiyaki": 1.0,
    # Korean specificity
    "Korean BBQ": 0.8,
    "Hansik": 1.0,
    # Indian specificity
    "South Indian": 0.9,
    "Punjabi": 0.9,
    "Gujarati": 1.0,
    "Bengali": 1.0,
    "Kerala": 1.0,
    "Chettinad": 1.0,
    "Hyderabadi": 0.9,
    # Italian specificity
    "Neapolitan": 0.9,
    "Sicilian": 1.0,
    "Tuscan": 0.9,
    "Roman": 0.9,
    "Venetian": 1.0,
    "Sardinian": 1.0,
    "Piedmontese": 1.0,
    "Emilian": 1.0,
    # Spanish specificity
    "Basque": 1.0,
    "Catalan": 0.9,
    "Galician": 1.0,
    "Andalusian": 0.9,
    # French specificity
    "Lyonnaise": 0.9,
    "Provençal": 0.9,
    "Alsatian": 0.9,
    "Breton": 0.9,
    "Burgundian": 1.0,
    "Savoyard": 0.9,
    # Mexican specificity
    "Oaxacan": 1.0,
    "Yucatecan": 1.0,
    "Jalisciense": 1.0,
    # Middle Eastern specificity
    "Levantine": 0.8,
    "Palestinian": 1.0,
    "Yemeni": 1.0,
    "Kurdish": 1.0,
    # African specificity
    "Ethiopian": 0.8,  # Already somewhat specific
    "Eritrean": 0.9,
    "Senegalese": 1.0,
    "Ivorian": 1.0,
    "Cameroonian": 1.0,
    "Ghanaian": 1.0,
    "Nigerian": 0.9,
    # Generic cuisines (no bonus)
    "Chinese": 0,
    "Japanese": 0,
    "Italian": 0,
    "French": 0,
    "Indian": 0,
    "Thai": 0,
    "Vietnamese": 0,
    "Mexican": 0,
    "American": 0,
    "Mediterranean": 0,
    "Asian": 0,
    "European": 0,
    "International": 0,
    "Fusion": 0,
}


def get_cuisine_specificity_bonus(cuisine):
    """
    Return specificity bonus for a cuisine type.
    Specific regional cuisines get a small boost over generic categories.
    """
    if not cuisine:
        return 0
    return CUISINE_SPECIFICITY.get(cuisine, 0)


# Known chain restaurants in Belgium
CHAIN_PATTERNS = [
    r"mcdonald", r"burger king", r"quick", r"kfc", r"subway", r"domino",
    r"pizza hut", r"starbucks", r"panos", r"exki", r"le pain quotidien",
    r"paul", r"class'croute", r"pizza express", r"vapiano", r"wagamama",
    r"nando", r"five guys", r"pitaya", r"sushi shop", r"planet sushi",
    r"bavet", r"balls & glory", r"ellis gourmet", r"manhattn",
    r"delitraiteur", r"o'tacos",
    # Note: "frituur/friterie" are NOT chains - they're independent Belgian institutions
    # Only specific friterie chains should be listed here
    r"\bfritland\b",  # Fritland is a specific chain with multiple locations
    # Açaí/smoothie bowl chains
    r"oakberry",
]

# Non-restaurant retail shops that shouldn't rank as restaurants
# These are shops that sell food products but are not places to eat
NON_RESTAURANT_SHOPS = [
    # Belgian chocolate shops/brands (use word boundaries to avoid false positives)
    r"\bcorné\b", r"\bcorne dynastie\b", r"\bneuhaus\b", r"\bgodiva\b", r"\bleonidas\b",
    r"\bpierre marcolini\b", r"\bmarcolini\b", r"\bgaller\b", r"\bwittamer\b",
    r"\bmary chocolatier\b", r"\bplanète chocolat\b", r"\bfrederic blondeel\b",
    # Generic shop indicators
    r"\bchocolatier\b", r"\bchocolate shop\b", r"\bpralines\b",
    # Butcher shops / slagerijen
    r"\bspek\s*[&n]\s*boonen\b",
    # Gas stations / tankstations (filter by name in case primary_type is wrong)
    r"^shell$", r"^totalenergies\b", r"^esso$", r"^lukoil\b", r"^texaco$",
    r"^q8$", r"^gulf$", r"\btankstation\b",
]

# Permanently closed restaurants - manually curated list
# These should be filtered out even if they appear in Google Maps data
PERMANENTLY_CLOSED = [
    "la canne en ville",
    "canne en ville",
]


def is_non_restaurant_shop(name):
    """Check if a place is a retail shop rather than a restaurant."""
    if not name:
        return False
    name_lower = name.lower()
    for pattern in NON_RESTAURANT_SHOPS:
        if re.search(pattern, name_lower):
            return True
    return False


def is_chain_restaurant(name):
    """
    Check if a restaurant is a chain based on CHAIN_PATTERNS.

    This is used during reranking to override the is_chain field from
    the original data, allowing us to add new chain patterns without
    re-running the full feature engineering pipeline.
    """
    if not name:
        return False
    name_lower = name.lower()
    for pattern in CHAIN_PATTERNS:
        if re.search(pattern, name_lower):
            return True
    return False

# Michelin starred restaurants (Brussels Capital Region)
# Updated for 2025 official Michelin Guide - Complete list
MICHELIN_STARS = {
    # === 2 STARS - Exceptional cooking, worth a detour ===
    "bon bon": 2,
    "comme chez soi": 2,
    "l'air du temps": 2,
    "air du temps": 2,
    "bozar restaurant": 2,
    "karen torosyan": 2,  # Chef at Bozar
    # Note: "la paix" pattern needs exact match - handled specially below

    # === 1 STAR - High-quality cooking, worth a stop ===
    "sanzaru": 1,
    "san ": 1,  # Note: space to avoid matching "sandwich"
    "la villa emily": 1,
    "villa emily": 1,
    "kwint": 1,
    "toshiro": 1,
    "la villa in the sky": 1,
    "villa in the sky": 1,
    "rouge tomate": 1,
    "kamo": 1,
    "nuance by nutri": 1,
    "nuance nutri": 1,
    "sea grill": 1,
    "l'écrin": 1,
    "ecrin": 1,
    "aux armes de bruxelles": 1,  # Starred location
    "orphyse chaussette": 1,
    "humphrey": 1,
    "alexandre": 1,
    # "la canne en ville": 1,  # PERMANENTLY CLOSED (2026)
    # "canne en ville": 1,
    "le chalet de la forêt": 1,
    "chalet de la forêt": 1,
    "roberto": 1,
    "lola": 1,
    "san degeimbre": 1,
    "l'atelier de bossimé": 1,
    "atelier de bossime": 1,
    # Additional confirmed starred
    "barge": 1,
    "da mimmo": 1,
    "eliane": 1,
    "humus x hortense": 1,  # Also Green Star
    "humus hortense": 1,
    "le pigeon noir": 1,
    "pigeon noir": 1,
    "menssa": 1,
    "senzanome": 1,
}

# Bib Gourmand (Michelin - good quality, good value)
# Updated for 2025 official Michelin Guide - Complete list (31 restaurants)
BIB_GOURMAND = [
    # === BRUSSELS PROPER ===
    "jb",
    "jb sushi",
    "selecto",
    "le selecto",
    "strofilia",
    "kline",
    "les filles",
    "tero",
    "rouge tomate",
    "humphrey",
    "wine bar des marolles",
    "le wine bar des marolles",
    "barge",
    "crab club",
    "humus x hortense",
    "humus hortense",
    "la bonne chère",
    "bonne chere",
    "faubourg saint-antoine",
    "faubourg saint antoine",
    "le rabassier",
    "rabassier",

    # === GREATER BRUSSELS ===
    "yoka tomo",
    "yokatomo",
    "lune siamoise",
    "car bon",
    "french kiss",
    "villa singha",
    "de maurice à olivier",
    "maurice à olivier",
    "babam",
    "au repos de la montagne",
    "repos de la montagne",
    "maza'j",
    "mazaj",
    "la branche d'olivier",
    "branche d'olivier",
    "appel thaï",
    "appel thai",
    "faraya",
    "station 3",
    "monsieur v",
    "ferment",
    "furbetto",

    # === LEGACY (may still be valid) ===
    "anju",
    "la charcuterie",
    "l'épicerie nomad",
    "epicerie nomad",
    "le tournant",
    "tournant",
    "le variétés",
    "variétés",
    "les potes en toque",
    "potes en toque",
    "nénu",
    "nenu",
    "osteria bolognese",
    "saint boniface",
    "st. kilda",
    "st kilda",
]

# Gault & Millau recognized restaurants (15+ points)
# Updated for Gault&Millau Belux Guide 2026
# Complete list scraped from Gault&Millau website (120+ restaurants)
# Note: This list is separate from Michelin - restaurants can have both
GAULT_MILLAU = [
    # === 17.5/20 - The Absolute Top ===
    "bozar restaurant",
    "karen torosyan",
    "comme chez soi",
    "chalet de la forêt",
    "le chalet de la forêt",
    # Note: "la paix" handled specially in function (17.5/20)

    # === 17/20 - Excellent ===
    "villa in the sky",
    "eliane",

    # === 16-16.5/20 - Excellent Tables ===
    "humus x hortense",
    "humus hortense",
    "kamo",
    "senzanome",

    # === 15-15.5/20 - High Rated ===
    "barge",
    "palais royal by david martin",
    "chaga",
    "da mimmo",
    "nonbe daigaku",
    "stirwen",
    "le stirwen",

    # === 14-14.5/20 - Upper Mid ===
    "quartz",          # Highest Newcomer
    "entropy",
    "la bonne chère",
    "bonne chere",
    "le passage",
    "amen",
    "aster",
    "ciao",
    "ivresse",
    "jayu",
    "l'ecailler du palais",
    "ecailler du palais",
    "la belle maraîchère",
    "belle maraichere",
    "la buvette",
    "la truffe noire",
    "truffe noire",
    "le monde est petit",
    "monde est petit",
    "le pigeon noir",
    "pigeon noir",
    "racines",
    "samouraï",
    "samourai",

    # === 13-13.5/20 - Mid Range ===
    "anju",
    "babam",
    "beaucoup belge",
    "beaucoup fish",
    "bocconi",
    "bogart-foodies corner",
    "bogart foodies",
    "bottega vannini",
    "brugmann",
    "brut",
    "car bon",
    "certo",
    "charlu",
    "chou",
    "cinq",
    "colonel fort jaco",
    "colonel louise",
    "dolce amaro",
    "fico",
    "flamme",
    "frasca",
    "friture rené",
    "friture rene",
    "gramm",
    "gus",
    "henri",
    "hispania",
    "il passatempo",
    "passatempo",
    "ioda",
    "jaco",
    "kartouche",
    "kline",
    "klok",
    "la branche d'olivier",
    "branche d'olivier",
    "la table de mus",
    "table de mus",
    "le 203",
    "le corbier",
    "corbier",
    "le coq en pâte",
    "coq en pate",
    "le fringant",
    "fringant",
    "le petit bon bon",
    "petit bon bon",
    "le rossini",
    "rossini",
    "le tournant",
    "tournant",
    "le variétés",
    "varietes",
    "les brigittines",
    "brigittines",
    "les petits bouchons",
    "petits bouchons",
    "wine bar des marolles",
    "lola",
    "maison du luxembourg",
    "maru",
    "miranda",
    "nénu",
    "nenu",
    "nightshop",
    "nyyó",
    "nyyo",
    "odette en ville",
    "old boy",
    "origine",
    "pénar",
    "penar",
    "ricciocapriccio",
    "sanzaru",
    "savage",
    "selecto",
    "strofilia",
    "the avenue",
    "toucan sur mer",
    "yamayu santatsu",

    # === 12-12.5/20 - Entry Level ===
    "65 degrés",
    "65 degres",
    "al piccolo mondo",
    "piccolo mondo",
    "asado",
    "au repos de la montagne",
    "repos de la montagne",
    "au savoy",
    "savoy",
    "belga queen",
    "brasserie de la patinoire",
    "café maris",
    "cafe maris",
    "canterbury",
    "casa due",
    "chez luma",
    "coincoin",
    "correspondance",
    "crush",
    "de l'ogenblik",
    "ogenblik",
    "genco",
    "groseille",
    "hadrien",
    "kolya",
    "la pierre bleue",
    "pierre bleue",
    "le buone maniere",
    "buone maniere",
    "le saint boniface",
    "saint boniface",
    "les brasseries georges",
    "brasseries georges",
    "les brassins",
    "brassins",
    "lily's",
    "lilys",
    "l'orchidée blanche",
    "orchidee blanche",
    "lune siamoise",
    "mome",
    "osteria bolognese",
    "osteria romana",
    "ottanta",
    "philema",
    "ploegmans",
    "rallye des autos",
    "soif de faim",
    "toucan brasserie",
    "uma",

    # === Classic Brussels (traditionally recognized) ===
    "sea grill",
    "san daniele",
    "la quincaillerie",
    "humphrey",
    "brinz'l",
    "le clan des belges",
    "fin de siècle",
    "fin de siecle",
    "nuetnigenough",
    "nüetnigenough",
    "in 't spinnekopke",
    "spinnekopke",
    "la roue d'or",
    "roue d'or",
    "viva m'boma",
    "wine bar sablon",
    "mobi",
    "fernand obb",
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

# Authenticity indicators (updated 2026)
AUTHENTICITY_KEYWORDS = {
    "general": ["authentic", "authentique", "echt", "local", "traditionnel", "traditional", "homemade", "fait maison"],
    "belgian": ["stoofvlees", "waterzooi", "moules", "mosselen", "frites", "carbonade", "vol-au-vent", "stoemp"],
    "congolese": ["moambe", "saka saka", "fufu", "madesu", "pondu", "chikwanga", "liboke", "mikate", "makemba"],
    "moroccan": ["tajine", "couscous", "pastilla", "harira", "mechoui", "kefta", "msemen", "rfissa"],
    "turkish": ["pide", "lahmacun", "iskender", "döner", "kebab", "köfte", "mantı", "tantuni", "gözleme", "simit"],
    "ethiopian": ["injera", "doro wat", "tibs", "kitfo", "shiro", "beyainatu"],
    "syrian": ["shawarma", "fattoush", "kibbeh", "muhammara", "mujaddara", "maqluba"],
    "lebanese": ["mezze", "tabbouleh", "hummus", "falafel", "manakish", "fatayer"],
    "brazilian": ["feijoada", "picanha", "coxinha", "pão de queijo", "açaí", "churrasco"],
    "polish": ["pierogi", "bigos", "żurek", "kotlet schabowy", "barszcz"],
    "romanian": ["mămăligă", "sarmale", "mici", "ciorbă", "papanași"],
    "portuguese": ["bacalhau", "francesinha", "pastel de nata", "cozido", "bifana"],
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


def is_within_brussels(lat, lng):
    """
    Check if a location is within Brussels Capital Region bounds.

    Returns True if the coordinates fall within the 19 Brussels communes area.
    Uses a bounding box approximation for fast filtering.
    """
    if lat is None or lng is None:
        return False
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return False

    return (BRUSSELS_BOUNDS["lat_min"] <= lat <= BRUSSELS_BOUNDS["lat_max"] and
            BRUSSELS_BOUNDS["lng_min"] <= lng <= BRUSSELS_BOUNDS["lng_max"])


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
        # Use custom radius if specified, otherwise default 0.5km
        radius = data.get("radius", 0.5)
        if dist < radius:
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


def get_diaspora_context(cuisine, commune, lat=None, lng=None):
    """
    Get informational context about diaspora geography for a restaurant.

    This is for display purposes - helps users understand the cultural
    geography of Brussels without affecting the score.

    Returns dict with:
    - is_in_diaspora_area: bool - is this cuisine typical for this commune?
    - diaspora_streets: list - nearby streets known for this cuisine
    - community_description: str - brief description of the diaspora presence
    """
    context = {
        "is_in_diaspora_area": False,
        "diaspora_streets": [],
        "community_description": None,
    }

    # Check if cuisine has diaspora data
    if cuisine in DIASPORA_AUTHENTICITY:
        commune_scores = DIASPORA_AUTHENTICITY[cuisine]
        if commune in commune_scores and commune_scores[commune] >= 0.7:
            context["is_in_diaspora_area"] = True

    # Get known streets for this cuisine
    if cuisine in DIASPORA_STREETS:
        streets = DIASPORA_STREETS[cuisine]
        # Filter to streets in this commune or nearby
        relevant_streets = []
        for street in streets:
            if street["commune"] == commune:
                relevant_streets.append(street["name"])
            elif lat and lng:
                # Check if within 1km
                dist = haversine_distance(lat, lng, street["lat"], street["lng"])
                if dist < 1.0:
                    relevant_streets.append(f"{street['name']} ({street['commune']})")
        context["diaspora_streets"] = relevant_streets[:3]  # Max 3 streets

    # Community descriptions (informational)
    COMMUNITY_DESCRIPTIONS = {
        "Moroccan": "Brussels has a large Moroccan community (3rd/4th generation) centered in Molenbeek, Anderlecht, and Schaerbeek",
        "Turkish": "Saint-Josse is known as 'Little Anatolia' - home to Brussels' Turkish community since the 1960s",
        "Congolese": "Matongé (Ixelles) is the cultural heart of the Congolese diaspora, named after a district in Kinshasa",
        "African": "Matongé hosts Brussels' vibrant African community with shops, restaurants, and cultural centers",
        "Polish": "A growing Polish community has established shops and eateries around Barrière de Saint-Gilles",
        "Romanian": "Romania's largest Brussels community is in Anderlecht and Koekelberg since 2007",
        "Syrian": "Post-2015 Syrian entrepreneurs have opened restaurants around Chaussée de Louvain",
        "Brazilian": "A young Brazilian community gathers around Saint-Gilles' Barrière and Place Flagey",
        "Portuguese": "Historic Portuguese community (post-WWII) in Saint-Gilles, around Porte de Hal",
    }

    if cuisine in COMMUNITY_DESCRIPTIONS:
        context["community_description"] = COMMUNITY_DESCRIPTIONS[cuisine]

    return context


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

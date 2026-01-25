"""
Brussels-Specific Restaurant Reranking

Implements the Brussels reranking formula that accounts for:
- Tourist trap penalties
- Diaspora authenticity bonuses
- Commune underrepresentation boosts
- Independent restaurant bonuses
- Cold-start corrections
- Cuisine rarity rewards
"""

import math
import json
import os
import pandas as pd
import numpy as np
from collections import Counter

from brussels_context import (
    COMMUNES, NEIGHBORHOODS, TIER_WEIGHTS,
    DIASPORA_AUTHENTICITY, BELGIAN_AUTHENTICITY,
    FRITERIE_AUTHENTICITY, BRUXELLOIS_INSTITUTIONS,
    get_commune, get_neighborhood, get_diaspora_context,
    distance_to_grand_place, distance_to_eu_quarter,
    haversine_distance, is_on_local_street,
    has_michelin_recognition, has_gault_millau, has_bib_gourmand,
    get_cuisine_specificity_bonus, is_non_restaurant_shop,
    is_chain_restaurant
)
from afsca_hygiene import get_afsca_score, match_restaurant


# Reddit mentions cache (loaded once)
_reddit_mentions_cache = None

def load_reddit_mentions():
    """
    Load Reddit mentions from data file.
    Returns dict: {normalized_name: mention_count}
    """
    global _reddit_mentions_cache
    if _reddit_mentions_cache is not None:
        return _reddit_mentions_cache

    # Try to load filtered mentions
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    mentions_file = os.path.join(data_dir, "reddit_mentions_filtered.json")

    if not os.path.exists(mentions_file):
        # Fall back to unfiltered
        mentions_file = os.path.join(data_dir, "reddit_mentions.json")

    if not os.path.exists(mentions_file):
        _reddit_mentions_cache = {}
        return _reddit_mentions_cache

    try:
        with open(mentions_file, 'r') as f:
            mentions_list = json.load(f)
        # Convert to dict with normalized names
        _reddit_mentions_cache = {
            m['name'].lower().strip(): m['reddit_mentions']
            for m in mentions_list
        }
    except Exception:
        _reddit_mentions_cache = {}

    return _reddit_mentions_cache


def reddit_community_score(name, review_count):
    """
    Calculate Reddit community endorsement score.

    Restaurants mentioned positively on r/brussels by locals get a boost.
    Scaled by mention count and adjusted for restaurant size.

    Returns: score (0-1), mention_count
    """
    mentions = load_reddit_mentions()

    if not name or not mentions:
        return 0, 0

    # Normalize name for matching
    name_lower = name.lower().strip()

    # Only exact matches - no fuzzy matching to avoid false positives
    # e.g., "Le Coq" should only match the specific restaurant, not "Le Coq D'or"
    mention_count = mentions.get(name_lower, 0)

    if mention_count == 0:
        return 0, 0

    # Calculate score based on mention count
    # 1 mention = small boost, 5+ mentions = significant boost
    if mention_count >= 10:
        base_score = 1.0  # Maximum - highly recommended
    elif mention_count >= 5:
        base_score = 0.8  # Strong community support
    elif mention_count >= 3:
        base_score = 0.6  # Good mentions
    elif mention_count >= 2:
        base_score = 0.4  # Some recognition
    else:
        base_score = 0.2  # Single mention

    # Boost smaller restaurants more (Reddit finds hidden gems)
    # Big places with many reviews don't need the Reddit boost as much
    if review_count and review_count < 200:
        size_multiplier = 1.2  # Hidden gem bonus
    elif review_count and review_count > 2000:
        size_multiplier = 0.7  # Already well-known
    else:
        size_multiplier = 1.0

    final_score = min(1.0, base_score * size_multiplier)

    return final_score, mention_count


def tourist_trap_score(lat, lng, rating, review_count, review_languages=None):
    """
    Calculate tourist trap score (0-1).
    Higher = more likely tourist trap.

    REALISTIC APPROACH: Location alone doesn't make a tourist trap.
    We only penalize when there are MULTIPLE signals:
    - Near Grand Place/Rue des Bouchers AND
    - High review volume (tourist magnet) AND
    - Below-average rating (quality suffers from volume)

    A good restaurant near Grand Place should NOT be penalized.
    """
    dist_gp = distance_to_grand_place(lat, lng)

    # Check if in known tourist trap neighborhood
    neighborhood, neighborhood_data = get_neighborhood(lat, lng)
    in_tourist_zone = False

    if neighborhood == "Rue des Bouchers":
        in_tourist_zone = True
    elif neighborhood_data and neighborhood_data.get("tier") == "tourist_trap":
        in_tourist_zone = True
    elif dist_gp < 0.15:  # Within 150m of Grand Place
        in_tourist_zone = True

    # If not in tourist zone, no penalty
    if not in_tourist_zone:
        return 0

    # In tourist zone - but are there other signals?
    # Good restaurants (4.5+) in tourist areas are often STILL good
    # Only penalize if rating is mediocre AND review count is high

    # Signal 1: High volume (tourist magnet)
    high_volume = review_count > 1500

    # Signal 2: Below-average rating (quality suffers)
    mediocre_rating = rating < 4.3

    # Both signals needed for full penalty
    if high_volume and mediocre_rating:
        # Classic tourist trap: lots of reviews, mediocre quality
        # Penalty scales with how bad the rating is
        penalty = 0.4 + 0.3 * (4.3 - rating)  # 0.4-0.7 range
        return min(1.0, penalty)
    elif high_volume:
        # High volume but good rating - mild penalty (tourist-famous but good)
        return 0.15
    elif mediocre_rating and dist_gp < 0.1:
        # Very close to GP with mediocre rating - mild penalty
        return 0.2
    else:
        # In tourist zone but no red flags - no penalty
        return 0


def diaspora_authenticity_score(cuisine, commune, review_languages=None):
    """
    Calculate diaspora authenticity score (0-1).
    Higher = more authentic diaspora restaurant.

    Based on:
    - Cuisine type + commune match
    - Review language diversity
    """
    score = 0

    # Check diaspora cuisine authenticity matrix
    if cuisine in DIASPORA_AUTHENTICITY:
        commune_scores = DIASPORA_AUTHENTICITY[cuisine]
        if commune in commune_scores:
            score = commune_scores[commune]
        else:
            # Small bonus for diaspora cuisine outside typical areas
            # (could be authentic, just in different location)
            score = 0.2

    # Check Belgian traditional authenticity
    if cuisine in BELGIAN_AUTHENTICITY:
        commune_scores = BELGIAN_AUTHENTICITY[cuisine]
        if commune in commune_scores:
            score = max(score, commune_scores[commune])

    # Boost if reviews are in diaspora languages
    if review_languages and score > 0:
        diaspora_languages = {
            "Congolese": ["fr", "ln"],  # French + Lingala
            "African": ["fr", "ln", "sw"],
            "Moroccan": ["ar", "fr"],
            "Turkish": ["tr"],
            "Lebanese": ["ar", "fr"],
            "Portuguese": ["pt"],
            "Vietnamese": ["vi"],
            "Chinese": ["zh"],
        }

        if cuisine in diaspora_languages:
            relevant_langs = diaspora_languages[cuisine]
            total = sum(review_languages.values())
            if total > 0:
                relevant_pct = sum(review_languages.get(lang, 0) for lang in relevant_langs) / total
                # Boost authenticity if reviews are in relevant languages
                score = min(1.0, score + 0.2 * relevant_pct)

    return score


def is_friterie(name):
    """
    Detect if a restaurant is a friterie/fritkot based on name.
    These are quintessentially Brussels establishments.
    """
    if not name:
        return False
    name_lower = name.lower()
    friterie_keywords = ['frit', 'frituur', 'friture', 'fritkot', 'friterie']
    return any(keyword in name_lower for keyword in friterie_keywords)


def normalize_name_for_matching(name):
    """
    Normalize restaurant name for matching against BRUXELLOIS_INSTITUTIONS.
    Removes accents, punctuation, and converts to lowercase.
    """
    if not name:
        return ""
    import unicodedata
    # Normalize unicode and remove accents
    normalized = unicodedata.normalize('NFD', name)
    without_accents = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    # Lowercase and strip
    return without_accents.lower().strip()


def bruxellois_authenticity_score(name, commune):
    """
    Calculate authenticity score for traditional Bruxellois establishments.

    Returns score 0-1 based on:
    1. Curated list of known authentic institutions
    2. Friterie in working-class commune
    """
    if not name:
        return 0.0

    name_lower = name.lower().strip()
    name_normalized = normalize_name_for_matching(name)

    # Check curated institutions list (exact and partial matches)
    for institution_name, score in BRUXELLOIS_INSTITUTIONS.items():
        # Exact match
        if institution_name in name_lower or institution_name in name_normalized:
            return score

    # Check if friterie in authentic commune
    if is_friterie(name) and commune in FRITERIE_AUTHENTICITY:
        return FRITERIE_AUTHENTICITY[commune]

    return 0.0


def commune_visibility_boost(commune, commune_review_totals):
    """
    Calculate visibility boost for underrepresented communes.
    Higher = commune has fewer total reviews (needs more visibility).
    """
    if commune not in commune_review_totals:
        return 0.5  # Unknown commune gets moderate boost

    total_reviews = commune_review_totals[commune]
    # Inverse log scale
    boost = 1 / (math.log(total_reviews + 1) + 1)
    return min(1.0, boost * 3)  # Scale up and cap


def cold_start_correction(review_count, rating, commune):
    """
    Boost new restaurants with few reviews but high ratings.
    Especially if they're in underexplored communes.
    """
    if review_count >= 50:
        return 0

    # High rating + few reviews = promising new place
    rating_factor = (rating - 4.0) / 1.0 if rating > 4.0 else 0
    review_factor = 1 - (review_count / 50)  # Higher boost for fewer reviews

    # Extra boost if in underexplored commune
    commune_data = COMMUNES.get(commune, {})
    tier = commune_data.get("tier", "mixed")
    tier_multiplier = 1.5 if tier == "underexplored" else 1.0

    return rating_factor * review_factor * tier_multiplier * 0.5


def cuisine_rarity_score(cuisine, commune, cuisine_counts_by_commune):
    """
    Reward rare cuisines in a commune.
    Promotes diversity of food options.
    """
    if commune not in cuisine_counts_by_commune:
        return 0.5  # Unknown = assume rare

    commune_cuisines = cuisine_counts_by_commune[commune]
    total = sum(commune_cuisines.values())

    if total == 0:
        return 0.5

    cuisine_count = commune_cuisines.get(cuisine, 0)
    frequency = cuisine_count / total

    # Inverse frequency (rare = high score)
    if frequency == 0:
        return 1.0
    return min(1.0, 1 / (frequency * 10))


# Rare cuisines in Brussels - these get a global scarcity bonus
# (cuisines that are hard to find in Brussels)
RARE_CUISINES_BRUSSELS = {
    "Georgian": 1.0,      # Very rare
    "Peruvian": 0.9,
    "Filipino": 0.9,
    "Malaysian": 0.9,
    "Sri Lankan": 0.9,
    "Scandinavian": 0.8,
    "Venezuelan": 0.8,
    "Argentinian": 0.8,
    "Korean": 0.7,        # Growing but still rare
    "Ethiopian": 0.7,
    "Indonesian": 0.7,
    "Tibetan": 0.9,
    "Nepalese": 0.8,
    "Burmese": 0.9,
    "Caribbean": 0.8,
    "Jamaican": 0.9,
    "Cuban": 0.9,
    "Hawaiian": 1.0,
    "Taiwanese": 0.8,
    "Szechuan": 0.7,
    "Cantonese": 0.7,
}


def unified_scarcity_score(restaurant):
    """
    Calculate a unified scarcity score that combines all scarcity signals.

    Scarcity = hard to access = likely a local gem.
    Components:
    - Review count scarcity: moderate reviews (not too few, not too many)
    - Hours scarcity: closes early (doesn't need late-night tourist traffic)
    - Days scarcity: fewer days open (exclusive, doesn't need to maximize revenue)
    - Schedule scarcity: weekdays only (caters to locals/office workers)
    - Cuisine scarcity: rare cuisine in Brussels (hard to find)

    Returns tuple: (total_score, component_breakdown)
    """
    rating = restaurant.get("rating", 0)
    review_count = restaurant.get("review_count", 0)
    cuisine = restaurant.get("cuisine", "Other")
    closes_early = restaurant.get("closes_early", False)
    typical_close_hour = restaurant.get("typical_close_hour")
    weekdays_only = restaurant.get("weekdays_only", False)
    closed_weekends = restaurant.get("closed_weekends", False)
    closed_sunday = restaurant.get("closed_sunday", False)
    days_open_count = restaurant.get("days_open_count")

    components = {}

    # 1. Review count scarcity (from brussels_context.scarcity_quality_score logic)
    # Sweet spot: 50-500 reviews = established but not tourist-famous
    review_scarcity = 0
    if rating and review_count and rating >= 4.0:
        if 50 <= review_count <= 200:
            review_scarcity = 1.0  # Perfect: known locally, not over-hyped
        elif 200 < review_count <= 500:
            review_scarcity = 0.7  # Good: popular but not tourist-dominated
        elif 35 <= review_count < 50:
            review_scarcity = 0.5  # Decent: building reputation
        elif 500 < review_count <= 1000:
            review_scarcity = 0.3  # Starting to get too popular
    components["review_scarcity"] = review_scarcity

    # 2. Hours scarcity (closes early = local favorite)
    hours_scarcity = 0
    if closes_early and typical_close_hour:
        if typical_close_hour <= 16:
            hours_scarcity = 1.0  # Lunch-only = very local
        elif typical_close_hour <= 18:
            hours_scarcity = 0.8  # Early dinner closing
        elif typical_close_hour <= 20:
            hours_scarcity = 0.5  # Closes by 20:00
        elif typical_close_hour < 22:
            hours_scarcity = 0.3  # Closes before 22:00
    components["hours_scarcity"] = hours_scarcity

    # 3. Days scarcity (fewer days = exclusive)
    days_scarcity = 0
    if days_open_count is not None and rating and rating >= 4.0:
        if days_open_count <= 2:
            days_scarcity = 1.0 if rating >= 4.5 else 0.7  # Very exclusive
        elif days_open_count <= 3:
            days_scarcity = 0.8 if rating >= 4.3 else 0.5  # Exclusive
        elif days_open_count <= 4:
            days_scarcity = 0.5 if rating >= 4.0 else 0.3  # Selective
        elif days_open_count == 5:
            days_scarcity = 0.2  # Standard weekdays
        elif days_open_count == 6:
            days_scarcity = 0.1  # Most restaurants
        # 7 days = 0 (always open, no scarcity)
    components["days_scarcity"] = days_scarcity

    # 4. Schedule scarcity (weekdays only = caters to locals)
    schedule_scarcity = 0
    if weekdays_only or closed_weekends:
        schedule_scarcity = 1.0  # Strong: doesn't need tourist weekend traffic
    elif closed_sunday:
        schedule_scarcity = 0.5  # Modest: family-run or traditional
    components["schedule_scarcity"] = schedule_scarcity

    # 5. Cuisine scarcity (rare in Brussels)
    cuisine_scarcity = RARE_CUISINES_BRUSSELS.get(cuisine, 0)
    components["cuisine_scarcity"] = cuisine_scarcity

    # Combine with weights
    # Hours + Days + Schedule are all about "limited availability"
    # Review count is about "not over-exposed"
    # Cuisine scarcity is minimal - rare cuisine doesn't mean good food
    weights = {
        "review_scarcity": 0.25,    # Not over-hyped
        "hours_scarcity": 0.25,     # Limited hours
        "days_scarcity": 0.30,      # Limited days (strongest signal)
        "schedule_scarcity": 0.15,  # Weekend closures
        "cuisine_scarcity": 0.05,   # Rare cuisine type (minimal weight)
    }

    total = sum(weights[k] * components[k] for k in weights)

    return total, components


def reputation_uncertainty_score(name, rating, review_count):
    """
    Calculate reputation uncertainty - how much we should discount the rating.

    This is NOT about detecting fraud, but about statistical confidence:
    1. Perfect 5.0 ratings are unstable (one bad review changes everything)
    2. Extreme review counts suggest tourist-heavy, not necessarily local quality
    3. SEO-heavy names suggest marketing focus over food focus

    Returns: uncertainty score (0-1, higher = less confident in rating)
    """
    uncertainty = 0
    flags = []

    # 1. Name signals (SEO focus = marketing over quality)
    name_len = len(name) if name else 0

    # Very long names suggest marketing focus
    if name_len > 80:
        uncertainty += 0.3
        flags.append("marketing_heavy_name")
    elif name_len > 60:
        uncertainty += 0.15
        flags.append("long_name")

    # Pipe separators are SEO patterns - strong penalty
    if name and '|' in name:
        uncertainty += 0.25
        flags.append("seo_formatting")

    # Multiple dashes often indicate keyword stuffing
    if name and name.count(' - ') >= 2:
        uncertainty += 0.08
        flags.append("keyword_rich_name")

    # SEO keywords in name
    seo_keywords = ['best', 'top', '#1', 'near', 'famous']
    if name:
        name_lower = name.lower()
        for keyword in seo_keywords:
            if keyword in name_lower:
                uncertainty += 0.08
                flags.append(f"promotional_name")
                break  # Only penalize once

    # 2. Perfect ratings - statistically unstable
    # New places often start with 5.0 (friends/family, nobody wants to be first bad review)
    # This is natural, not fraud - but we should be cautious
    if rating == 5.0 and review_count:
        if review_count > 200:
            # 5.0 with >200 reviews is statistically very rare - strong penalty
            uncertainty += 0.40
            flags.append("statistically_unlikely_perfect")
        elif review_count > 100:
            # Still unusual but could be legitimate niche place
            uncertainty += 0.15
            flags.append("unusually_perfect")
        # < 100 reviews with 5.0 is normal for new places, no penalty

    # 3. Extreme review counts (tourist magnet effect)
    # High volume often means tourist-optimized, not local quality
    if review_count:
        if review_count > 15000:
            # Very extreme - strong penalty
            uncertainty += 0.35
            flags.append("tourist_volume")
        elif review_count > 10000:
            uncertainty += 0.20
            flags.append("high_volume")

    # 4. High rating + extreme reviews = tourist trap pattern
    if rating and rating >= 4.8 and review_count and review_count > 8000:
        uncertainty += 0.25
        flags.append("tourist_trap_pattern")

    # Cap at 1.0
    return min(1.0, uncertainty), flags


def is_family_restaurant_name(name):
    """
    Detect family restaurant naming patterns.

    Bourdain philosophy: "Chez [Name]" restaurants are typically family-run
    establishments with authentic, personal cooking. Same for patterns like
    "La Maison de [Name]", "[Name]'s Kitchen", etc.

    Returns: (is_family: bool, pattern_matched: str or None)
    """
    if not name:
        return False, None

    import re
    name_lower = name.lower().strip()

    # French patterns (common in Brussels)
    # "Chez Marie", "Chez Papa", etc.
    if re.match(r"^chez\s+\w+", name_lower):
        return True, "chez"

    # "La Maison de X", "Maison X"
    if re.match(r"^(la\s+)?maison\s+(de\s+)?\w+", name_lower):
        return True, "maison"

    # "Au Bon X", "Au Vieux X" - traditional Belgian/French naming
    if re.match(r"^au\s+(bon|vieux|petit)\s+", name_lower):
        return True, "au_tradition"

    # Dutch/Flemish patterns
    # "Bij X", "'t Huisje van X"
    if re.match(r"^bij\s+\w+", name_lower):
        return True, "bij"

    if re.match(r"^'?t\s+\w+", name_lower):
        return True, "t_diminutive"

    # English patterns (less common but exist)
    # "X's Kitchen", "Mama X's"
    if re.search(r"\b(mama|papa|nonna|oma|opa)\b", name_lower):
        return True, "family_title"

    return False, None


def eu_bubble_penalty(lat, lng, price_level, review_languages=None):
    """
    Penalty for EU bubble restaurants.
    High price + near Schuman + English-heavy = expat-targeted.
    """
    dist_eu = distance_to_eu_quarter(lat, lng)

    # Only applies within 1km of EU quarter
    if dist_eu > 1.0:
        return 0

    proximity_score = 1 - (dist_eu / 1.0)

    # Price component (expensive = more likely EU bubble)
    price_score = 0
    if price_level and price_level >= 3:
        price_score = (price_level - 2) / 2

    # Language component
    language_score = 0
    if review_languages:
        total = sum(review_languages.values())
        if total > 0:
            english_pct = review_languages.get("en", 0) / total
            if english_pct > 0.7:
                language_score = 0.5

    return proximity_score * (0.4 * price_score + 0.3 * language_score + 0.3)


def calculate_brussels_score(restaurant, commune_review_totals, cuisine_counts_by_commune):
    """
    Calculate the Brussels-specific restaurant score.

    Score components:
    - Base quality (rating + ML residual)
    - Tourist trap penalty
    - Diaspora authenticity bonus
    - Commune visibility boost
    - Independent restaurant bonus
    - Cold-start correction
    - Cuisine rarity reward
    - EU bubble penalty
    """
    name = restaurant.get("name", "")
    lat = restaurant.get("lat")
    lng = restaurant.get("lng")
    rating = restaurant.get("rating", 0)
    residual = restaurant.get("residual", 0)
    cuisine = restaurant.get("cuisine", "Other")
    review_count = restaurant.get("review_count", 0)
    is_chain = restaurant.get("is_chain", False)
    price_level = restaurant.get("price_numeric", 2)
    review_languages = restaurant.get("review_languages")  # Dict of lang -> count

    # Determine commune
    commune = get_commune(lat, lng) if lat and lng else "Bruxelles"

    # Get neighborhood context
    neighborhood, neighborhood_data = get_neighborhood(lat, lng) if lat and lng else (None, None)

    # Check tier override from neighborhood
    tier = "mixed"
    if neighborhood_data:
        tier = neighborhood_data.get("tier", "mixed")
    else:
        tier = COMMUNES.get(commune, {}).get("tier", "mixed")

    # === NORMALIZED SCORING SYSTEM (0-1 scale) ===
    #
    # Design: All components sum to ~1.0 for a "perfect" restaurant.
    # Penalties can push below 0, bonuses rarely exceed 1.0.
    # Final score is clamped to [0, 1] for display.
    #
    # Weight budget (positive components sum to ~1.0):
    #   Base quality:     0.35 (35%) - Google rating is primary signal
    #   ML residual:      0.20 (20%) - Undervaluation detection
    #   Scarcity:         0.12 (12%) - Limited hours/days = local gem
    #   Independent:      0.10 (10%) - Non-chain bonus
    #   Guide recognition: 0.08 (8%) - Michelin/GaultMillau
    #   Reddit:           0.05 (5%) - Community endorsement
    #   Local street:     0.04 (4%) - Known foodie streets
    #   Diaspora:         0.03 (3%) - Authenticity signal
    #   Family name:      0.02 (2%) - "Chez X" pattern
    #   Cuisine rarity:   0.01 (1%) - Rare cuisines
    #   ─────────────────────────────
    #   Total positive:   1.00 (100%)

    # 0. Review count - Brussels "Saturation Curve"
    # In a mid-sized European capital (1.2M people), review count is a proxy for commercialization
    # Unlike NYC/London, Brussels locals don't generate 2000+ reviews for authentic spots
    #
    # Exception: Friteries (fritkots) are high-turnover by design and can be authentic with 3000+ reviews
    KNOWN_FRITKOTS = ["maison antoine", "chez clementine", "la baraque à frites"]
    name_lower = name.lower() if name else ""
    is_fritkot = cuisine in ["Fast Food", "Belgian"] and (
        any(term in name_lower for term in ["frit", "fritkot", "frituur", "friterie", "friture"]) or
        any(known in name_lower for known in KNOWN_FRITKOTS)
    )

    if review_count < 10:
        # Extremely few reviews = statistically meaningless rating
        # Harsh but not overwhelming (-0.35 instead of -0.60)
        review_adjustment = -0.35
    elif review_count < 20:
        # Still very few reviews = strong penalty (scales -0.35 to -0.15)
        review_adjustment = -0.35 + 0.20 * ((review_count - 10) / 10)
    elif review_count < 35:
        # Getting there but still limited data (scales -0.15 to 0)
        review_adjustment = -0.15 * (1 - (review_count - 20) / 15)
    elif review_count <= 100:
        # "Discovery" zone - slight bonus for emerging spots
        review_adjustment = 0.03
    elif review_count <= 500:
        # "Sweet Spot" - the Goldilocks zone
        # Enough social proof, but clientele is likely locals/EU expats
        review_adjustment = 0.05
    elif review_count <= 800:
        # "Famous Local" zone - institutions like Fin de Siècle
        review_adjustment = 0.02
    elif review_count <= 1200:
        # Transition zone - getting popular
        review_adjustment = 0
    elif review_count <= 1500:
        # Warning zone
        review_adjustment = -0.03
    elif is_fritkot:
        # Fritkot exception: high-turnover by design
        review_adjustment = 0
    elif tier in ["local_foodie", "diaspora_hub", "underexplored"]:
        # High-volume in LOCAL areas - could be old institution OR new delivery-optimized
        penalty_factor = min(1.0, (review_count - 1500) / 8000)
        review_adjustment = -0.03 - (0.07 * penalty_factor)  # -0.03 to -0.10
    else:
        # "Disneyfication" zone (1500+ reviews in tourist/mixed areas)
        penalty_factor = min(1.0, (review_count - 1500) / 5000)
        review_adjustment = -0.08 - (0.12 * penalty_factor)  # -0.08 to -0.20

    # 1. Base quality (35% weight) - primary driver
    # A 5.0★ restaurant gets full 0.35, a 4.0★ gets 0.28, a 3.0★ gets 0.21
    base_quality = 0.35 * (rating / 5.0) if rating else 0

    # 2. ML residual (20% weight) - undervaluation detection
    # Residual typically ranges -0.5 to +0.5, we scale and clamp
    residual_score = 0.20 * min(1.0, max(-1.0, residual * 2))

    # 3. Tourist trap penalty (up to -15%)
    tourist_penalty = -0.15 * tourist_trap_score(lat, lng, rating, review_count, review_languages) if lat and lng else 0

    # 4. Diaspora authenticity bonus (3% weight)
    # Meaningful but not dominant - rewards authentic diaspora spots
    diaspora_bonus = 0.03 * diaspora_authenticity_score(cuisine, commune, review_languages)

    # 5. Independent restaurant bonus (10% weight)
    independent_bonus = 0.10 * (0 if is_chain else 1)

    # 6. Cuisine rarity bonus (1% weight)
    # Small but noticeable - rewards rare cuisines in Brussels
    rarity_bonus = 0.01 * cuisine_rarity_score(cuisine, commune, cuisine_counts_by_commune)

    # 7. EU bubble penalty (up to -3%)
    eu_penalty = -0.03 * eu_bubble_penalty(lat, lng, price_level, review_languages) if lat and lng else 0

    # 8. Price/quality mismatch penalty
    price_quality_penalty = 0
    if price_level and rating:
        if price_level == 4:  # Very expensive
            expected_rating = 4.5
            if rating < expected_rating:
                price_quality_penalty = -0.10 * (expected_rating - rating)
        elif price_level == 3:  # Expensive
            expected_rating = 4.3
            if rating < expected_rating:
                price_quality_penalty = -0.06 * (expected_rating - rating)

    # 9. Local street bonus (4% weight)
    local_street_bonus = 0
    local_street_name = None
    if lat and lng:
        is_local, street_name = is_on_local_street(lat, lng)
        if is_local:
            local_street_bonus = 0.04
            local_street_name = street_name

    # 10. Scarcity score (12% weight)
    # Combines: hours, days, schedule, rare cuisine
    scarcity_total, scarcity_components = unified_scarcity_score(restaurant)
    scarcity_bonus = 0.12 * scarcity_total

    # Extract individual values for transparency/debugging
    closes_early = restaurant.get("closes_early", False)
    typical_close_hour = restaurant.get("typical_close_hour")
    weekdays_only = restaurant.get("weekdays_only", False)
    closed_weekends = restaurant.get("closed_weekends", False)
    closed_sunday = restaurant.get("closed_sunday", False)
    days_open_count = restaurant.get("days_open_count")

    # 11. Guide recognition bonus (up to 8%)
    guide_bonus = 0
    michelin_stars = has_michelin_recognition(name)
    is_bib_gourmand = has_bib_gourmand(name)
    is_gault_millau = has_gault_millau(name)

    if michelin_stars >= 2:
        guide_bonus = 0.08  # 2+ stars: full bonus
    elif michelin_stars == 1:
        guide_bonus = 0.06  # 1 star
    elif is_bib_gourmand:
        guide_bonus = 0.04  # Bib Gourmand
    elif is_gault_millau:
        guide_bonus = 0.03  # Gault Millau only

    # 12. Reddit community endorsement (5% weight)
    reddit_score, reddit_mentions = reddit_community_score(name, review_count)
    reddit_bonus = 0.05 * reddit_score

    # 13. Perfection penalty (up to -4%)
    # 5.0★ with few reviews is statistically suspicious
    perfection_penalty = 0
    if rating >= 5.0:
        if review_count < 50:
            perfection_penalty = -0.04
        elif review_count < 100:
            perfection_penalty = -0.02
        elif review_count < 200:
            perfection_penalty = -0.01
    elif rating >= 4.9:
        if review_count < 30:
            perfection_penalty = -0.02

    # 14. AFSCA Hygiene certification (informational only)
    address = restaurant.get("address", "")
    afsca_score = get_afsca_score(name, address)
    has_afsca_smiley = afsca_score > 0

    # 15. Family restaurant bonus (2% weight)
    is_family_name, family_pattern = is_family_restaurant_name(name)
    family_bonus = 0.02 if (is_family_name and not is_chain) else 0

    # 16. Cuisine specificity bonus (up to 2%)
    cuisine_specificity = get_cuisine_specificity_bonus(cuisine)
    specificity_bonus = 0.02 * cuisine_specificity

    # 17. Non-restaurant shop penalty
    is_shop = is_non_restaurant_shop(name)
    shop_penalty = -0.80 if is_shop else 0

    # 18. Diaspora context (informational - for UI display only)
    diaspora_context = get_diaspora_context(cuisine, commune, lat, lng)

    # 19. Bruxellois authenticity bonus (up to 5%)
    # Rewards authentic Brussels establishments: friteries in working-class
    # communes and curated list of local institutions
    bruxellois_score = bruxellois_authenticity_score(name, commune)
    bruxellois_bonus = 0.05 * bruxellois_score

    # Total score (sum of all components)
    total = (
        review_adjustment +
        base_quality +
        residual_score +
        tourist_penalty +
        diaspora_bonus +
        independent_bonus +
        rarity_bonus +
        eu_penalty +
        price_quality_penalty +
        local_street_bonus +
        scarcity_bonus +
        guide_bonus +
        reddit_bonus +
        perfection_penalty +
        family_bonus +
        specificity_bonus +
        shop_penalty +
        bruxellois_bonus
    )

    # Clamp to [0, 1] for normalized output
    total = max(0.0, min(1.0, total))

    # Determine restaurant quality tier based on score (Kitchen Confidential theme)
    # Thresholds calibrated for ~15% Chef's Kiss, ~20% Kitchen Approved
    if total >= 0.60:
        restaurant_tier = "Chef's Kiss"
    elif total >= 0.50:
        restaurant_tier = "Kitchen Approved"
    elif total >= 0.40:
        restaurant_tier = "Workable"
    else:
        restaurant_tier = "Line Cook Shrug"

    # Return score and component breakdown
    return {
        "brussels_score": total,
        "commune": commune,
        "neighborhood": neighborhood,
        "local_street": local_street_name,
        "commune_tier": tier,  # Renamed: this is the commune/neighborhood tier
        "tier": restaurant_tier,  # This is the restaurant quality tier
        "closes_early": closes_early,
        "typical_close_hour": typical_close_hour,
        "weekdays_only": weekdays_only,
        "closed_sunday": closed_sunday,
        "days_open_count": days_open_count,
        "is_rare_cuisine": RARE_CUISINES_BRUSSELS.get(cuisine, 0) > 0,
        "michelin_stars": michelin_stars,
        "bib_gourmand": is_bib_gourmand,
        "gault_millau": is_gault_millau,
        "reddit_mentions": reddit_mentions,  # Number of Reddit mentions
        "has_afsca_smiley": has_afsca_smiley,  # AFSCA hygiene certification
        "is_family_restaurant": is_family_name,  # "Chez X" family naming pattern
        "family_pattern": family_pattern,  # Type of pattern matched
        "scarcity_components": scarcity_components,  # Detailed breakdown
        "diaspora_context": diaspora_context,  # Diaspora geography info (for UI display)
        "components": {
            "review_adjustment": review_adjustment,  # Saturation curve
            "base_quality": base_quality,  # 35% weight
            "residual_score": residual_score,  # 20% weight
            "tourist_penalty": tourist_penalty,
            "diaspora_bonus": diaspora_bonus,  # 3% weight
            "independent_bonus": independent_bonus,  # 10% weight
            "rarity_bonus": rarity_bonus,  # 1% weight
            "eu_penalty": eu_penalty,
            "price_quality_penalty": price_quality_penalty,
            "local_street_bonus": local_street_bonus,  # 4% weight
            "scarcity_bonus": scarcity_bonus,  # 12% weight
            "guide_bonus": guide_bonus,  # Up to 8%
            "reddit_bonus": reddit_bonus,  # 5% weight
            "perfection_penalty": perfection_penalty,
            "family_bonus": family_bonus,  # 2% weight
            "specificity_bonus": specificity_bonus,  # Up to 2%
            "shop_penalty": shop_penalty,
        }
    }


def rerank_restaurants(df):
    """
    Apply Brussels-specific reranking to restaurant dataframe.
    """
    # Calculate commune-level statistics
    df["commune"] = df.apply(
        lambda r: get_commune(r["lat"], r["lng"]) if pd.notna(r["lat"]) and pd.notna(r["lng"]) else "Bruxelles",
        axis=1
    )

    # Re-check chains against CHAIN_PATTERNS (overrides features.py chain detection)
    # This allows adding new chain patterns without re-running full pipeline
    original_chains = df["is_chain"].sum() if "is_chain" in df.columns else 0
    df["is_chain"] = df["name"].apply(is_chain_restaurant)
    new_chains = df["is_chain"].sum()
    if new_chains > original_chains:
        newly_flagged = df[df["is_chain"]]["name"].unique().tolist()
        print(f"\nFlagged {new_chains} chains (was {original_chains}):")
        for chain in newly_flagged[:10]:
            print(f"  - {chain}")

    commune_review_totals = df.groupby("commune")["review_count"].sum().to_dict()

    cuisine_counts_by_commune = {}
    for commune in df["commune"].unique():
        commune_df = df[df["commune"] == commune]
        cuisine_counts_by_commune[commune] = commune_df["cuisine"].value_counts().to_dict()

    # Calculate Brussels score for each restaurant
    results = []
    for _, row in df.iterrows():
        restaurant = row.to_dict()
        score_data = calculate_brussels_score(
            restaurant,
            commune_review_totals,
            cuisine_counts_by_commune
        )
        results.append(score_data)

    # Add new columns
    df["brussels_score"] = [r["brussels_score"] for r in results]
    df["neighborhood"] = [r["neighborhood"] for r in results]
    df["local_street"] = [r["local_street"] for r in results]
    df["tier"] = [r["tier"] for r in results]  # Restaurant quality tier (Chef's Kiss, etc.)
    df["commune_tier"] = [r["commune_tier"] for r in results]  # Commune/neighborhood type
    df["closes_early"] = [r["closes_early"] for r in results]
    df["typical_close_hour"] = [r["typical_close_hour"] for r in results]
    df["weekdays_only"] = [r["weekdays_only"] for r in results]
    df["closed_sunday"] = [r["closed_sunday"] for r in results]
    df["days_open_count"] = [r["days_open_count"] for r in results]
    df["is_rare_cuisine"] = [r["is_rare_cuisine"] for r in results]
    df["michelin_stars"] = [r["michelin_stars"] for r in results]
    df["bib_gourmand"] = [r["bib_gourmand"] for r in results]
    df["gault_millau"] = [r["gault_millau"] for r in results]
    df["reddit_mentions"] = [r["reddit_mentions"] for r in results]
    df["has_afsca_smiley"] = [r["has_afsca_smiley"] for r in results]
    df["diaspora_context"] = [r["diaspora_context"] for r in results]

    # Add component columns for debugging/transparency
    for component in ["review_adjustment", "tourist_penalty", "scarcity_bonus", "local_street_bonus", "perfection_penalty"]:
        df[f"score_{component}"] = [r["components"][component] for r in results]

    # Add scarcity sub-components for detailed analysis
    for sub in ["review_scarcity", "hours_scarcity", "days_scarcity", "schedule_scarcity", "cuisine_scarcity"]:
        df[f"scarcity_{sub}"] = [r["scarcity_components"][sub] for r in results]

    # Filter out non-restaurant shops (chocolate shops, etc.)
    # These should not appear in the database at all
    original_count = len(df)
    df["is_shop"] = df["name"].apply(is_non_restaurant_shop)
    shops_removed = df[df["is_shop"]]["name"].tolist()
    df = df[~df["is_shop"]].drop(columns=["is_shop"])
    if shops_removed:
        print(f"\nRemoved {len(shops_removed)} non-restaurant shops:")
        for shop in shops_removed[:10]:  # Show first 10
            print(f"  - {shop}")
        if len(shops_removed) > 10:
            print(f"  ... and {len(shops_removed) - 10} more")

    # Sort by Brussels score
    df = df.sort_values("brussels_score", ascending=False)

    return df


def print_reranking_analysis(df):
    """Print analysis of reranking results."""
    print("\n=== BRUSSELS RERANKING ANALYSIS ===\n")

    # Top 20 by Brussels score
    print("TOP 20 BY BRUSSELS SCORE:")
    top = df.nlargest(20, "brussels_score")
    for i, (_, r) in enumerate(top.iterrows(), 1):
        print(f"{i:2}. {r['name'][:35]:<35} | {r['rating']:.1f}★ | {r['commune']:<20} | Score: {r['brussels_score']:.3f}")

    print("\n" + "="*80)

    # Top by commune
    print("\nTOP RESTAURANT BY COMMUNE:")
    for commune in sorted(df["commune"].unique()):
        commune_df = df[df["commune"] == commune]
        if len(commune_df) > 0:
            top_in_commune = commune_df.nlargest(1, "brussels_score").iloc[0]
            print(f"  {commune:<25}: {top_in_commune['name'][:30]:<30} ({top_in_commune['rating']:.1f}★)")

    print("\n" + "="*80)

    # Biggest winners from reranking
    print("\nBIGGEST WINNERS (Brussels score vs pure rating rank):")
    df["rating_rank"] = df["rating"].rank(ascending=False, method="min")
    df["brussels_rank"] = df["brussels_score"].rank(ascending=False, method="min")
    df["rank_improvement"] = df["rating_rank"] - df["brussels_rank"]

    winners = df.nlargest(10, "rank_improvement")
    for _, r in winners.iterrows():
        print(f"  {r['name'][:35]:<35} | {r['commune']:<15} | Moved up {int(r['rank_improvement'])} positions")

    print("\n" + "="*80)

    # Diaspora highlights
    print("\nTOP DIASPORA RESTAURANTS:")
    diaspora_cuisines = ["Congolese", "African", "Moroccan", "Turkish", "Lebanese", "Ethiopian"]
    diaspora_df = df[df["cuisine"].isin(diaspora_cuisines)]
    if len(diaspora_df) > 0:
        for _, r in diaspora_df.nlargest(10, "brussels_score").iterrows():
            print(f"  {r['name'][:30]:<30} | {r['cuisine']:<12} | {r['commune']:<15} | {r['rating']:.1f}★")

    print("\n" + "="*80)

    # Underexplored commune highlights
    print("\nBEST IN UNDEREXPLORED COMMUNES:")
    underexplored = ["Anderlecht", "Forest", "Jette", "Ganshoren", "Evere", "Koekelberg", "Berchem-Sainte-Agathe"]
    under_df = df[df["commune"].isin(underexplored)]
    if len(under_df) > 0:
        for _, r in under_df.nlargest(10, "brussels_score").iterrows():
            print(f"  {r['name'][:30]:<30} | {r['commune']:<20} | {r['rating']:.1f}★ | {r['review_count']} reviews")


if __name__ == "__main__":
    # Load processed data
    df = pd.read_csv("../data/restaurants_with_predictions.csv")
    print(f"Loaded {len(df)} restaurants")

    # Apply Brussels reranking
    df = rerank_restaurants(df)

    # Print analysis
    print_reranking_analysis(df)

    # Save reranked data
    df.to_csv("../data/restaurants_brussels_reranked.csv", index=False)
    print(f"\nSaved reranked data to ../data/restaurants_brussels_reranked.csv")

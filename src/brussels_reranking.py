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
    DIASPORA_STREETS, LOCAL_FOOD_STREETS,
    get_commune, get_neighborhood, get_diaspora_context,
    distance_to_grand_place, distance_to_eu_quarter,
    haversine_distance, is_on_local_street,
    has_michelin_recognition, has_gault_millau, has_bib_gourmand,
    get_cuisine_specificity_bonus, is_non_restaurant_shop,
    is_chain_restaurant, get_authenticity_markers
)
from afsca_hygiene import get_afsca_score, match_restaurant


# ============================================================================
# STATISTICAL UTILITY FUNCTIONS
# ============================================================================

def sigmoid(x, center=0, steepness=1):
    """
    Smooth sigmoid function for gradual transitions instead of hard cutoffs.

    Args:
        x: Input value
        center: Value where sigmoid returns 0.5
        steepness: How sharp the transition is (higher = sharper)

    Returns:
        Value between 0 and 1
    """
    return 1 / (1 + math.exp(-steepness * (x - center)))


def confidence_weight(review_count, min_reviews=10, half_confidence=50):
    """
    Calculate confidence weight based on review count using Bayesian approach.

    Uses the formula: confidence = 1 - 1/sqrt(1 + review_count/k)
    where k controls how quickly confidence grows.

    Args:
        review_count: Number of reviews
        min_reviews: Below this, confidence is very low
        half_confidence: Reviews needed for 50% confidence

    Returns:
        Confidence weight between 0 and 1
    """
    if review_count < min_reviews:
        # Very low confidence for tiny sample sizes
        return 0.3 * (review_count / min_reviews)

    # Bayesian-style confidence that asymptotes to 1.0
    # At half_confidence reviews, this returns ~0.71
    # At 200 reviews, this returns ~0.90
    # At 500 reviews, this returns ~0.95
    return 1 - 1 / math.sqrt(1 + review_count / half_confidence)


def smooth_threshold(value, threshold, transition_width=0.2):
    """
    Smooth transition around a threshold instead of hard cutoff.

    Args:
        value: The value to check
        threshold: The center threshold
        transition_width: Width of transition zone (as fraction of threshold)

    Returns:
        0 to 1, where 0 = well below threshold, 1 = well above
    """
    width = threshold * transition_width
    return sigmoid(value, center=threshold, steepness=4/width)


def normalize_weights(components):
    """
    Normalize a dict of component weights to sum to exactly 1.0.

    Args:
        components: Dict of {name: weight}

    Returns:
        Dict with normalized weights
    """
    total = sum(abs(v) for v in components.values() if v > 0)
    if total == 0:
        return components
    return {k: v / total if v > 0 else v for k, v in components.items()}


# ============================================================================
# WEIGHT CONFIGURATION (normalized to sum to 1.0)
# ============================================================================

# Positive component weights (must sum to 1.0)
POSITIVE_WEIGHTS = {
    'base_quality': 0.32,      # Google rating (reduced from 0.35)
    'ml_residual': 0.18,       # Undervaluation detection (reduced from 0.20)
    'scarcity': 0.12,          # Limited hours/days
    'independent': 0.10,       # Non-chain bonus
    'guide': 0.08,             # Michelin/GaultMillau
    'diaspora': 0.07,          # Location authenticity
    'reddit': 0.05,            # Community endorsement
    'bruxellois': 0.04,        # Local institutions (reduced from 0.05)
    'family_name': 0.02,       # "Chez X" pattern
    'specificity': 0.01,       # Regional cuisines
    'cuisine_rarity': 0.01,    # Rare in Brussels
}
# Verify: sum = 0.32 + 0.18 + 0.12 + 0.10 + 0.08 + 0.07 + 0.05 + 0.04 + 0.02 + 0.01 + 0.01 = 1.00

# Penalty caps (these subtract from the score)
PENALTY_CAPS = {
    'tourist_trap': -0.15,
    'chain': -0.10,
    'low_review': -0.15,       # Reduced from -0.20, now uses confidence weighting
    'eu_bubble': -0.03,
    'price_quality': -0.10,
    'shop': -0.80,
}


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


def diaspora_bonus_score(cuisine, commune, lat, lng, review_languages=None):
    """
    Calculate unified diaspora bonus score (0-1).

    Only gives bonus when cuisine matches the area's diaspora community.
    An Italian restaurant in Matongé gets no bonus - only Congolese/African does.

    Signals:
    1. Cuisine/commune match: is this a diaspora cuisine in its community's area?
    2. Diaspora street: is the restaurant on a known food corridor for this cuisine?

    Higher = more authentic diaspora restaurant.
    """
    commune_score = 0
    street_name = None
    is_on_matching_street = False

    # 1. Check diaspora cuisine authenticity matrix (cuisine + commune)
    # This is the PRIMARY check - no bonus if cuisine doesn't match area
    if cuisine in DIASPORA_AUTHENTICITY:
        commune_scores = DIASPORA_AUTHENTICITY[cuisine]
        if commune in commune_scores:
            commune_score = commune_scores[commune]
        else:
            # Small bonus for diaspora cuisine outside typical areas
            # (could still be authentic, just in different location)
            commune_score = 0.2

    # Check Belgian traditional authenticity
    if cuisine in BELGIAN_AUTHENTICITY:
        commune_scores = BELGIAN_AUTHENTICITY[cuisine]
        if commune in commune_scores:
            commune_score = max(commune_score, commune_scores[commune])

    # 2. Street bonus ONLY if cuisine matches the street's diaspora community
    # An Indian restaurant on Chaussée de Wavre (Matongé) gets NO street bonus
    # because Matongé is known for Congolese/African cuisine, not Indian.
    # A Turkish restaurant on Chaussée de Haecht DOES get the bonus.
    if commune_score > 0 and lat and lng:
        is_local, local_street_name = is_on_local_street(lat, lng)
        if is_local:
            # Check if this street is actually relevant for this cuisine
            # by looking at DIASPORA_STREETS mapping
            street_matches_cuisine = False
            if cuisine in DIASPORA_STREETS:
                cuisine_streets = DIASPORA_STREETS[cuisine]
                for street_info in cuisine_streets:
                    diaspora_street_name = street_info["name"]
                    # Normalize both names for comparison:
                    # Extract key words and check for overlap
                    # e.g., "Matongé (Chaussée de Wavre)" and "Chaussée de Wavre (Matongé)"
                    # should match because they share "Matongé" and "Chaussée de Wavre"
                    local_words = set(local_street_name.lower().replace('(', ' ').replace(')', ' ').split())
                    diaspora_words = set(diaspora_street_name.lower().replace('(', ' ').replace(')', ' ').split())
                    # Remove common French words that don't help matching
                    stopwords = {'de', 'la', 'le', 'du', 'des', 'l', 'd'}
                    local_words -= stopwords
                    diaspora_words -= stopwords
                    # Check if there's significant overlap (at least 1 meaningful word)
                    overlap = local_words & diaspora_words
                    if len(overlap) >= 1:
                        street_matches_cuisine = True
                        break

            if street_matches_cuisine:
                street_name = local_street_name
                is_on_matching_street = True
                # Boost the commune score if on a MATCHING street
                commune_score = min(1.0, commune_score + 0.3)
            # If on a local food street but NOT matching cuisine, no street bonus
            # (but commune_score from DIASPORA_AUTHENTICITY still applies)

    # Boost if reviews are in diaspora languages
    if review_languages and commune_score > 0:
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
                commune_score = min(1.0, commune_score + 0.2 * relevant_pct)

    return commune_score, street_name


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


def parse_opening_hours(opening_hours_str):
    """
    Parse Google Maps opening hours string into structured data.

    Input format: "['Monday: 11:30 AM – 2:00 PM, 5:00 PM – 1:00 AM', 'Tuesday: Closed', ...]"

    Returns dict with:
    - days_open: number of days open (0-7)
    - total_hours_per_week: approximate total hours open
    - latest_close_hour: latest closing hour (0-23, where 1 = 1am next day)
    - has_service_coupe: True if has afternoon break (closes ~15:00, reopens ~18:00)
    - closes_late: True if regularly closes after 1:00 AM
    - is_lunch_only: True if closes before 17:00 most days
    """
    import ast
    import re

    result = {
        "days_open": 0,
        "total_hours_per_week": 0,
        "latest_close_hour": 0,
        "has_service_coupe": False,
        "closes_late": False,
        "is_lunch_only": False,
        "parsed": False
    }

    if not opening_hours_str or pd.isna(opening_hours_str):
        return result

    try:
        # Parse the string as a Python list
        hours_list = ast.literal_eval(opening_hours_str)
        if not isinstance(hours_list, list):
            return result

        days_open = 0
        total_hours = 0
        close_hours = []
        service_coupe_count = 0
        late_close_count = 0
        early_close_count = 0

        for day_str in hours_list:
            if not isinstance(day_str, str):
                continue

            # Check if closed
            if "Closed" in day_str or "closed" in day_str:
                continue

            days_open += 1

            # Extract time ranges - handle unicode characters
            # Format: "Monday: 11:30 AM – 2:00 PM, 5:00 PM – 1:00 AM"
            day_str_clean = day_str.replace('\u202f', ' ').replace('\u2009', ' ').replace('–', '-').replace('—', '-')

            # Find all time ranges
            time_pattern = r'(\d{1,2}):?(\d{2})?\s*(AM|PM|am|pm)?\s*-\s*(\d{1,2}):?(\d{2})?\s*(AM|PM|am|pm)?'
            matches = re.findall(time_pattern, day_str_clean)

            day_close_hours = []
            day_open_hours = []

            for match in matches:
                open_hour = int(match[0])
                open_ampm = match[2].upper() if match[2] else None
                close_hour = int(match[3])
                close_ampm = match[5].upper() if match[5] else None

                # Convert to 24-hour format
                # If open_ampm is missing, infer from close_ampm and context
                if open_ampm == 'PM' and open_hour != 12:
                    open_hour += 12
                elif open_ampm == 'AM' and open_hour == 12:
                    open_hour = 0
                elif open_ampm is None:
                    # Infer: if close is PM and open < close, open is likely same period
                    # Exception: 12:00-2:00 PM means 12:00 PM (noon)
                    if close_ampm == 'PM':
                        if open_hour <= close_hour or open_hour == 12:
                            # Same period: 12:00-2:00 PM or 1:00-3:00 PM
                            if open_hour != 12:
                                open_hour += 12
                        else:
                            # Cross-period: 7:00-10:00 PM means 7:00 PM
                            open_hour += 12
                    elif close_ampm == 'AM':
                        # Late night: 10:00-2:00 AM means 10:00 PM to 2:00 AM
                        if open_hour >= 6:  # Assume evening start
                            open_hour += 12

                if close_ampm == 'PM' and close_hour != 12:
                    close_hour += 12
                elif close_ampm == 'AM' and close_hour == 12:
                    close_hour = 0

                # Handle overnight closing (e.g., closes at 1 AM = 25 for calculation)
                if close_hour < open_hour:
                    close_hour += 24

                day_open_hours.append(open_hour)
                day_close_hours.append(close_hour)

                # Calculate hours for this shift
                shift_hours = close_hour - open_hour
                if shift_hours > 0:
                    total_hours += shift_hours

            # Check for service coupé (gap between ~14:00-15:00 and ~18:00-19:00)
            if len(matches) >= 2:
                # Multiple time ranges = likely service coupé
                if day_open_hours and day_close_hours:
                    # Check if first shift ends around lunch (13-16) and second starts evening (17-20)
                    first_close = day_close_hours[0] if len(day_close_hours) > 0 else 0
                    second_open = day_open_hours[1] if len(day_open_hours) > 1 else 0
                    if 13 <= first_close <= 16 and 17 <= second_open <= 20:
                        service_coupe_count += 1

            # Track latest close hour
            if day_close_hours:
                latest = max(day_close_hours)
                # Normalize: 25 = 1am, 26 = 2am, etc.
                if latest > 24:
                    latest = latest - 24
                close_hours.append(latest)

                # Late close = after 1:00 AM (represented as 1 after normalization)
                if max(day_close_hours) >= 25:  # 1:00 AM or later
                    late_close_count += 1

                # Early close = before 5:00 PM
                if max(day_close_hours) <= 17:
                    early_close_count += 1

        result["days_open"] = days_open
        result["total_hours_per_week"] = total_hours
        result["latest_close_hour"] = max(close_hours) if close_hours else 0
        result["has_service_coupe"] = service_coupe_count >= 3  # At least 3 days with service coupé
        result["closes_late"] = late_close_count >= 3  # At least 3 days closing after 1 AM
        result["is_lunch_only"] = early_close_count >= 4 and days_open >= 4  # Closes early most days
        result["parsed"] = True

    except Exception as e:
        # Parsing failed, return defaults
        pass

    return result


def calculate_horseshoe_bonus(restaurant):
    """
    Calculate the "Horseshoe Theory" bonus for operating hours.

    The horseshoe rewards BOTH extremes of the operating hours spectrum:

    1. "Lark Bonus" (The Artisan) - Left tail of horseshoe
       - Open < 30 hours/week OR has service coupé
       - Signals: "I prioritize prep time and quality over revenue"
       - Examples: Sourdough bakery, supper club, serious bistro

    2. "Owl Bonus" (The Community Anchor) - Right tail of horseshoe
       - Open past 1:00 AM regularly
       - Signals: "I work incredibly hard to serve when others won't"
       - Examples: Late-night pitta, frituur, neighborhood bar

    3. "Middle Zone" (The Factory) - No bonus
       - Standard 7-day, 11:00-22:00 non-stop
       - Signals: "I maximize table turnover"
       - Examples: Chains, tourist traps, generic brasseries

    Returns: (bonus_score 0-1, bonus_type string or None)
    """
    opening_hours = restaurant.get("opening_hours")
    rating = restaurant.get("rating", 0)

    # Only apply to restaurants with decent ratings
    if not rating or rating < 4.0:
        return 0, None

    # Parse hours
    hours_data = parse_opening_hours(opening_hours)

    if not hours_data["parsed"]:
        return 0, None

    # Check for Lark Bonus (Artisan)
    is_lark = False
    lark_score = 0

    # Service coupé is the strongest signal of serious cooking
    if hours_data["has_service_coupe"]:
        is_lark = True
        lark_score = 1.0  # Full bonus

    # Very limited hours (< 30h/week) also qualifies
    elif hours_data["total_hours_per_week"] > 0 and hours_data["total_hours_per_week"] < 30:
        is_lark = True
        lark_score = 0.8

    # Lunch-only spots (closes before 5pm most days)
    elif hours_data["is_lunch_only"]:
        is_lark = True
        lark_score = 0.7

    # Limited days (open 4 or fewer days)
    elif hours_data["days_open"] <= 4 and hours_data["days_open"] > 0:
        is_lark = True
        lark_score = 0.6

    # Check for Owl Bonus (Community Anchor)
    is_owl = False
    owl_score = 0

    if hours_data["closes_late"]:
        is_owl = True
        owl_score = 0.8  # Reward late-night service

    # A restaurant can be BOTH (rare but possible: limited days but late hours)
    # In that case, take the higher bonus
    if is_lark and is_owl:
        if lark_score >= owl_score:
            return lark_score, "lark"
        else:
            return owl_score, "owl"
    elif is_lark:
        return lark_score, "lark"
    elif is_owl:
        return owl_score, "owl"

    # Middle zone: no bonus
    return 0, None


def unified_scarcity_score(restaurant):
    """
    Calculate a unified scarcity score based on review count, cuisine rarity,
    and the "Horseshoe Theory" for operating hours.

    HORSESHOE THEORY (Jan 2025): Replaced linear hours bias with U-curve.

    The old "limited hours = quality" assumption was class-biased:
    - It rewarded privilege (can afford to close 3 days/week)
    - It penalized hardworking immigrant families (pittas, kebabs)

    NEW APPROACH: Reward BOTH extremes of the operating hours spectrum:
    - "Lark Bonus": Service coupé, <30h/week, lunch-only (artisan signal)
    - "Owl Bonus": Open past 1:00 AM (community anchor signal)
    - "Middle Zone": Standard 7-day 11:00-22:00 = no bonus (chains)

    Components:
    - Review count scarcity: "Goldilocks zone" of 50-500 reviews
    - Horseshoe bonus: Lark (artisan) or Owl (late-night) bonus
    - Cuisine scarcity: rare cuisines in Brussels (minimal weight)

    Returns tuple: (total_score, component_breakdown)
    """
    rating = restaurant.get("rating", 0)
    review_count = restaurant.get("review_count", 0)
    cuisine = restaurant.get("cuisine", "Other")

    components = {}

    # 1. Review count scarcity - the "Goldilocks Zone" with smooth transitions
    # Sweet spot: 50-500 reviews = established but not tourist-famous
    # This applies equally to all cuisines without class bias
    #
    # SMOOTHING (Jan 2026): Fixed the "review cliff" at 50 reviews.
    # Old approach had a 14% jump from 49→50 reviews due to:
    # - Penalty ending at 50
    # - Bonus starting at 50 (full value)
    # New approach uses gradual ramps to avoid gaming incentives.
    review_scarcity = 0
    if rating and review_count and rating >= 4.0:
        if 50 <= review_count <= 200:
            review_scarcity = 1.0  # Perfect: known locally, not over-hyped
        elif 200 < review_count <= 500:
            review_scarcity = 0.7  # Good: popular but not tourist-dominated
        elif 35 <= review_count < 50:
            # Gradual ramp from 0.3 to 0.9 (smoother transition to full bonus)
            # At 35: 0.3, at 49: 0.86
            review_scarcity = 0.3 + 0.6 * ((review_count - 35) / 15)
        elif 20 <= review_count < 35:
            # Neutral zone: no bonus, no penalty (was previously penalized)
            review_scarcity = 0.0
        elif 500 < review_count <= 1000:
            review_scarcity = 0.3  # Starting to get too popular
    components["review_scarcity"] = review_scarcity

    # 2. Horseshoe bonus - rewards BOTH extremes
    horseshoe_score, horseshoe_type = calculate_horseshoe_bonus(restaurant)
    components["horseshoe_bonus"] = horseshoe_score
    components["horseshoe_type"] = horseshoe_type  # "lark", "owl", or None

    # Legacy fields for backwards compatibility (kept at 0)
    components["hours_scarcity"] = 0
    components["days_scarcity"] = 0
    components["schedule_scarcity"] = 0

    # 3. Cuisine scarcity (rare in Brussels) - minimal weight
    # Rare cuisine doesn't mean good food, but adds diversity value
    cuisine_scarcity = RARE_CUISINES_BRUSSELS.get(cuisine, 0)
    components["cuisine_scarcity"] = cuisine_scarcity

    # Combine with weights
    weights = {
        "review_scarcity": 0.70,    # Primary: not over-hyped
        "horseshoe_bonus": 0.20,    # Secondary: artisan OR late-night
        "cuisine_scarcity": 0.10,   # Minor: rare cuisine diversity
    }

    total = (
        weights["review_scarcity"] * review_scarcity +
        weights["horseshoe_bonus"] * horseshoe_score +
        weights["cuisine_scarcity"] * cuisine_scarcity
    )

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


# ============================================================================
# SCORING COMPONENT FUNCTIONS (extracted from calculate_brussels_score)
# ============================================================================

def _calculate_review_adjustment(review_count, cuisine, name, tier):
    """
    Calculate review count adjustment based on Brussels saturation curve.

    Uses smooth sigmoid transitions instead of hard cutoffs for more
    statistically robust behavior at boundaries.

    In a mid-sized European capital (1.2M people), review count is a proxy
    for commercialization. Unlike NYC/London, Brussels locals don't generate
    2000+ reviews for authentic spots.

    Returns: float adjustment value (can be negative)
    """
    # Fritkot exception: high-turnover by design
    KNOWN_FRITKOTS = ["maison antoine", "chez clementine", "la baraque à frites"]
    name_lower = name.lower() if name else ""
    is_fritkot = cuisine in ["Fast Food", "Belgian"] and (
        any(term in name_lower for term in ["frit", "fritkot", "frituur", "friterie", "friture"]) or
        any(known in name_lower for known in KNOWN_FRITKOTS)
    )

    # SMOOTH SATURATION CURVE using sigmoid blending
    # This eliminates hard cutoff "cliffs" in the scoring

    # Zone 1: Very few reviews (0-25) - penalty that smoothly decreases
    # Uses sigmoid centered at 15 reviews
    if review_count < 25:
        # Smooth transition from -0.30 at 0 reviews to ~0 at 25 reviews
        low_review_factor = 1 - sigmoid(review_count, center=15, steepness=0.2)
        return -0.30 * low_review_factor

    # Zone 2: Discovery zone (25-150) - small bonus, peaks around 75
    if review_count <= 150:
        # Bell curve bonus centered at 75 reviews
        discovery_bonus = 0.05 * math.exp(-((review_count - 75) ** 2) / (2 * 40 ** 2))
        return discovery_bonus

    # Zone 3: Sweet spot (150-600) - optimal range
    if review_count <= 600:
        # Gradual bonus that peaks at 300 and tapers
        sweet_spot_bonus = 0.05 * math.exp(-((review_count - 300) ** 2) / (2 * 150 ** 2))
        return sweet_spot_bonus

    # Zone 4: Famous local (600-1200) - transition to neutral
    if review_count <= 1200:
        # Smooth transition from small bonus to neutral
        transition_factor = sigmoid(review_count, center=900, steepness=0.005)
        return 0.02 * (1 - transition_factor)

    # Zone 5: High volume (1200+) - penalty zone with exceptions
    if is_fritkot:
        # Fritkots can handle high volume authentically
        return 0

    # Smooth penalty that increases with review count
    # Uses different steepness based on area type
    if tier in ["local_foodie", "diaspora_hub", "underexplored"]:
        # Gentler penalty in local areas (could be old institution)
        penalty = -0.03 * sigmoid(review_count, center=2000, steepness=0.001)
        return max(-0.10, penalty)
    else:
        # Steeper penalty in tourist/mixed areas
        penalty = -0.08 * sigmoid(review_count, center=1500, steepness=0.002)
        return max(-0.20, penalty)


def _calculate_diaspora_bonus(cuisine, commune, lat, lng, review_languages, name,
                               address, price_level, rating, tourist_trap_raw):
    """
    Calculate diaspora authenticity bonus with various filters.

    Combines: being on a diaspora food street + cuisine matching the area.
    Applies filters for tourist traps, hipster names, fine dining, low ratings.

    Returns: tuple (bonus_value, street_name)
    """
    diaspora_score, diaspora_street_name = diaspora_bonus_score(cuisine, commune, lat, lng, review_languages)

    # Filter: No diaspora bonus if in tourist trap
    if tourist_trap_raw > 0.3:
        return 0, None

    # Filter: Hipster/fusion names are not authentic diaspora
    hipster_keywords = ['eatery', 'kitchen', 'factory', 'lab', 'workshop', 'studio', 'house', 'corner', 'spot']
    if name and any(kw in name.lower() for kw in hipster_keywords):
        diaspora_score = diaspora_score * 0.3

    # Filter: Fine dining rarely represents authentic diaspora
    if price_level == 4:
        diaspora_score = diaspora_score * 0.2

    # Filter: Low rating
    if rating and rating < 3.5:
        return 0, None

    # Filter: Food halls, casinos, stations
    non_restaurant_locations = ['wolf', 'food market', 'food hall', 'casino', 'viage',
                                'hotel restaurant', 'station', 'gare', 'sncb', 'nmbs']
    if name and address:
        combined = (name + ' ' + str(address)).lower()
        if any(loc in combined for loc in non_restaurant_locations):
            return 0, None

    return 0.07 * diaspora_score, diaspora_street_name


def _calculate_value_bonus(price_level, rating):
    """
    Calculate value bonus for budget restaurants with high ratings.

    Based on validation: budget restaurants with high ratings are hidden gems.

    Returns: float bonus value (0 to 0.04)
    """
    if not price_level or not rating:
        return 0

    if price_level == 1 and rating >= 4.5:
        return 0.04
    elif price_level == 1 and rating >= 4.2:
        return 0.02
    elif price_level == 2 and rating >= 4.6:
        return 0.02
    elif price_level == 2 and rating >= 4.4:
        return 0.01
    return 0


def _calculate_price_quality_penalty(price_level, rating):
    """
    Calculate penalty for expensive restaurants with mediocre ratings.

    Returns: float penalty value (negative or 0)
    """
    if not price_level or not rating:
        return 0

    if price_level == 4:  # Very expensive
        expected_rating = 4.5
        if rating < expected_rating:
            return -0.10 * (expected_rating - rating)
    elif price_level == 3:  # Expensive
        expected_rating = 4.3
        if rating < expected_rating:
            return -0.06 * (expected_rating - rating)
    return 0


def _calculate_guide_bonus(name):
    """
    Calculate guide recognition bonus (Michelin, Bib Gourmand, Gault&Millau).

    Uses highest applicable bonus only - no double-counting.

    Returns: tuple (bonus_value, michelin_stars, is_bib, is_gaultmillau)
    """
    michelin_stars = has_michelin_recognition(name)
    is_bib_gourmand = has_bib_gourmand(name)
    is_gault_millau = has_gault_millau(name)

    if michelin_stars >= 2:
        bonus = 0.08
    elif michelin_stars == 1:
        bonus = 0.06
    elif is_bib_gourmand:
        bonus = 0.04
    elif is_gault_millau:
        bonus = 0.03
    else:
        bonus = 0

    return bonus, michelin_stars, is_bib_gourmand, is_gault_millau


def _calculate_low_review_penalty(review_count, rating):
    """
    Calculate penalty for statistically unreliable ratings using confidence weighting.

    Uses Bayesian-style confidence that accounts for:
    - Sample size (review count)
    - Rating extremity (perfect 5.0 or very high ratings are suspicious with few reviews)

    Returns: float penalty value (negative or 0)
    """
    if review_count >= 200:
        # Sufficient sample size - no penalty needed
        return 0

    # Calculate base confidence (0-1)
    conf = confidence_weight(review_count, min_reviews=10, half_confidence=50)

    # Calculate rating extremity factor
    # Perfect 5.0 is most suspicious, 4.8+ is also suspicious
    # Lower ratings are less suspicious (could be legitimately bad)
    if rating == 5.0:
        extremity = 1.0  # Maximum suspicion
    elif rating >= 4.8:
        extremity = 0.8
    elif rating >= 4.5:
        extremity = 0.5
    elif rating >= 4.0:
        extremity = 0.2
    else:
        extremity = 0.0  # Low ratings with few reviews - no penalty

    # Penalty scales with both low confidence AND rating extremity
    # Max penalty: -0.15 (for 5.0 rating with <10 reviews)
    # At 50 reviews with 5.0: ~-0.04
    # At 100 reviews with 5.0: ~-0.02
    uncertainty_penalty = -0.15 * (1 - conf) * extremity

    return uncertainty_penalty


def _determine_tier(total_score):
    """
    Determine restaurant quality tier based on score.

    Thresholds calibrated for confidence-weighted scoring:
    - Chef's Kiss: top ~5% (95th percentile = 0.55)
    - Kitchen Approved: top ~15% (85th percentile = 0.50)
    - Workable: top ~50% (50th percentile = 0.39)
    - Line Cook Shrug: bottom ~50%

    Returns: str tier name
    """
    if total_score >= 0.55:
        return "Chef's Kiss"
    elif total_score >= 0.48:
        return "Kitchen Approved"
    elif total_score >= 0.30:
        return "Workable"
    else:
        return "Line Cook Shrug"


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
    address = restaurant.get("address", "")
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
    # Uses POSITIVE_WEIGHTS constant (sums to exactly 1.0)
    # All bonuses are weighted by confidence to account for sample size

    # Calculate confidence weight based on review count
    conf = confidence_weight(review_count, min_reviews=10, half_confidence=50)

    # 0. Review count adjustment (saturation curve with smooth transitions)
    review_adjustment = _calculate_review_adjustment(review_count, cuisine, name, tier)

    # 1. Base quality - primary driver
    # Apply confidence weighting: low review count = rating less trusted
    # A 5.0★ with high confidence gets full weight; 5.0★ with low confidence gets less
    raw_quality = (rating / 5.0) if rating else 0
    base_quality = POSITIVE_WEIGHTS['base_quality'] * raw_quality * (0.5 + 0.5 * conf)

    # 2. ML residual - undervaluation detection
    # Residual typically ranges -0.5 to +0.5, we scale and clamp
    # Also weighted by confidence (residual is less meaningful with few reviews)
    raw_residual = min(1.0, max(-1.0, residual * 2))
    residual_score = POSITIVE_WEIGHTS['ml_residual'] * raw_residual * conf

    # 3. Tourist trap penalty (up to -15%)
    # NOTE: Removed collinearity with review_adjustment by focusing only on location/language signals
    # The review_adjustment handles the review count aspect
    tourist_trap_raw = tourist_trap_score(lat, lng, rating, review_count, review_languages) if lat and lng else 0
    # Scale down if review_adjustment already penalized (avoid double-penalty)
    collinearity_factor = 1.0 if review_adjustment >= 0 else 0.5
    tourist_penalty = PENALTY_CAPS['tourist_trap'] * tourist_trap_raw * collinearity_factor

    # 4. Diaspora bonus (7% weight) - unified street + cuisine/commune
    diaspora_bonus, diaspora_street_name = _calculate_diaspora_bonus(
        cuisine, commune, lat, lng, review_languages, name,
        address, price_level, rating, tourist_trap_raw
    )

    # 5. Independent restaurant bonus + Chain penalty
    # Using normalized weights from POSITIVE_WEIGHTS
    independent_bonus = POSITIVE_WEIGHTS['independent'] * (0 if is_chain else 1)
    chain_penalty = PENALTY_CAPS['chain'] if is_chain else 0

    # 6. Cuisine rarity bonus
    rarity_bonus = POSITIVE_WEIGHTS['cuisine_rarity'] * cuisine_rarity_score(cuisine, commune, cuisine_counts_by_commune)

    # 7. EU bubble penalty
    eu_penalty = PENALTY_CAPS['eu_bubble'] * eu_bubble_penalty(lat, lng, price_level, review_languages) if lat and lng else 0

    # 8. Price/quality mismatch penalty
    price_quality_penalty = _calculate_price_quality_penalty(price_level, rating)

    # 9. Value Score bonus (up to 4%)
    value_bonus = _calculate_value_bonus(price_level, rating)

    # 10. Scarcity score
    scarcity_total, scarcity_components = unified_scarcity_score(restaurant)
    scarcity_bonus = POSITIVE_WEIGHTS['scarcity'] * scarcity_total

    # Extract individual values for transparency/debugging
    closes_early = restaurant.get("closes_early", False)
    typical_close_hour = restaurant.get("typical_close_hour")
    weekdays_only = restaurant.get("weekdays_only", False)
    closed_weekends = restaurant.get("closed_weekends", False)
    closed_sunday = restaurant.get("closed_sunday", False)
    days_open_count = restaurant.get("days_open_count")

    # 11. Guide recognition bonus
    raw_guide_bonus, michelin_stars, is_bib_gourmand, is_gault_millau = _calculate_guide_bonus(name)
    guide_bonus = raw_guide_bonus  # Already returns weighted value

    # 12. Reddit community endorsement
    reddit_score, reddit_mentions = reddit_community_score(name, review_count)
    reddit_bonus = POSITIVE_WEIGHTS['reddit'] * reddit_score

    # 13. Low review count penalty (now uses confidence-based calculation)
    low_review_penalty = _calculate_low_review_penalty(review_count, rating)

    # 14. AFSCA Hygiene certification (informational only)
    address = restaurant.get("address", "")
    afsca_score = get_afsca_score(name, address)
    has_afsca_smiley = afsca_score > 0

    # 15. Family restaurant bonus
    is_family_name, family_pattern = is_family_restaurant_name(name)
    family_bonus = POSITIVE_WEIGHTS['family_name'] if (is_family_name and not is_chain) else 0

    # 16. Cuisine specificity bonus
    cuisine_specificity = get_cuisine_specificity_bonus(cuisine)
    specificity_bonus = POSITIVE_WEIGHTS['specificity'] * cuisine_specificity

    # 17. Non-restaurant shop penalty
    is_shop = is_non_restaurant_shop(name)
    shop_penalty = PENALTY_CAPS['shop'] if is_shop else 0

    # 18. Diaspora context (informational - for UI display only)
    diaspora_context = get_diaspora_context(cuisine, commune, lat, lng)

    # 19. Bruxellois authenticity bonus
    bruxellois_score = bruxellois_authenticity_score(name, commune)
    bruxellois_bonus = POSITIVE_WEIGHTS['bruxellois'] * bruxellois_score

    # Total score (sum of all components)
    total = (
        review_adjustment +
        base_quality +
        residual_score +
        tourist_penalty +
        diaspora_bonus +
        independent_bonus +
        chain_penalty +
        rarity_bonus +
        eu_penalty +
        price_quality_penalty +
        value_bonus +
        scarcity_bonus +
        guide_bonus +
        reddit_bonus +
        low_review_penalty +
        family_bonus +
        specificity_bonus +
        shop_penalty +
        bruxellois_bonus
    )

    # Clamp to [0, 1] for normalized output
    total = max(0.0, min(1.0, total))

    # Determine restaurant quality tier based on score
    restaurant_tier = _determine_tier(total)

    # Get authenticity markers from restaurant name
    auth_markers = get_authenticity_markers(name)

    # Return score and component breakdown
    return {
        "brussels_score": total,
        "commune": commune,
        "neighborhood": neighborhood,
        "diaspora_street": diaspora_street_name,  # Renamed from local_street
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
        # Authenticity markers (auto-detected from name)
        "has_diacritics": auth_markers["has_diacritics"],
        "has_flag_emoji": auth_markers["has_flag"],
        "diacritics_cuisine": auth_markers["diacritics_cuisine"],
        "flag_cuisine": auth_markers["flag_cuisine"],
        "components": {
            "review_adjustment": review_adjustment,  # Saturation curve
            "base_quality": base_quality,  # 35% weight
            "residual_score": residual_score,  # 20% weight
            "tourist_penalty": tourist_penalty,
            "diaspora_bonus": diaspora_bonus,  # 7% weight (unified)
            "independent_bonus": independent_bonus,  # 10% weight
            "rarity_bonus": rarity_bonus,  # 1% weight
            "eu_penalty": eu_penalty,
            "price_quality_penalty": price_quality_penalty,
            "value_bonus": value_bonus,  # Up to 4% for budget + high rating
            "scarcity_bonus": scarcity_bonus,  # 12% weight
            "guide_bonus": guide_bonus,  # Up to 8%
            "reddit_bonus": reddit_bonus,  # 5% weight
            "low_review_penalty": low_review_penalty,
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
    df["diaspora_street"] = [r["diaspora_street"] for r in results]
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

    # Add authenticity marker columns
    df["has_diacritics"] = [r["has_diacritics"] for r in results]
    df["has_flag_emoji"] = [r["has_flag_emoji"] for r in results]
    df["diacritics_cuisine"] = [r["diacritics_cuisine"] for r in results]
    df["flag_cuisine"] = [r["flag_cuisine"] for r in results]

    # Add component columns for debugging/transparency
    for component in ["review_adjustment", "tourist_penalty", "scarcity_bonus", "diaspora_bonus", "low_review_penalty"]:
        df[f"score_{component}"] = [r["components"][component] for r in results]

    # Add scarcity sub-components for detailed analysis
    for sub in ["review_scarcity", "hours_scarcity", "days_scarcity", "schedule_scarcity", "cuisine_scarcity"]:
        df[f"scarcity_{sub}"] = [r["scarcity_components"][sub] for r in results]

    # Add horseshoe bonus columns
    df["horseshoe_bonus"] = [r["scarcity_components"].get("horseshoe_bonus", 0) for r in results]
    df["horseshoe_type"] = [r["scarcity_components"].get("horseshoe_type") for r in results]

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

    # Filter out hotels and other non-food establishments
    # These are places where primary_type indicates non-food business
    NON_FOOD_TYPES = [
        "hotel", "motel", "hostel", "lodging",
        "sauna", "spa", "gym", "fitness_center", "beauty_salon",
        "hair_salon", "wellness_center", "massage", "public_bath",
        "furniture_store", "home_goods_store", "home_improvement_store",
        "clothing_store", "shopping_mall", "department_store",
        "movie_theater", "night_club", "casino"
    ]
    if "primary_type" in df.columns:
        non_food_mask = df["primary_type"].isin(NON_FOOD_TYPES)
        non_food_removed = df[non_food_mask]["name"].tolist()
        df = df[~non_food_mask]
        if non_food_removed:
            print(f"\nRemoved {len(non_food_removed)} non-food establishments (hotels, spas, etc.):")
            for name in non_food_removed[:10]:
                print(f"  - {name}")
            if len(non_food_removed) > 10:
                print(f"  ... and {len(non_food_removed) - 10} more")

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

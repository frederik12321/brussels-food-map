"""
City Configuration Template

Copy this file and fill in your city's data to create a new food map.

Steps:
1. Copy this file to config/your_city_config.py
2. Fill in all the TODO sections with your city's data
3. Run the data pipeline with your city's configuration
4. Deploy!

Example cities you might adapt this for:
- London, Paris, Berlin, Amsterdam, Barcelona
- New York, Los Angeles, Chicago, Toronto
- Tokyo, Seoul, Singapore, Hong Kong
- Melbourne, Sydney, Auckland
"""

from city_config_base import (
    CityConfig, District, LocalStreet, DiasporaHub,
    DEFAULT_CUISINE_SPECIFICITY, DEFAULT_CHAIN_PATTERNS
)


# TODO: Replace with your city name
YOUR_CITY_CONFIG = CityConfig(
    # === BASIC INFO ===
    city_name="Your City",  # TODO: e.g., "London", "Paris", "New York"
    country="Your Country",  # TODO: e.g., "UK", "France", "USA"
    center_lat=0.0,  # TODO: City center latitude
    center_lng=0.0,  # TODO: City center longitude
    default_zoom=13,

    # === TOURIST EPICENTER ===
    # The main tourist area where tourist trap penalties are strongest
    # Examples: Times Square (NYC), Eiffel Tower (Paris), Big Ben (London)
    tourist_epicenter=(0.0, 0.0),  # TODO: (lat, lng)
    tourist_epicenter_name="Main Square",  # TODO: e.g., "Times Square"

    # === DISTRICTS/NEIGHBORHOODS ===
    # Define your city's main areas
    # Tier options:
    #   - "tourist_heavy": Main tourist zones (penalty)
    #   - "tourist_trap": Extreme tourist traps (strong penalty)
    #   - "mixed": Average areas (neutral)
    #   - "local_foodie": Where locals eat (bonus)
    #   - "diaspora_hub": Immigrant communities (bonus for authentic diaspora food)
    #   - "underexplored": Hidden gem areas (bonus)
    #   - "eu_bubble" or similar: Expat bubbles (slight penalty)
    districts={
        # TODO: Add your city's districts
        # "District Name": District(lat=0.0, lng=0.0, tier="local_foodie"),
        # Example for London:
        # "Soho": District(lat=51.5137, lng=-0.1337, tier="mixed"),
        # "Brick Lane": District(lat=51.5215, lng=-0.0715, tier="diaspora_hub"),
        # "Leicester Square": District(lat=51.5103, lng=-0.1301, tier="tourist_heavy"),
    },

    # === SPECIAL NEIGHBORHOODS ===
    # More granular areas within districts
    neighborhoods={
        # TODO: Add special neighborhoods
        # "Chinatown": District(lat=0.0, lng=0.0, tier="diaspora_hub",
        #                       cuisine_affinity=["Chinese", "Vietnamese"]),
    },

    # === LOCAL FOOD STREETS ===
    # Streets known for good local food (not on tourist maps)
    local_streets=[
        # TODO: Add local food streets
        # LocalStreet("Street Name", lat, lng, radius_km),
    ],

    # === LOCAL CUISINES ===
    # What's the local cuisine that deserves a bonus?
    local_cuisines=["Local"],  # TODO: e.g., ["British", "Pub Food"] for London
    local_cuisine_bonus=0.03,

    # === CHAIN PATTERNS ===
    # Regex patterns for chain restaurants to penalize
    chain_patterns=DEFAULT_CHAIN_PATTERNS + [
        # TODO: Add local chains
        # r"local chain name",
    ],

    # === NON-RESTAURANT EXCLUSIONS ===
    # Shops that shouldn't appear in restaurant rankings
    non_restaurant_patterns=[
        # TODO: Add patterns for non-restaurants
        # r"\bchocolate shop\b",
        # r"\bbakery\b",  # if you want to exclude bakeries
    ],

    # === MICHELIN STARRED RESTAURANTS ===
    # Current Michelin Guide stars for your city
    michelin_stars={
        # TODO: Add Michelin-starred restaurants
        # "restaurant name": 1,  # or 2, or 3
    },

    # === BIB GOURMAND ===
    # Michelin Bib Gourmand restaurants (good value)
    bib_gourmand=[
        # TODO: Add Bib Gourmand restaurants
    ],

    # === LOCAL FOOD GUIDES ===
    # Other local food guides/awards
    local_guides={
        # TODO: Add local guides
        # "guide_name": ["restaurant1", "restaurant2"],
        # Examples:
        # "timeout_top_100": [...],  # TimeOut 100 Best Restaurants
        # "eater_38": [...],  # Eater's Essential Restaurants
        # "local_newspaper": [...],
    },

    # === REDDIT/COMMUNITY ===
    # Subreddit for community endorsements
    reddit_subreddit=None,  # TODO: e.g., "london" for r/london

    # === TIMEZONE ===
    timezone="UTC",  # TODO: e.g., "Europe/London", "America/New_York"

    # === CUISINE SPECIFICITY ===
    # Use defaults, or add city-specific regional cuisines
    cuisine_specificity=DEFAULT_CUISINE_SPECIFICITY,
)


# === DIASPORA AUTHENTICITY (OPTIONAL) ===
# Map cuisines to their authentic diaspora hubs in your city
# This helps identify authentic ethnic restaurants
DIASPORA_HUBS = {
    # TODO: Fill in for your city
    # "Indian": [
    #     DiasporaHub("Brick Lane", "Tower Hamlets", 51.5215, -0.0715, ["Bangladeshi", "Indian"]),
    # ],
    # "Chinese": [
    #     DiasporaHub("Chinatown", "Westminster", 51.5115, -0.1317, ["Chinese", "Cantonese"]),
    # ],
}

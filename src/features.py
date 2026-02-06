"""
Feature Engineering for Brussels Restaurant Data

This module transforms raw restaurant data into ML-ready features,
including log-transformed review counts, cuisine encoding, chain detection,
and spatial grid features.
"""

import json
import re
import pandas as pd
import numpy as np
import h3

from brussels_context import is_within_brussels

# Common chain restaurant patterns in Belgium/Brussels
CHAIN_PATTERNS = [
    r"mcdonald", r"burger king", r"quick", r"kfc", r"subway", r"domino",
    r"pizza hut", r"starbucks", r"panos", r"exki", r"le pain quotidien",
    r"paul", r"class'croute", r"pizza express", r"vapiano", r"wagamama",
    r"nando", r"five guys", r"pitaya", r"wok", r"sushi shop", r"planet sushi",
    r"bavet", r"balls & glory", r"ellis", r"fred & ginger", r"la brasserie",
    r"otomat", r"manhattn", r"il fiore", r"delitraiteur"
]

# Non-restaurant entries to exclude (supermarkets, grocery stores, hotels)
EXCLUDE_PATTERNS = [
    r"carrefour", r"delhaize", r"colruyt", r"aldi\b", r"lidl", r"proxy",
    r"\bhotel\b", r"\bhôtel\b", r"thermen", r"wellness"
]

# Primary types to exclude (non-food establishments)
EXCLUDE_TYPES = [
    "supermarket", "grocery_store", "convenience_store",
    # Hotels and lodging
    "hotel", "motel", "hostel", "lodging",
    # Wellness and fitness
    "sauna", "spa", "gym", "fitness_center", "beauty_salon",
    "hair_salon", "wellness_center", "massage", "public_bath",
    # Retail stores
    "furniture_store", "home_goods_store", "home_improvement_store",
    "clothing_store", "shopping_mall", "department_store",
    # Other non-food
    "movie_theater", "night_club", "casino"
]


def load_data(filepath="../data/brussels_restaurants.json"):
    """Load restaurant data from JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return pd.DataFrame(data)


def detect_chain(name):
    """Detect if a restaurant is likely a chain based on name."""
    if not name:
        return False
    name_lower = name.lower()
    for pattern in CHAIN_PATTERNS:
        if re.search(pattern, name_lower):
            return True
    return False


def should_exclude(row):
    """Check if a place should be excluded (non-food establishments, outside Brussels, etc.)."""
    name = row.get("name", "") or ""
    primary_type = row.get("primary_type", "") or ""
    lat = row.get("lat")
    lng = row.get("lng")

    # Check if location is outside Brussels Capital Region
    if lat is not None and lng is not None:
        if not is_within_brussels(lat, lng):
            return True

    # Check name patterns
    name_lower = name.lower()
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, name_lower):
            return True

    # Check primary type
    if primary_type in EXCLUDE_TYPES:
        return True

    return False


def extract_cuisine(types, primary_type, name=None):
    """Extract cuisine category from place types and name patterns."""
    # Priority mapping for cuisine detection
    cuisine_map = {
        "italian_restaurant": "Italian",
        "pizza_restaurant": "Italian",
        "french_restaurant": "French",
        "belgian_restaurant": "Belgian",
        "japanese_restaurant": "Japanese",
        "sushi_restaurant": "Japanese",
        "chinese_restaurant": "Chinese",
        "thai_restaurant": "Thai",
        "vietnamese_restaurant": "Vietnamese",
        "indian_restaurant": "Indian",
        "mexican_restaurant": "Mexican",
        "greek_restaurant": "Greek",
        "turkish_restaurant": "Turkish",
        "lebanese_restaurant": "Lebanese",
        "middle_eastern_restaurant": "Middle Eastern",
        "mediterranean_restaurant": "Mediterranean",
        "seafood_restaurant": "Seafood",
        "steak_house": "Steakhouse",
        "vegetarian_restaurant": "Vegetarian",
        "vegan_restaurant": "Vegan",
        "fast_food_restaurant": "Fast Food",
        "hamburger_restaurant": "Burger",
        "american_restaurant": "American",
        "korean_restaurant": "Korean",
        "spanish_restaurant": "Spanish",
        "asian_restaurant": "Asian",
        "african_restaurant": "African",
        "brazilian_restaurant": "Brazilian",
        "cafe": "Cafe",
        "coffee_shop": "Cafe",
        "bakery": "Bakery",
        "bar": "Bar",
        "brunch_restaurant": "Brunch",
        "breakfast_restaurant": "Breakfast",
    }

    # Priority name-based detection: Override Google's incorrect classifications
    # Poke restaurants are Hawaiian, not American (Google often misclassifies these)
    if name:
        name_lower = name.lower()
        poke_patterns = ["poké", "poke bowl", "poke bar", "poke house", "hawaiian poke", "açaí bowl", "acai bowl", "pokebowl", "mypoke", "pokevie"]
        for pattern in poke_patterns:
            if pattern in name_lower:
                return "Hawaiian"
        # Also check for just "poke" but only if it's a word boundary (catches "Kameha Poke", "Poke & More")
        if " poke " in f" {name_lower} " or name_lower.startswith("poke ") or name_lower.endswith(" poke") or " poke" in name_lower:
            return "Hawaiian"

    # Check primary type first
    if primary_type and primary_type in cuisine_map:
        return cuisine_map[primary_type]

    # Check all types
    if types and isinstance(types, list):
        for t in types:
            if t in cuisine_map:
                return cuisine_map[t]

    # Name-based cuisine detection for cuisines Google doesn't classify well
    # This catches many cuisines that get classified as generic "restaurant"
    if name:
        name_lower = name.lower()

        # French patterns (check before Belgian due to "brasserie" overlap)
        french_patterns = ["bistro", "brasserie", "french", "paris", "lyon", "provenc"]
        for pattern in french_patterns:
            if pattern in name_lower:
                return "French"

        # Belgian patterns
        belgian_patterns = ["belg", "frites", "gaufre", "waffle", "moules", "stoemp", "carbonade", "waterzooi"]
        for pattern in belgian_patterns:
            if pattern in name_lower:
                return "Belgian"

        # Moroccan patterns
        moroccan_patterns = ["bab ", "dar ", "riad", "marrakech", "casablanca", "fes ", "tajine", "tagine", "couscous", "maroc"]
        for pattern in moroccan_patterns:
            if pattern in name_lower:
                return "Moroccan"

        # Congolese patterns (important for Brussels/Matongé)
        congolese_patterns = ["congo", "kinshasa", "maman ", "mamie ", "chez maman", "pondu", "fufu"]
        for pattern in congolese_patterns:
            if pattern in name_lower:
                return "Congolese"

        # Ethiopian patterns
        ethiopian_patterns = ["ethiopia", "eritrea", "injera", "addis"]
        for pattern in ethiopian_patterns:
            if pattern in name_lower:
                return "Ethiopian"

        # Syrian patterns
        syrian_patterns = ["syria", "damas", "alep", "شام"]
        for pattern in syrian_patterns:
            if pattern in name_lower:
                return "Syrian"

        # Portuguese patterns
        portuguese_patterns = ["portugal", "portugalia", "churrasqueira", "pastel de nata", "bacalhau", "lisbon", "lisboa", "lisbonne"]
        for pattern in portuguese_patterns:
            if pattern in name_lower:
                return "Portuguese"

        # Spanish patterns
        spanish_patterns = ["tapas", "espanol", "española", "bodega", "iberic", "paella"]
        for pattern in spanish_patterns:
            if pattern in name_lower:
                return "Spanish"

        # Peruvian patterns
        peruvian_patterns = ["peru", "ceviche", "machu picchu", "inca", "lomo saltado", "pisco"]
        for pattern in peruvian_patterns:
            if pattern in name_lower:
                return "Peruvian"

        # Brazilian patterns
        brazilian_patterns = ["brasil", "brazil", "churrasco", "rodizio", "feijoada"]
        for pattern in brazilian_patterns:
            if pattern in name_lower:
                return "Brazilian"

        # Mexican patterns
        mexican_patterns = ["mexic", "taco", "burrito", "guacamole", "nacho", "enchilada"]
        for pattern in mexican_patterns:
            if pattern in name_lower:
                return "Mexican"

        # Venezuelan patterns
        venezuelan_patterns = ["arepa", "venezuela", "pabellon"]
        for pattern in venezuelan_patterns:
            if pattern in name_lower:
                return "Venezuelan"

        # Sushi/Japanese (catch remaining)
        sushi_patterns = ["sushi", "maki", "ramen", "udon", "tempura", "izakaya"]
        for pattern in sushi_patterns:
            if pattern in name_lower:
                return "Japanese"

        # Korean patterns
        korean_patterns = ["korea", "korean", "bibimbap", "kimchi", "seoul", "bulgogi"]
        for pattern in korean_patterns:
            if pattern in name_lower:
                return "Korean"

        # African patterns (West/Central Africa)
        african_patterns = ["dakar", "senegal", "cameroun", "cameroon", "nigeria", "ghana", "mali ", "burkina", "togo ", "benin", "afric"]
        for pattern in african_patterns:
            if pattern in name_lower:
                return "African"

        # Seafood patterns
        seafood_patterns = ["seafood", "fish", "poisson", "fruits de mer", "crab", "lobster", "homard", "pêcherie", "oyster", "huitre"]
        for pattern in seafood_patterns:
            if pattern in name_lower:
                return "Seafood"

        # Steakhouse/Grill patterns
        steak_patterns = ["steak", "grill", "bbq", "barbecue", "butcher", "viande", "meat", "angus", "wagyu"]
        for pattern in steak_patterns:
            if pattern in name_lower:
                return "Steakhouse"

        # Israeli/Middle Eastern patterns
        israeli_patterns = ["falafel", "hummus", "shawarma", "kosher"]
        for pattern in israeli_patterns:
            if pattern in name_lower:
                return "Middle Eastern"

        # Afghan patterns
        afghan_patterns = ["afghan", "kabul", "kabob"]
        for pattern in afghan_patterns:
            if pattern in name_lower:
                return "Afghan"

        # Nepali/Tibetan patterns
        nepali_patterns = ["nepal", "tibet", "himalaya", "momo", "kathmandu"]
        for pattern in nepali_patterns:
            if pattern in name_lower:
                return "Nepali"

        # Armenian patterns
        armenian_patterns = ["armenia", "yerevan"]
        for pattern in armenian_patterns:
            if pattern in name_lower:
                return "Armenian"

        # Georgian patterns
        georgian_patterns = ["georgia", "khachapuri", "tbilisi"]
        for pattern in georgian_patterns:
            if pattern in name_lower:
                return "Georgian"

        # Russian/Eastern European patterns
        russian_patterns = ["russia", "ukraine", "poland", "polski", "pierogi", "borscht", "pelmeni", "kartchma"]
        for pattern in russian_patterns:
            if pattern in name_lower:
                return "Eastern European"

        # Caribbean patterns
        caribbean_patterns = ["caribbean", "jamaican", "haiti", "cuba", "dominican", "antilles"]
        for pattern in caribbean_patterns:
            if pattern in name_lower:
                return "Caribbean"

        # Italian patterns (pizza, pasta, osteria) - very specific, safe to match
        italian_patterns = ["pizza", "pizzeria", "pasta", "osteria", "trattoria", "risotto", "lasagna", "italiano", "italiana"]
        for pattern in italian_patterns:
            if pattern in name_lower:
                return "Italian"

        # Burger patterns
        burger_patterns = ["burger"]
        for pattern in burger_patterns:
            if pattern in name_lower:
                return "Burger"

        # Poke/Hawaiian patterns - specific terms only
        poke_patterns = ["poké", "poke bowl", "hawaiian poke", "açaí", "acai"]
        for pattern in poke_patterns:
            if pattern in name_lower:
                return "Hawaiian"

        # Turkish patterns (kebab variants)
        turkish_extra_patterns = ["kebab", "kebap", "döner", "doner", "lahmacun", "pide"]
        for pattern in turkish_extra_patterns:
            if pattern in name_lower:
                return "Turkish"

        # Indian patterns (tandoori, curry)
        indian_patterns = ["tandoori", "masala", "biryani", "tikka", "punjab", "delhi", "mumbai"]
        for pattern in indian_patterns:
            if pattern in name_lower:
                return "Indian"

        # Thai patterns
        thai_patterns = ["thai", "thaï", "bangkok", "pad thai", "tom yum"]
        for pattern in thai_patterns:
            if pattern in name_lower:
                return "Thai"

        # Vietnamese patterns - careful with "pho"
        vietnamese_patterns = ["vietnam", "vietnamese", "banh mi", "saigon", "hanoi", " pho ", "pho "]
        for pattern in vietnamese_patterns:
            if pattern in name_lower:
                return "Vietnamese"

        # Chinese patterns
        chinese_patterns = ["chinese", "chinois", "dim sum", "dumpling", "peking", "szechuan", "cantonese"]
        for pattern in chinese_patterns:
            if pattern in name_lower:
                return "Chinese"

        # Asian generic patterns - after specific Asian cuisines
        asian_patterns = ["wok ", " wok", "asian", "asiatique"]
        for pattern in asian_patterns:
            if pattern in name_lower:
                return "Asian"

        # Belgian patterns (taverne, frituur, snack frite)
        belgian_extra_patterns = ["taverne", "frituur", "friterie", "fritkot", "estaminet", "snack frit"]
        for pattern in belgian_extra_patterns:
            if pattern in name_lower:
                return "Belgian"

        # Brunch/Breakfast patterns
        brunch_patterns = ["brunch", "breakfast", "pancake", "ontbijt"]
        for pattern in brunch_patterns:
            if pattern in name_lower:
                return "Brunch"

        # Salad/Healthy patterns - specific terms
        healthy_patterns = ["salad bar", "saladbar", "salade bar"]
        for pattern in healthy_patterns:
            if pattern in name_lower:
                return "Vegetarian"

        # Greek patterns
        greek_patterns = ["greek", "grec", "gyros", "souvlaki", "tzatziki", "zorba"]
        for pattern in greek_patterns:
            if pattern in name_lower:
                return "Greek"

        # Lebanese/Middle Eastern extra
        lebanese_patterns = ["liban", "lebanese", "libanais", "mezze", "fattoush", "tabouleh", "manouche"]
        for pattern in lebanese_patterns:
            if pattern in name_lower:
                return "Lebanese"

    return "Other"


def extract_venue_type(types, primary_type, name=None):
    """Extract venue type (restaurant, cafe, bar, etc.)."""
    # Check for specific sub-types first (before generic "restaurant")
    if primary_type:
        # Sandwich shops - separate category
        if primary_type == "sandwich_shop":
            return "Sandwich_shop"
        # Fast food - separate category
        if primary_type == "fast_food_restaurant":
            return "Fast_food"

    # Then check general venue types
    venue_priority = ["restaurant", "cafe", "bar", "bakery", "meal_takeaway"]

    if primary_type and isinstance(primary_type, str):
        for v in venue_priority:
            if v in primary_type:
                return v.capitalize()

    if types and isinstance(types, list):
        for v in venue_priority:
            if v in types:
                return v.capitalize()

    # Check name for café/bar indicators (unless it says "restaurant" too)
    if name and isinstance(name, str):
        name_lower = name.lower()
        # If name contains café or bar but NOT restaurant, classify as Bar
        has_bar_indicator = any(word in name_lower for word in ["café", "cafe", " bar ", " bar,", "bar ", "(bar)", "le bar", "the bar"])
        has_restaurant = "restaurant" in name_lower or "resto" in name_lower
        if has_bar_indicator and not has_restaurant:
            return "Bar"

    return "Restaurant"


def parse_price_level(price_level):
    """Convert price level string to numeric."""
    price_map = {
        "PRICE_LEVEL_FREE": 0,
        "PRICE_LEVEL_INEXPENSIVE": 1,
        "PRICE_LEVEL_MODERATE": 2,
        "PRICE_LEVEL_EXPENSIVE": 3,
        "PRICE_LEVEL_VERY_EXPENSIVE": 4
    }
    return price_map.get(price_level, 2)  # Default to moderate


def parse_closing_times(closing_times):
    """
    Parse closing times dict and determine if restaurant closes early.

    Returns tuple: (closes_early, typical_closing_hour)
    closes_early: True if closes before 22:00 on weekdays (Mon-Fri)
    """
    if not closing_times or not isinstance(closing_times, dict):
        return False, None

    weekday_close_hours = []

    # Days 1-5 are Monday-Friday
    for day in [1, 2, 3, 4, 5]:
        day_str = str(day)
        if day_str in closing_times:
            time_str = closing_times[day_str]
            try:
                hour = int(time_str.split(":")[0])
                weekday_close_hours.append(hour)
            except (ValueError, IndexError):
                pass
        elif day in closing_times:
            time_str = closing_times[day]
            try:
                hour = int(time_str.split(":")[0])
                weekday_close_hours.append(hour)
            except (ValueError, IndexError):
                pass

    if not weekday_close_hours:
        return False, None

    # Calculate typical closing hour (median)
    typical_close = sorted(weekday_close_hours)[len(weekday_close_hours) // 2]

    # "Closes early" if typically closes before 22:00 (10 PM)
    # Restaurants closing early often = popular lunch spots or local favorites
    closes_early = typical_close < 22 and typical_close > 12  # Not breakfast-only places

    return closes_early, typical_close


def parse_days_open(days_open):
    """
    Parse days_open list and extract schedule characteristics.

    Returns dict with:
    - days_open_count: number of days open per week
    - closed_weekends: True if closed on both Saturday and Sunday
    - closed_sunday: True if closed on Sunday only
    - weekdays_only: True if only open Mon-Fri
    """
    if not days_open or not isinstance(days_open, list):
        return {
            "days_open_count": None,
            "closed_weekends": False,
            "closed_sunday": False,
            "weekdays_only": False
        }

    # Days: 0=Sunday, 1=Monday, ..., 6=Saturday
    days_set = set(days_open)
    days_count = len(days_set)

    # Check weekend status
    has_saturday = 6 in days_set
    has_sunday = 0 in days_set

    closed_weekends = not has_saturday and not has_sunday
    closed_sunday = not has_sunday and has_saturday

    # Weekdays only = open Mon-Fri, closed Sat-Sun
    weekdays = {1, 2, 3, 4, 5}
    weekdays_only = days_set == weekdays or (days_set.issubset(weekdays) and closed_weekends)

    return {
        "days_open_count": days_count,
        "closed_weekends": closed_weekends,
        "closed_sunday": closed_sunday,
        "weekdays_only": weekdays_only
    }


def add_h3_features(df, resolution=8):
    """Add H3 hexagonal grid features for spatial analysis."""
    # Drop existing hex columns if they exist (avoid _x/_y suffixes on re-runs)
    hex_cols = [c for c in df.columns if c.startswith("hex_")]
    if hex_cols:
        df = df.drop(columns=hex_cols)

    df["h3_index"] = df.apply(
        lambda row: h3.latlng_to_cell(row["lat"], row["lng"], resolution)
        if pd.notna(row["lat"]) and pd.notna(row["lng"]) else None,
        axis=1
    )

    # Count restaurants per hexagon
    hex_counts = df.groupby("h3_index").size().reset_index(name="hex_restaurant_count")
    df = df.merge(hex_counts, on="h3_index", how="left")

    # Mean rating per hexagon
    hex_ratings = df.groupby("h3_index")["rating"].mean().reset_index(name="hex_mean_rating")
    df = df.merge(hex_ratings, on="h3_index", how="left")

    return df


def engineer_features(df):
    """Main feature engineering pipeline."""
    # Basic cleaning
    df = df.dropna(subset=["lat", "lng"])
    df = df[df["rating"].notna()]

    # Exclude non-restaurant entries (supermarkets, grocery stores)
    excluded_mask = df.apply(should_exclude, axis=1)
    excluded_count = excluded_mask.sum()
    if excluded_count > 0:
        print(f"Excluding {excluded_count} non-restaurant entries (supermarkets, etc.)")
        df = df[~excluded_mask]

    # Log-transform review counts (with +1 to handle zeros)
    df["log_review_count"] = np.log1p(df["review_count"].fillna(0))

    # Chain detection
    df["is_chain"] = df["name"].apply(detect_chain)

    # Cuisine extraction (with name-based fallback for cuisines Google doesn't classify)
    df["cuisine"] = df.apply(
        lambda row: extract_cuisine(row.get("types", []), row.get("primary_type"), row.get("name")),
        axis=1
    )

    # Venue type (now also checks name for café/bar indicators)
    df["venue_type"] = df.apply(
        lambda row: extract_venue_type(row.get("types", []), row.get("primary_type"), row.get("name")),
        axis=1
    )

    # Price level (numeric)
    df["price_numeric"] = df["price_level"].apply(parse_price_level)

    # Opening hours - extract "closes early" signal
    if "closing_times" in df.columns:
        closing_info = df["closing_times"].apply(parse_closing_times)
        df["closes_early"] = closing_info.apply(lambda x: x[0] if x else False)
        df["typical_close_hour"] = closing_info.apply(lambda x: x[1] if x else None)
        print(f"  Closes early: {df['closes_early'].sum()} restaurants")
    else:
        df["closes_early"] = False
        df["typical_close_hour"] = None

    # Days open - extract schedule characteristics
    if "days_open" in df.columns:
        days_info = df["days_open"].apply(parse_days_open)
        df["days_open_count"] = days_info.apply(lambda x: x["days_open_count"] if x else None)
        df["closed_weekends"] = days_info.apply(lambda x: x["closed_weekends"] if x else False)
        df["closed_sunday"] = days_info.apply(lambda x: x["closed_sunday"] if x else False)
        df["weekdays_only"] = days_info.apply(lambda x: x["weekdays_only"] if x else False)
        print(f"  Closed weekends: {df['closed_weekends'].sum()} restaurants")
        print(f"  Weekdays only: {df['weekdays_only'].sum()} restaurants")
    else:
        df["days_open_count"] = None
        df["closed_weekends"] = False
        df["closed_sunday"] = False
        df["weekdays_only"] = False

    # H3 spatial features
    df = add_h3_features(df)

    # Cuisine diversity in hexagon (entropy-based)
    def cuisine_entropy(group):
        counts = group.value_counts(normalize=True)
        return -np.sum(counts * np.log(counts + 1e-10))

    hex_entropy = df.groupby("h3_index")["cuisine"].apply(cuisine_entropy).reset_index(
        name="hex_cuisine_entropy"
    )
    df = df.merge(hex_entropy, on="h3_index", how="left")

    # Chain share per hexagon
    hex_chain = df.groupby("h3_index")["is_chain"].mean().reset_index(
        name="hex_chain_share"
    )
    df = df.merge(hex_chain, on="h3_index", how="left")

    return df


def prepare_ml_features(df):
    """Prepare features for ML model."""
    # One-hot encode cuisine
    cuisine_dummies = pd.get_dummies(df["cuisine"], prefix="cuisine")

    # One-hot encode venue type
    venue_dummies = pd.get_dummies(df["venue_type"], prefix="venue")

    # Select numeric features
    numeric_features = [
        "log_review_count",
        "price_numeric",
        "is_chain",
        "hex_restaurant_count",
        "hex_mean_rating",
        "hex_cuisine_entropy",
        "hex_chain_share"
    ]

    # Combine all features
    X = pd.concat([
        df[numeric_features].fillna(0),
        cuisine_dummies,
        venue_dummies
    ], axis=1)

    # Convert boolean to int
    X["is_chain"] = X["is_chain"].astype(int)

    y = df["rating"]

    return X, y


def save_processed_data(df, output_file="../data/brussels_restaurants_processed.csv"):
    """Save processed data to CSV."""
    df.to_csv(output_file, index=False)
    print(f"Saved processed data to {output_file}")


if __name__ == "__main__":
    print("Loading data...")
    df = load_data()
    print(f"Loaded {len(df)} restaurants")

    print("Engineering features...")
    df = engineer_features(df)
    print(f"After cleaning: {len(df)} restaurants")

    print("\nFeature summary:")
    print(f"  Cuisines: {df['cuisine'].nunique()} types")
    print(f"  Chains: {df['is_chain'].sum()} ({df['is_chain'].mean()*100:.1f}%)")
    print(f"  H3 hexagons: {df['h3_index'].nunique()} cells")

    save_processed_data(df)

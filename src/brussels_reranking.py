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
import pandas as pd
import numpy as np
from collections import Counter

from brussels_context import (
    COMMUNES, NEIGHBORHOODS, TIER_WEIGHTS,
    DIASPORA_AUTHENTICITY, BELGIAN_AUTHENTICITY,
    get_commune, get_neighborhood,
    distance_to_grand_place, distance_to_eu_quarter,
    haversine_distance, is_on_local_street,
    has_michelin_recognition, has_gault_millau, has_bib_gourmand
)


def tourist_trap_score(lat, lng, review_languages=None):
    """
    Calculate tourist trap score (0-1).
    Higher = more likely tourist trap.

    Based on:
    - Distance to Grand Place (closer = worse)
    - Neighborhood tier
    - Review language distribution (if available)
    """
    # Distance component (exponential decay from Grand Place)
    dist_gp = distance_to_grand_place(lat, lng)
    distance_score = math.exp(-dist_gp / 0.25)  # 0.25km decay constant (tighter radius)

    # Check if in known tourist trap neighborhood
    neighborhood, neighborhood_data = get_neighborhood(lat, lng)
    neighborhood_score = 0
    if neighborhood_data and neighborhood_data.get("tier") == "tourist_trap":
        neighborhood_score = 0.5

    # Rue des Bouchers specific (notorious tourist trap)
    if neighborhood == "Rue des Bouchers":
        neighborhood_score = 0.8

    # Language distribution (if we have it)
    language_score = 0
    if review_languages:
        # High proportion of English-only reviews = tourist indicator
        total = sum(review_languages.values())
        if total > 0:
            english_pct = review_languages.get("en", 0) / total
            # Penalty if >60% English reviews
            if english_pct > 0.6:
                language_score = (english_pct - 0.6) * 2

    # Combine scores
    score = 0.5 * distance_score + 0.3 * neighborhood_score + 0.2 * language_score
    return min(1.0, score)


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

    # === SCORING COMPONENTS ===

    # 0. Review count penalty (both too few AND too many reviews are problematic)
    # Too few reviews = unreliable rating
    # Too many reviews = likely tourist trap or overhyped
    if review_count < 15:
        review_penalty = -0.30 * (1 - review_count / 15)  # Up to -0.30 penalty
    elif review_count < 35:
        review_penalty = -0.12 * (1 - (review_count - 15) / 20)  # Up to -0.12 penalty
    elif review_count > 3000:
        # Super popular = likely tourist trap (e.g., Delirium with 25k reviews)
        review_penalty = -0.15 * min(1.0, (review_count - 3000) / 10000)
    elif review_count > 1500:
        # Very popular = mild penalty
        review_penalty = -0.08 * ((review_count - 1500) / 1500)
    else:
        review_penalty = 0  # Sweet spot: 35-1500 reviews

    # 1. Base quality (normalized rating 0-1) - primary driver
    base_quality = 0.30 * (rating / 5.0) if rating else 0

    # 2. ML residual (undervalued bonus) - secondary driver
    residual_score = 0.25 * min(1.0, max(-1.0, residual * 2))

    # 3. Tourist trap penalty
    tourist_penalty = -0.15 * tourist_trap_score(lat, lng, review_languages) if lat and lng else 0

    # 4. Diaspora authenticity bonus - DISABLED (Brussels is too international for this to be meaningful)
    diaspora_bonus = 0

    # 5. Commune visibility boost (small - just a tiebreaker)
    commune_boost = 0.03 * commune_visibility_boost(commune, commune_review_totals)

    # 6. Independent restaurant bonus
    independent_bonus = 0.10 * (0 if is_chain else 1)

    # 7. Cold-start correction (minimal - don't boost unproven places)
    cold_start = 0.02 * cold_start_correction(review_count, rating, commune)

    # 8. Cuisine rarity reward (minimal - rare cuisine doesn't mean good food)
    rarity_bonus = 0.005 * cuisine_rarity_score(cuisine, commune, cuisine_counts_by_commune)

    # 9. EU bubble penalty
    eu_penalty = -0.03 * eu_bubble_penalty(lat, lng, price_level, review_languages) if lat and lng else 0

    # 10. Price/quality mismatch penalty
    # Expensive restaurants should have higher ratings to justify the price
    # €€€ (price_level=3) should have rating >= 4.3
    # €€€€ (price_level=4) should have rating >= 4.5
    price_quality_penalty = 0
    if price_level and rating:
        if price_level == 4:  # Very expensive
            expected_rating = 4.5
            if rating < expected_rating:
                price_quality_penalty = -0.12 * (expected_rating - rating)
        elif price_level == 3:  # Expensive
            expected_rating = 4.3
            if rating < expected_rating:
                price_quality_penalty = -0.08 * (expected_rating - rating)

    # 11. Local street bonus (known locally, not on tourist maps)
    local_street_bonus = 0
    local_street_name = None
    if lat and lng:
        is_local, street_name = is_on_local_street(lat, lng)
        if is_local:
            local_street_bonus = 0.06
            local_street_name = street_name

    # 12. UNIFIED SCARCITY SCORE
    # Combines: review count scarcity, hours, days, schedule, rare cuisine
    # Scarcity = hard to access = likely a local gem
    scarcity_total, scarcity_components = unified_scarcity_score(restaurant)
    scarcity_bonus = 0.15 * scarcity_total  # Up to 0.15 total from all scarcity signals

    # Extract individual values for transparency/debugging
    closes_early = restaurant.get("closes_early", False)
    typical_close_hour = restaurant.get("typical_close_hour")
    weekdays_only = restaurant.get("weekdays_only", False)
    closed_weekends = restaurant.get("closed_weekends", False)
    closed_sunday = restaurant.get("closed_sunday", False)

    days_open_count = restaurant.get("days_open_count")

    # 13. Tier-based adjustment (minimal - just a hint)
    tier_adjustment = TIER_WEIGHTS.get(tier, 0) * 0.02

    # 14. Guide recognition bonus (Michelin, Bib Gourmand & Gault Millau)
    guide_bonus = 0
    michelin_stars = has_michelin_recognition(name)
    is_bib_gourmand = has_bib_gourmand(name)
    is_gault_millau = has_gault_millau(name)

    if michelin_stars >= 2:
        guide_bonus = 0.12  # 2+ stars: strong boost
    elif michelin_stars == 1:
        guide_bonus = 0.08  # 1 star: moderate boost
    elif is_bib_gourmand:
        guide_bonus = 0.06  # Bib Gourmand: good value recognition
    elif is_gault_millau:
        guide_bonus = 0.05  # Gault Millau only: small boost

    # Total score
    total = (
        review_penalty +
        base_quality +
        residual_score +
        tourist_penalty +
        diaspora_bonus +
        commune_boost +
        independent_bonus +
        cold_start +
        rarity_bonus +
        eu_penalty +
        price_quality_penalty +
        local_street_bonus +
        scarcity_bonus +
        tier_adjustment +
        guide_bonus
    )

    # Return score and component breakdown
    return {
        "brussels_score": total,
        "commune": commune,
        "neighborhood": neighborhood,
        "local_street": local_street_name,
        "tier": tier,
        "closes_early": closes_early,
        "typical_close_hour": typical_close_hour,
        "weekdays_only": weekdays_only,
        "closed_sunday": closed_sunday,
        "days_open_count": days_open_count,
        "is_rare_cuisine": RARE_CUISINES_BRUSSELS.get(cuisine, 0) > 0,
        "michelin_stars": michelin_stars,
        "bib_gourmand": is_bib_gourmand,
        "gault_millau": is_gault_millau,
        "scarcity_components": scarcity_components,  # Detailed breakdown
        "components": {
            "review_penalty": review_penalty,
            "base_quality": base_quality,
            "residual_score": residual_score,
            "tourist_penalty": tourist_penalty,
            "diaspora_bonus": diaspora_bonus,
            "commune_boost": commune_boost,
            "independent_bonus": independent_bonus,
            "cold_start": cold_start,
            "rarity_bonus": rarity_bonus,
            "eu_penalty": eu_penalty,
            "price_quality_penalty": price_quality_penalty,
            "local_street_bonus": local_street_bonus,
            "scarcity_bonus": scarcity_bonus,  # Unified scarcity (includes hours, days, cuisine)
            "tier_adjustment": tier_adjustment,
            "guide_bonus": guide_bonus,
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
    df["tier"] = [r["tier"] for r in results]
    df["closes_early"] = [r["closes_early"] for r in results]
    df["typical_close_hour"] = [r["typical_close_hour"] for r in results]
    df["weekdays_only"] = [r["weekdays_only"] for r in results]
    df["closed_sunday"] = [r["closed_sunday"] for r in results]
    df["days_open_count"] = [r["days_open_count"] for r in results]
    df["is_rare_cuisine"] = [r["is_rare_cuisine"] for r in results]
    df["michelin_stars"] = [r["michelin_stars"] for r in results]
    df["bib_gourmand"] = [r["bib_gourmand"] for r in results]
    df["gault_millau"] = [r["gault_millau"] for r in results]

    # Add component columns for debugging/transparency
    for component in ["tourist_penalty", "scarcity_bonus", "local_street_bonus"]:
        df[f"score_{component}"] = [r["components"][component] for r in results]

    # Add scarcity sub-components for detailed analysis
    for sub in ["review_scarcity", "hours_scarcity", "days_scarcity", "schedule_scarcity", "cuisine_scarcity"]:
        df[f"scarcity_{sub}"] = [r["scarcity_components"][sub] for r in results]

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

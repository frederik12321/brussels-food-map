"""
Scrape review data from Google Maps for language analysis.

Uses the Places API to get reviews with language detection.
Note: This is optional enhancement - requires additional API calls.
"""

import os
import json
import time
import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
DETAILS_URL = "https://places.googleapis.com/v1/places"


def get_place_reviews(place_id, max_reviews=5):
    """Get reviews for a place."""
    headers = {
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "reviews"
    }

    url = f"{DETAILS_URL}/{place_id}"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return None

    data = response.json()
    return data.get("reviews", [])


def detect_language_simple(text):
    """
    Simple language detection based on character patterns and common words.
    Returns language code.
    """
    if not text:
        return "unknown"

    text_lower = text.lower()

    # Check for non-Latin scripts first
    # Arabic
    if any('\u0600' <= c <= '\u06FF' for c in text):
        return "ar"
    # Turkish specific characters
    if any(c in text_lower for c in ['ğ', 'ş', 'ı', 'ü', 'ö', 'ç']):
        return "tr"
    # Dutch specific
    if any(word in text_lower for word in ['lekker', 'eten', 'goed', 'leuk', 'mooi', 'deze', 'heel', 'erg']):
        return "nl"
    # French indicators
    if any(word in text_lower for word in ['très', 'était', 'nous', 'avec', 'pour', 'mais', 'sont', 'cette', 'leur']):
        return "fr"
    # Portuguese
    if any(word in text_lower for word in ['muito', 'bom', 'não', 'está', 'são', 'uma', 'boa']):
        return "pt"
    # Spanish
    if any(word in text_lower for word in ['muy', 'está', 'pero', 'una', 'los', 'las', 'por', 'con']):
        return "es"
    # German
    if any(word in text_lower for word in ['sehr', 'ist', 'und', 'das', 'ein', 'für', 'auch', 'war']):
        return "de"
    # Italian
    if any(word in text_lower for word in ['molto', 'sono', 'questo', 'una', 'con', 'che', 'anche']):
        return "it"
    # English (default for Latin script)
    if any(word in text_lower for word in ['the', 'and', 'was', 'very', 'good', 'food', 'great', 'nice']):
        return "en"

    return "other"


def analyze_reviews_for_restaurant(place_id):
    """
    Get reviews and analyze language distribution.
    Returns dict of language -> count.
    """
    reviews = get_place_reviews(place_id)

    if not reviews:
        return {}

    language_counts = {}

    for review in reviews:
        # Google provides originalLanguage in some cases
        orig_lang = review.get("originalText", {}).get("languageCode")
        text = review.get("originalText", {}).get("text", "")

        if orig_lang:
            lang = orig_lang
        else:
            lang = detect_language_simple(text)

        language_counts[lang] = language_counts.get(lang, 0) + 1

    return language_counts


def scrape_review_languages(input_file="../data/brussels_restaurants.json",
                           output_file="../data/restaurants_with_languages.json",
                           limit=None):
    """
    Scrape review languages for all restaurants.
    Warning: This makes one API call per restaurant!
    """
    if not API_KEY:
        print("Error: GOOGLE_MAPS_API_KEY not set")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        restaurants = json.load(f)

    print(f"Loaded {len(restaurants)} restaurants")

    if limit:
        restaurants = restaurants[:limit]
        print(f"Processing first {limit} restaurants only")

    for restaurant in tqdm(restaurants, desc="Analyzing reviews"):
        place_id = restaurant.get("id")
        if not place_id:
            continue

        languages = analyze_reviews_for_restaurant(place_id)
        restaurant["review_languages"] = languages

        time.sleep(0.1)  # Rate limiting

    # Save results
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(restaurants, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to {output_file}")

    # Print summary
    all_languages = {}
    for r in restaurants:
        for lang, count in r.get("review_languages", {}).items():
            all_languages[lang] = all_languages.get(lang, 0) + count

    print("\nLanguage distribution across all reviews:")
    for lang, count in sorted(all_languages.items(), key=lambda x: -x[1]):
        print(f"  {lang}: {count}")

    return restaurants


if __name__ == "__main__":
    import sys

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None

    print("Note: This will make one API call per restaurant.")
    print(f"Estimated cost: ~$0.02-0.05 per restaurant")

    if limit:
        print(f"\nRunning with limit of {limit} restaurants")

    scrape_review_languages(limit=limit)

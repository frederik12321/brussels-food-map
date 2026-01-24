"""
OSM Data Enrichment Script for Brussels Food Map

Uses OpenStreetMap as a secondary source to:
1. Discover restaurants not in Google Maps data
2. Verify new restaurants via Google Places API
3. Enrich with full Google data (ratings, reviews, hours, etc.)

OSM provides unique attributes like outdoor_seating, wheelchair access,
and dietary options that we preserve alongside Google's data.
"""

import os
import json
import time
import requests
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm
from math import radians, cos, sin, asin, sqrt

load_dotenv()

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_DETAILS_URL = "https://places.googleapis.com/v1/places"


def haversine(lon1, lat1, lon2, lat2):
    """Calculate distance between two points in meters."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371000 * c  # meters


def fetch_osm_restaurants(cache_file="/tmp/osm_brussels.json"):
    """Fetch all restaurants from OSM for Brussels Capital Region."""

    # Try to use cached data first
    if os.path.exists(cache_file):
        print(f"Loading cached OSM data from {cache_file}...")
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
            elements = data.get("elements", [])
            if elements:
                print(f"Loaded {len(elements)} elements from cache")
            else:
                print("Cache empty, fetching fresh data...")
                elements = None
        except Exception as e:
            print(f"Error loading cache: {e}")
            elements = None
    else:
        elements = None

    if elements is None:
        print("Fetching restaurants from OpenStreetMap...")

        query = """
        [out:json][timeout:60];
        area["name"="Région de Bruxelles-Capitale - Brussels Hoofdstedelijk Gewest"]->.brussels;
        (
          node["amenity"="restaurant"](area.brussels);
          way["amenity"="restaurant"](area.brussels);
          node["amenity"="cafe"](area.brussels);
          way["amenity"="cafe"](area.brussels);
          node["amenity"="bar"](area.brussels);
          way["amenity"="bar"](area.brussels);
          node["amenity"="fast_food"](area.brussels);
          way["amenity"="fast_food"](area.brussels);
        );
        out body center;
        """

        response = requests.post(OVERPASS_URL, data={"data": query})

        if response.status_code != 200:
            print(f"Error fetching OSM data: {response.status_code}")
            return []

        data = response.json()
        elements = data.get("elements", [])

        # Cache the data
        with open(cache_file, "w") as f:
            json.dump(data, f)
        print(f"Cached OSM data to {cache_file}")

    restaurants = []
    for e in elements:
        tags = e.get("tags", {})
        if not tags.get("name"):
            continue

        # Get coordinates (nodes have lat/lon, ways have center)
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")

        if not lat or not lon:
            continue

        restaurants.append({
            "osm_id": e.get("id"),
            "osm_type": e.get("type"),
            "name": tags.get("name"),
            "lat": lat,
            "lon": lon,
            "amenity": tags.get("amenity"),
            "cuisine": tags.get("cuisine"),
            "outdoor_seating": tags.get("outdoor_seating"),
            "wheelchair": tags.get("wheelchair"),
            "diet_vegan": tags.get("diet:vegan"),
            "diet_vegetarian": tags.get("diet:vegetarian"),
            "diet_halal": tags.get("diet:halal"),
            "osm_phone": tags.get("phone") or tags.get("contact:phone"),
            "osm_website": tags.get("website") or tags.get("contact:website"),
            "osm_opening_hours": tags.get("opening_hours"),
        })

    print(f"Found {len(restaurants)} restaurants in OSM")
    return restaurants


def normalize_name(name):
    """Normalize restaurant name for comparison."""
    if not name:
        return ""
    return (name.lower()
            .replace("'", "")
            .replace("'", "")
            .replace("-", " ")
            .replace("  ", " ")
            .strip())


def find_matching_google_restaurant(osm_restaurant, google_df):
    """Find if OSM restaurant already exists in Google data."""
    osm_name = normalize_name(osm_restaurant["name"])
    osm_lat = osm_restaurant["lat"]
    osm_lon = osm_restaurant["lon"]

    # First try exact name match within 100m
    for _, row in google_df.iterrows():
        google_name = normalize_name(row.get("name", ""))
        if google_name == osm_name:
            dist = haversine(osm_lon, osm_lat, row["lng"], row["lat"])
            if dist < 100:
                return row["id"]

    # Then try partial name match within 50m
    for _, row in google_df.iterrows():
        google_name = normalize_name(row.get("name", ""))
        dist = haversine(osm_lon, osm_lat, row["lng"], row["lat"])
        if dist < 50:
            # Check if names are similar enough
            if osm_name in google_name or google_name in osm_name:
                return row["id"]
            # Check word overlap
            osm_words = set(osm_name.split())
            google_words = set(google_name.split())
            if len(osm_words & google_words) >= 2:
                return row["id"]

    return None


def search_google_places(name, lat, lon):
    """Search for a restaurant on Google Places API."""
    if not API_KEY:
        return None

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,"
            "places.location,places.rating,places.userRatingCount,"
            "places.priceLevel,places.types,places.primaryType,"
            "places.primaryTypeDisplayName,places.websiteUri,"
            "places.googleMapsUri,places.regularOpeningHours"
        )
    }

    body = {
        "textQuery": f"{name} restaurant Brussels",
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": 100.0
            }
        },
        "maxResultCount": 5
    }

    try:
        response = requests.post(PLACES_SEARCH_URL, headers=headers, json=body)
        if response.status_code != 200:
            return None

        data = response.json()
        places = data.get("places", [])

        # Find best match based on distance and name similarity
        osm_name = normalize_name(name)

        for place in places:
            place_name = normalize_name(place.get("displayName", {}).get("text", ""))
            place_lat = place.get("location", {}).get("latitude")
            place_lon = place.get("location", {}).get("longitude")

            if place_lat and place_lon:
                dist = haversine(lon, lat, place_lon, place_lat)

                # Accept if within 100m and name is similar
                if dist < 100:
                    if osm_name in place_name or place_name in osm_name:
                        return place
                    osm_words = set(osm_name.split())
                    place_words = set(place_name.split())
                    if len(osm_words & place_words) >= 1:
                        return place

        return None

    except Exception as e:
        print(f"Error searching Google Places: {e}")
        return None


def parse_google_place(place, osm_data):
    """Parse Google place data and merge with OSM attributes."""
    location = place.get("location", {})
    display_name = place.get("displayName", {})
    primary_type_display = place.get("primaryTypeDisplayName", {})
    opening_hours = place.get("regularOpeningHours", {})

    # Extract closing times and days open
    closing_times = {}
    days_open = set()
    weekday_descriptions = opening_hours.get("weekdayDescriptions", [])
    periods = opening_hours.get("periods", [])

    for period in periods:
        open_info = period.get("open", {})
        if open_info:
            day = open_info.get("day")
            if day is not None:
                days_open.add(day)

        close_info = period.get("close", {})
        if close_info:
            day = close_info.get("day", 0)
            hour = close_info.get("hour", 0)
            minute = close_info.get("minute", 0)
            closing_times[day] = f"{hour:02d}:{minute:02d}"

    return {
        "id": place.get("id"),
        "name": display_name.get("text", ""),
        "address": place.get("formattedAddress", ""),
        "lat": location.get("latitude"),
        "lng": location.get("longitude"),
        "rating": place.get("rating"),
        "review_count": place.get("userRatingCount", 0),
        "price_level": place.get("priceLevel"),
        "types": place.get("types", []),
        "primary_type": place.get("primaryType", ""),
        "primary_type_display": primary_type_display.get("text", ""),
        "website": place.get("websiteUri"),
        "google_maps_url": place.get("googleMapsUri"),
        "opening_hours": weekday_descriptions,
        "closing_times": closing_times,
        "days_open": sorted(list(days_open)),
        # OSM-specific attributes preserved
        "osm_id": osm_data.get("osm_id"),
        "outdoor_seating": osm_data.get("outdoor_seating"),
        "wheelchair": osm_data.get("wheelchair"),
        "diet_vegan": osm_data.get("diet_vegan"),
        "diet_vegetarian": osm_data.get("diet_vegetarian"),
        "diet_halal": osm_data.get("diet_halal"),
        "source": "osm_verified"
    }


def enrich_from_osm(
    google_data_file="../data/brussels_restaurants.json",
    output_file="../data/brussels_restaurants_enriched.json",
    max_new=500,
    delay=0.1
):
    """
    Main function to discover and verify new restaurants from OSM.

    Args:
        google_data_file: Path to existing Google Maps restaurant data
        output_file: Path to save enriched data
        max_new: Maximum number of new restaurants to add
        delay: Delay between API calls in seconds
    """
    if not API_KEY:
        print("Error: GOOGLE_MAPS_API_KEY not set in environment")
        return

    # Load existing Google data
    print(f"Loading existing data from {google_data_file}...")
    with open(google_data_file, "r", encoding="utf-8") as f:
        google_restaurants = json.load(f)

    google_df = pd.DataFrame(google_restaurants)
    print(f"Loaded {len(google_df)} existing restaurants")

    # Fetch OSM data
    osm_restaurants = fetch_osm_restaurants()

    # Find restaurants in OSM but not in Google data
    print("\nFinding new restaurants not in Google data...")
    new_candidates = []

    for osm_r in tqdm(osm_restaurants, desc="Matching OSM to Google"):
        match_id = find_matching_google_restaurant(osm_r, google_df)
        if not match_id:
            new_candidates.append(osm_r)

    print(f"Found {len(new_candidates)} potential new restaurants")

    # Limit to max_new
    if len(new_candidates) > max_new:
        print(f"Limiting to {max_new} restaurants for verification")
        new_candidates = new_candidates[:max_new]

    # Verify and enrich via Google Places API
    print("\nVerifying new restaurants via Google Places API...")
    verified_new = []
    not_found = []

    for osm_r in tqdm(new_candidates, desc="Verifying via Google"):
        google_place = search_google_places(
            osm_r["name"],
            osm_r["lat"],
            osm_r["lon"]
        )

        if google_place:
            parsed = parse_google_place(google_place, osm_r)
            # Only add if not already in our data (double check by Google ID)
            if parsed["id"] not in google_df["id"].values:
                verified_new.append(parsed)
        else:
            not_found.append(osm_r)

        time.sleep(delay)

    print(f"\nVerification results:")
    print(f"  Verified and added: {len(verified_new)}")
    print(f"  Not found on Google: {len(not_found)}")

    # Merge with existing data
    all_restaurants = google_restaurants + verified_new

    # Save enriched data
    print(f"\nSaving {len(all_restaurants)} restaurants to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_restaurants, f, ensure_ascii=False, indent=2)

    # Also save not-found list for reference
    not_found_file = output_file.replace(".json", "_osm_only.json")
    with open(not_found_file, "w", encoding="utf-8") as f:
        json.dump(not_found, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(not_found)} OSM-only restaurants to {not_found_file}")

    # Print sample of new restaurants
    if verified_new:
        print("\nSample of newly added restaurants:")
        for r in verified_new[:5]:
            osm_attrs = []
            if r.get("outdoor_seating") == "yes":
                osm_attrs.append("terrace")
            if r.get("wheelchair") == "yes":
                osm_attrs.append("wheelchair")
            if r.get("diet_vegan") in ["yes", "only"]:
                osm_attrs.append("vegan")
            if r.get("diet_vegetarian") in ["yes", "only"]:
                osm_attrs.append("vegetarian")

            attrs_str = f" [{', '.join(osm_attrs)}]" if osm_attrs else ""
            print(f"  - {r['name']} ({r.get('rating', 'N/A')}★, {r.get('review_count', 0)} reviews){attrs_str}")

    return verified_new


def enrich_existing_with_osm_attributes(
    google_data_file="../data/brussels_restaurants.json",
    output_file="../data/brussels_restaurants_enriched.json"
):
    """
    Add OSM attributes (outdoor_seating, wheelchair, dietary) to existing Google data.
    """
    print(f"Loading existing data from {google_data_file}...")
    with open(google_data_file, "r", encoding="utf-8") as f:
        google_restaurants = json.load(f)

    google_df = pd.DataFrame(google_restaurants)
    print(f"Loaded {len(google_df)} existing restaurants")

    # Fetch OSM data
    osm_restaurants = fetch_osm_restaurants()

    # Match and enrich
    print("\nMatching OSM attributes to existing restaurants...")
    enriched_count = 0

    for osm_r in tqdm(osm_restaurants, desc="Enriching"):
        match_id = find_matching_google_restaurant(osm_r, google_df)

        if match_id:
            # Find the restaurant in our list and add OSM attributes
            for r in google_restaurants:
                if r.get("id") == match_id:
                    # Add OSM attributes if not already present
                    if osm_r.get("outdoor_seating") and not r.get("outdoor_seating"):
                        r["outdoor_seating"] = osm_r["outdoor_seating"]
                        enriched_count += 1
                    if osm_r.get("wheelchair") and not r.get("wheelchair"):
                        r["wheelchair"] = osm_r["wheelchair"]
                    if osm_r.get("diet_vegan") and not r.get("diet_vegan"):
                        r["diet_vegan"] = osm_r["diet_vegan"]
                    if osm_r.get("diet_vegetarian") and not r.get("diet_vegetarian"):
                        r["diet_vegetarian"] = osm_r["diet_vegetarian"]
                    if osm_r.get("diet_halal") and not r.get("diet_halal"):
                        r["diet_halal"] = osm_r["diet_halal"]
                    break

    print(f"Enriched {enriched_count} restaurants with OSM attributes")

    # Save
    print(f"Saving to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(google_restaurants, f, ensure_ascii=False, indent=2)

    # Count attributes
    outdoor = sum(1 for r in google_restaurants if r.get("outdoor_seating") == "yes")
    wheelchair = sum(1 for r in google_restaurants if r.get("wheelchair"))
    vegan = sum(1 for r in google_restaurants if r.get("diet_vegan") in ["yes", "only"])
    vegetarian = sum(1 for r in google_restaurants if r.get("diet_vegetarian") in ["yes", "only"])

    print(f"\nAttribute coverage after enrichment:")
    print(f"  Outdoor seating: {outdoor}")
    print(f"  Wheelchair info: {wheelchair}")
    print(f"  Vegan options: {vegan}")
    print(f"  Vegetarian options: {vegetarian}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "attributes":
        # Only add OSM attributes to existing data (no new restaurants)
        enrich_existing_with_osm_attributes()
    elif len(sys.argv) > 1 and sys.argv[1] == "discover":
        # Discover and verify new restaurants
        max_new = int(sys.argv[2]) if len(sys.argv) > 2 else 500
        enrich_from_osm(max_new=max_new)
    else:
        print("Usage:")
        print("  python enrich_from_osm.py attributes  - Add OSM attributes to existing restaurants")
        print("  python enrich_from_osm.py discover [max_new]  - Discover new restaurants from OSM")
        print("")
        print("Examples:")
        print("  python enrich_from_osm.py attributes")
        print("  python enrich_from_osm.py discover 100")

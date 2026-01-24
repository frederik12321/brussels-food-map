"""
Scrape specific Brussels communes with focused coverage.
"""

import os
import json
import time
import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
BASE_URL = "https://places.googleapis.com/v1/places:searchNearby"
SEARCH_RADIUS = 600  # Smaller radius for denser coverage

# Commune boundaries (approximate)
COMMUNES = {
    "Bruxelles-Centre": {
        "center": (50.8467, 4.3517),
        "bounds": {"north": 50.8600, "south": 50.8350, "east": 4.3700, "west": 4.3300}
    },
    "Saint-Gilles": {
        "center": (50.8261, 4.3456),
        "bounds": {"north": 50.8350, "south": 50.8150, "east": 4.3600, "west": 4.3300}
    },
    "Ixelles": {
        "center": (50.8275, 4.3697),
        "bounds": {"north": 50.8450, "south": 50.8100, "east": 4.4000, "west": 4.3500}
    },
    "Etterbeek": {
        "center": (50.8333, 4.3833),
        "bounds": {"north": 50.8450, "south": 50.8200, "east": 4.4100, "west": 4.3700}
    }
}


def generate_grid_points(bounds, step_km=0.4):
    """Generate a dense grid of points for a commune."""
    points = []
    lat = bounds["south"]

    lat_step = step_km / 111
    lng_step = step_km / 71

    while lat <= bounds["north"]:
        lng = bounds["west"]
        while lng <= bounds["east"]:
            points.append((lat, lng))
            lng += lng_step
        lat += lat_step

    return points


def search_nearby(lat, lng, radius=SEARCH_RADIUS):
    """Search for restaurants near a location."""
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
        "includedTypes": ["restaurant", "cafe", "bar", "bakery", "meal_takeaway"],
        "maxResultCount": 20,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radius
            }
        }
    }

    response = requests.post(BASE_URL, headers=headers, json=body)

    if response.status_code != 200:
        return None

    return response.json().get("places", [])


def parse_place(place):
    """Parse a place object into a clean dictionary."""
    location = place.get("location", {})
    display_name = place.get("displayName", {})
    primary_type_display = place.get("primaryTypeDisplayName", {})
    opening_hours = place.get("regularOpeningHours", {})

    # Extract closing times and days open
    closing_times = {}
    days_open = set()  # Track which days the restaurant is open
    weekday_descriptions = opening_hours.get("weekdayDescriptions", [])
    periods = opening_hours.get("periods", [])

    # Parse periods to get closing times and days open (more structured)
    for period in periods:
        # Get the opening day
        open_info = period.get("open", {})
        if open_info:
            day = open_info.get("day")
            if day is not None:
                days_open.add(day)

        close_info = period.get("close", {})
        if close_info:
            day = close_info.get("day", 0)  # 0=Sunday, 1=Monday, etc.
            hour = close_info.get("hour", 0)
            minute = close_info.get("minute", 0)
            closing_times[day] = f"{hour:02d}:{minute:02d}"

    # Convert days_open to a sorted list (0=Sunday, 1=Monday, ..., 6=Saturday)
    days_open_list = sorted(list(days_open))

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
        "days_open": days_open_list
    }


def scrape_communes(communes_to_scrape=None):
    """Scrape restaurants from specific communes."""
    if not API_KEY:
        print("Error: GOOGLE_MAPS_API_KEY not set")
        return

    if communes_to_scrape is None:
        communes_to_scrape = list(COMMUNES.keys())

    all_places = {}

    for commune_name in communes_to_scrape:
        if commune_name not in COMMUNES:
            print(f"Unknown commune: {commune_name}")
            continue

        commune = COMMUNES[commune_name]
        grid_points = generate_grid_points(commune["bounds"])
        print(f"\n{commune_name}: {len(grid_points)} grid points")

        for lat, lng in tqdm(grid_points, desc=f"Scraping {commune_name}"):
            places = search_nearby(lat, lng)

            if places:
                for place in places:
                    parsed = parse_place(place)
                    if parsed["id"] and parsed["id"] not in all_places:
                        all_places[parsed["id"]] = parsed

            time.sleep(0.05)

    restaurants = list(all_places.values())
    print(f"\nFound {len(restaurants)} unique restaurants from selected communes")

    # Save to file
    output_file = "../data/communes_restaurants.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(restaurants, f, ensure_ascii=False, indent=2)

    print(f"Saved to {output_file}")
    return restaurants


def merge_with_existing():
    """Merge new data with existing dataset."""
    # Load existing data
    existing_file = "../data/brussels_restaurants.json"
    new_file = "../data/communes_restaurants.json"

    try:
        with open(existing_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Loaded {len(existing)} existing restaurants")
    except FileNotFoundError:
        existing = []
        print("No existing data found")

    try:
        with open(new_file, "r", encoding="utf-8") as f:
            new_data = json.load(f)
        print(f"Loaded {len(new_data)} new restaurants")
    except FileNotFoundError:
        print("No new data to merge")
        return

    # Merge by ID
    all_restaurants = {r["id"]: r for r in existing}
    new_count = 0
    for r in new_data:
        if r["id"] not in all_restaurants:
            all_restaurants[r["id"]] = r
            new_count += 1

    merged = list(all_restaurants.values())
    print(f"Added {new_count} new restaurants")
    print(f"Total: {len(merged)} restaurants")

    # Save merged data
    with open(existing_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"Saved merged data to {existing_file}")
    return merged


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "merge":
        merge_with_existing()
    else:
        # Scrape all 4 communes
        scrape_communes(["Bruxelles-Centre", "Saint-Gilles", "Ixelles", "Etterbeek"])

        # Ask to merge
        print("\nRun 'python scrape_communes.py merge' to merge with existing data")

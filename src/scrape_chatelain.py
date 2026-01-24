"""
Scrape restaurants specifically in the Chatelain area of Brussels.
Chatelain is centered around Place du Châtelain in Ixelles.
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

# Chatelain area bounds - tight focus on the neighborhood
# Center: Place du Châtelain ~50.8245, 4.3625
CHATELAIN_BOUNDS = {
    "north": 50.8320,
    "south": 50.8170,
    "east": 4.3750,
    "west": 4.3500
}

# Smaller radius for denser coverage
SEARCH_RADIUS = 300


def generate_grid_points(bounds, step_km=0.25):
    """Generate a dense grid of lat/lng points covering Chatelain."""
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
        print(f"Error: {response.status_code} - {response.text}")
        return None

    data = response.json()
    return data.get("places", [])


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


def scrape_chatelain():
    """Scrape all restaurants in the Chatelain area."""
    if not API_KEY:
        print("Error: GOOGLE_MAPS_API_KEY not set")
        return

    grid_points = generate_grid_points(CHATELAIN_BOUNDS)
    print(f"Searching Chatelain area with {len(grid_points)} grid points...")

    all_places = {}

    for lat, lng in tqdm(grid_points, desc="Searching Chatelain"):
        places = search_nearby(lat, lng)

        if places:
            for place in places:
                parsed = parse_place(place)
                if parsed["id"] and parsed["id"] not in all_places:
                    all_places[parsed["id"]] = parsed

        time.sleep(0.05)

    restaurants = list(all_places.values())
    print(f"\nFound {len(restaurants)} restaurants in Chatelain")

    # Save to file
    output_file = "../data/chatelain_restaurants.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(restaurants, f, ensure_ascii=False, indent=2)

    print(f"Saved to {output_file}")

    # Print summary
    print("\n--- Chatelain Restaurants Summary ---")
    rated = [r for r in restaurants if r.get("rating")]
    if rated:
        avg_rating = sum(r["rating"] for r in rated) / len(rated)
        print(f"Average rating: {avg_rating:.2f}")

        top_5 = sorted(rated, key=lambda x: (x["rating"], x.get("review_count", 0)), reverse=True)[:10]
        print("\nTop 10 by rating:")
        for r in top_5:
            print(f"  {r['name']}: {r['rating']}★ ({r.get('review_count', 0)} reviews)")

    return restaurants


if __name__ == "__main__":
    scrape_chatelain()

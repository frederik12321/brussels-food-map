"""
Dense scraping for high-density areas to capture more restaurants.

The regular scraper misses restaurants like Les Brigittines because:
- searchNearby returns max 20 results per location
- Results are sorted by prominence (review count)
- In dense areas, popular places crowd out less-reviewed restaurants

Solution: Use smaller radius and denser grid in high-traffic areas.
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

# Dense areas that need finer-grained scraping
DENSE_AREAS = {
    "Grand-Place": {
        "center": (50.8467, 4.3525),
        "bounds": {"north": 50.8550, "south": 50.8380, "east": 4.3650, "west": 4.3400}
    },
    "Sablon": {
        "center": (50.8419, 4.3551),
        "bounds": {"north": 50.8480, "south": 50.8380, "east": 4.3620, "west": 4.3480}
    },
    "Marolles": {
        "center": (50.8390, 4.3470),
        "bounds": {"north": 50.8450, "south": 50.8330, "east": 4.3550, "west": 4.3400}
    },
    "Saint-Catherine": {
        "center": (50.8515, 4.3470),
        "bounds": {"north": 50.8560, "south": 50.8470, "east": 4.3540, "west": 4.3400}
    },
    "Flagey-Ixelles": {
        "center": (50.8275, 4.3720),
        "bounds": {"north": 50.8350, "south": 50.8200, "east": 4.3800, "west": 4.3640}
    },
    "Chatelain": {
        "center": (50.8230, 4.3590),
        "bounds": {"north": 50.8290, "south": 50.8170, "east": 4.3670, "west": 4.3510},
        "step_km": 0.08,  # Extra fine grid for Chatelain
        "radius": 150     # Smaller radius to avoid crowding
    },
    "Saint-Gilles-Parvis": {
        "center": (50.8280, 4.3460),
        "bounds": {"north": 50.8340, "south": 50.8220, "east": 4.3540, "west": 4.3380}
    },
    "Vrijheidswijk": {
        "center": (50.8520, 4.3700),
        "bounds": {"north": 50.8580, "south": 50.8460, "east": 4.3800, "west": 4.3600},
        "step_km": 0.08,
        "radius": 150
    }
}

# Ultra-dense areas - specific streets/blocks that need very fine scraping
ULTRA_DENSE_AREAS = {
    # Chatelain
    "Chatelain-Core": {
        "center": (50.8235, 4.3595),
        "bounds": {"north": 50.8260, "south": 50.8210, "east": 4.3630, "west": 4.3550},
        "step_km": 0.05,
        "radius": 100
    },
    "Rue-Americaine": {
        "center": (50.8231, 4.3591),
        "bounds": {"north": 50.8250, "south": 50.8210, "east": 4.3620, "west": 4.3560},
        "step_km": 0.04,
        "radius": 80
    },

    # Saint-Gilles - comprehensive coverage
    "Parvis-Saint-Gilles": {
        "center": (50.8270, 4.3465),
        "bounds": {"north": 50.8300, "south": 50.8240, "east": 4.3510, "west": 4.3420},
        "step_km": 0.04,
        "radius": 80
    },
    "Rue-du-Fort": {
        "center": (50.8255, 4.3490),
        "bounds": {"north": 50.8280, "south": 50.8230, "east": 4.3530, "west": 4.3450},
        "step_km": 0.04,
        "radius": 80
    },
    "Chaussee-Charleroi-StGilles": {
        "center": (50.8300, 4.3520),
        "bounds": {"north": 50.8340, "south": 50.8260, "east": 4.3580, "west": 4.3460},
        "step_km": 0.05,
        "radius": 100
    },
    "Rue-Vanderschrick": {
        "center": (50.8245, 4.3435),
        "bounds": {"north": 50.8270, "south": 50.8220, "east": 4.3480, "west": 4.3390},
        "step_km": 0.04,
        "radius": 80
    },
    "Rue-de-Moscou": {
        "center": (50.8265, 4.3445),
        "bounds": {"north": 50.8285, "south": 50.8245, "east": 4.3480, "west": 4.3410},
        "step_km": 0.04,
        "radius": 80
    },
    "Barriere-Saint-Gilles": {
        "center": (50.8235, 4.3475),
        "bounds": {"north": 50.8260, "south": 50.8210, "east": 4.3520, "west": 4.3430},
        "step_km": 0.04,
        "radius": 80
    },
    "Avenue-Jean-Volders": {
        "center": (50.8285, 4.3410),
        "bounds": {"north": 50.8310, "south": 50.8260, "east": 4.3460, "west": 4.3360},
        "step_km": 0.04,
        "radius": 80
    },
    "Place-Bethlehem": {
        "center": (50.8205, 4.3455),
        "bounds": {"north": 50.8230, "south": 50.8180, "east": 4.3500, "west": 4.3410},
        "step_km": 0.04,
        "radius": 80
    },
    "Rue-de-la-Victoire": {
        "center": (50.8220, 4.3510),
        "bounds": {"north": 50.8245, "south": 50.8195, "east": 4.3560, "west": 4.3460},
        "step_km": 0.04,
        "radius": 80
    },
    "Porte-de-Hal-South": {
        "center": (50.8350, 4.3480),
        "bounds": {"north": 50.8380, "south": 50.8320, "east": 4.3540, "west": 4.3420},
        "step_km": 0.04,
        "radius": 80
    },

    # Brussels Centre
    "Grand-Place-Core": {
        "center": (50.8467, 4.3525),
        "bounds": {"north": 50.8500, "south": 50.8435, "east": 4.3580, "west": 4.3470},
        "step_km": 0.04,
        "radius": 80
    },
    "Rue-des-Bouchers": {
        "center": (50.8480, 4.3545),
        "bounds": {"north": 50.8500, "south": 50.8460, "east": 4.3580, "west": 4.3510},
        "step_km": 0.03,
        "radius": 60
    },
    "Saint-Catherine-Core": {
        "center": (50.8510, 4.3465),
        "bounds": {"north": 50.8545, "south": 50.8475, "east": 4.3520, "west": 4.3410},
        "step_km": 0.04,
        "radius": 80
    },
    "Dansaert": {
        "center": (50.8505, 4.3430),
        "bounds": {"north": 50.8540, "south": 50.8470, "east": 4.3480, "west": 4.3380},
        "step_km": 0.04,
        "radius": 80
    },
    "Sablon-Core": {
        "center": (50.8420, 4.3550),
        "bounds": {"north": 50.8450, "south": 50.8390, "east": 4.3600, "west": 4.3500},
        "step_km": 0.04,
        "radius": 80
    },
    "Marolles-Core": {
        "center": (50.8390, 4.3470),
        "bounds": {"north": 50.8420, "south": 50.8360, "east": 4.3520, "west": 4.3420},
        "step_km": 0.04,
        "radius": 80
    },

    # Flagey / Ixelles - comprehensive coverage
    "Place-Flagey": {
        "center": (50.8275, 4.3720),
        "bounds": {"north": 50.8305, "south": 50.8245, "east": 4.3770, "west": 4.3670},
        "step_km": 0.04,
        "radius": 80
    },
    "Rue-Lesbroussart": {
        "center": (50.8265, 4.3755),
        "bounds": {"north": 50.8290, "south": 50.8240, "east": 4.3800, "west": 4.3710},
        "step_km": 0.04,
        "radius": 80
    },
    "Chaussee-Ixelles": {
        "center": (50.8310, 4.3670),
        "bounds": {"north": 50.8350, "south": 50.8270, "east": 4.3720, "west": 4.3620},
        "step_km": 0.04,
        "radius": 80
    },
    "Matongé": {
        "center": (50.8325, 4.3635),
        "bounds": {"north": 50.8355, "south": 50.8295, "east": 4.3680, "west": 4.3590},
        "step_km": 0.04,
        "radius": 80
    },
    "Place-Fernand-Cocq": {
        "center": (50.8280, 4.3680),
        "bounds": {"north": 50.8305, "south": 50.8255, "east": 4.3720, "west": 4.3640},
        "step_km": 0.04,
        "radius": 80
    },
    "Saint-Boniface": {
        "center": (50.8308, 4.3672),
        "bounds": {"north": 50.8335, "south": 50.8280, "east": 4.3720, "west": 4.3620},
        "step_km": 0.04,
        "radius": 80
    },
    "Rue-de-la-Paix": {
        "center": (50.8295, 4.3665),
        "bounds": {"north": 50.8320, "south": 50.8270, "east": 4.3710, "west": 4.3620},
        "step_km": 0.04,
        "radius": 80
    },
    "Avenue-Louise-South": {
        "center": (50.8200, 4.3630),
        "bounds": {"north": 50.8250, "south": 50.8150, "east": 4.3700, "west": 4.3560},
        "step_km": 0.05,
        "radius": 100
    },
    "Place-du-Luxembourg": {
        "center": (50.8380, 4.3720),
        "bounds": {"north": 50.8410, "south": 50.8350, "east": 4.3780, "west": 4.3660},
        "step_km": 0.04,
        "radius": 80
    },
    "Etangs-Ixelles": {
        "center": (50.8220, 4.3720),
        "bounds": {"north": 50.8260, "south": 50.8180, "east": 4.3780, "west": 4.3660},
        "step_km": 0.04,
        "radius": 80
    },
    "Rue-du-Bailli": {
        "center": (50.8260, 4.3610),
        "bounds": {"north": 50.8290, "south": 50.8230, "east": 4.3660, "west": 4.3560},
        "step_km": 0.04,
        "radius": 80
    },
    "Rue-Washington": {
        "center": (50.8235, 4.3660),
        "bounds": {"north": 50.8265, "south": 50.8205, "east": 4.3710, "west": 4.3610},
        "step_km": 0.04,
        "radius": 80
    },
    "Rue-Longue-Vie": {
        "center": (50.8255, 4.3700),
        "bounds": {"north": 50.8280, "south": 50.8230, "east": 4.3750, "west": 4.3650},
        "step_km": 0.04,
        "radius": 80
    },
    "ULB-Solbosch": {
        "center": (50.8130, 4.3820),
        "bounds": {"north": 50.8180, "south": 50.8080, "east": 4.3900, "west": 4.3740},
        "step_km": 0.05,
        "radius": 100
    },
    "Cimetiere-Ixelles": {
        "center": (50.8185, 4.3770),
        "bounds": {"north": 50.8220, "south": 50.8150, "east": 4.3830, "west": 4.3710},
        "step_km": 0.04,
        "radius": 80
    },

    # Vrijheidswijk / Saint-Josse near Madou - diverse food scene
    "Vrijheidswijk-Core": {
        "center": (50.8520, 4.3700),
        "bounds": {"north": 50.8560, "south": 50.8480, "east": 4.3760, "west": 4.3640},
        "step_km": 0.04,
        "radius": 80
    },
    "Madou": {
        "center": (50.8510, 4.3700),
        "bounds": {"north": 50.8545, "south": 50.8475, "east": 4.3760, "west": 4.3640},
        "step_km": 0.04,
        "radius": 80
    },
    "Rue-de-la-Liberte": {
        "center": (50.8525, 4.3680),
        "bounds": {"north": 50.8560, "south": 50.8490, "east": 4.3740, "west": 4.3620},
        "step_km": 0.04,
        "radius": 80
    },
    "Chaussee-de-Haecht": {
        "center": (50.8540, 4.3720),
        "bounds": {"north": 50.8580, "south": 50.8500, "east": 4.3800, "west": 4.3640},
        "step_km": 0.04,
        "radius": 80
    },
    "Place-Saint-Josse": {
        "center": (50.8535, 4.3755),
        "bounds": {"north": 50.8570, "south": 50.8500, "east": 4.3810, "west": 4.3700},
        "step_km": 0.04,
        "radius": 80
    }
}


def generate_dense_grid(bounds, step_km=0.15):
    """Generate a very dense grid for high-traffic areas."""
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


def search_nearby(lat, lng, radius=300):
    """Search for restaurants with small radius."""
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


def scrape_dense_areas(areas_to_scrape=None, radius=300, step_km=0.15, include_ultra=False):
    """Scrape dense areas with finer grid."""
    if not API_KEY:
        print("Error: GOOGLE_MAPS_API_KEY not set")
        return

    if areas_to_scrape is None:
        areas_to_scrape = list(DENSE_AREAS.keys())

    all_places = {}

    for area_name in areas_to_scrape:
        if area_name not in DENSE_AREAS:
            print(f"Unknown area: {area_name}")
            continue

        area = DENSE_AREAS[area_name]
        # Use area-specific settings if available, otherwise use defaults
        area_step = area.get("step_km", step_km)
        area_radius = area.get("radius", radius)
        grid_points = generate_dense_grid(area["bounds"], step_km=area_step)
        print(f"\n{area_name}: {len(grid_points)} grid points (radius={area_radius}m, step={area_step}km)")

        for lat, lng in tqdm(grid_points, desc=f"Scraping {area_name}"):
            places = search_nearby(lat, lng, radius=area_radius)

            if places:
                for place in places:
                    parsed = parse_place(place)
                    if parsed["id"] and parsed["id"] not in all_places:
                        all_places[parsed["id"]] = parsed

            time.sleep(0.05)

    # Also scrape ultra-dense areas if requested
    if include_ultra:
        for area_name, area in ULTRA_DENSE_AREAS.items():
            area_step = area.get("step_km", 0.05)
            area_radius = area.get("radius", 100)
            grid_points = generate_dense_grid(area["bounds"], step_km=area_step)
            print(f"\n{area_name} (ultra): {len(grid_points)} grid points (radius={area_radius}m, step={area_step}km)")

            for lat, lng in tqdm(grid_points, desc=f"Scraping {area_name}"):
                places = search_nearby(lat, lng, radius=area_radius)

                if places:
                    for place in places:
                        parsed = parse_place(place)
                        if parsed["id"] and parsed["id"] not in all_places:
                            all_places[parsed["id"]] = parsed

                time.sleep(0.05)

    restaurants = list(all_places.values())
    print(f"\nFound {len(restaurants)} unique restaurants from dense areas")

    # Save to file
    output_file = "../data/dense_restaurants.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(restaurants, f, ensure_ascii=False, indent=2)

    print(f"Saved to {output_file}")
    return restaurants


def merge_with_existing():
    """Merge dense scraping results with existing dataset."""
    existing_file = "../data/brussels_restaurants.json"
    new_file = "../data/dense_restaurants.json"

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
        print(f"Loaded {len(new_data)} new restaurants from dense scraping")
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
    elif len(sys.argv) > 1 and sys.argv[1] == "ultra":
        # Scrape only ultra-dense areas (for targeted updates)
        scrape_dense_areas(areas_to_scrape=[], include_ultra=True)
        print("\nRun 'python scrape_dense.py merge' to merge with existing data")
    elif len(sys.argv) > 1 and sys.argv[1] == "chatelain":
        # Scrape just Chatelain with ultra-fine granularity
        scrape_dense_areas(areas_to_scrape=["Chatelain"], include_ultra=True)
        print("\nRun 'python scrape_dense.py merge' to merge with existing data")
    else:
        # Scrape all dense areas with small radius, including ultra-dense
        scrape_dense_areas(radius=300, step_km=0.15, include_ultra=True)

        print("\nRun 'python scrape_dense.py merge' to merge with existing data")

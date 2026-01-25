"""
Collect restaurant data from OpenStreetMap using Overpass API.
No API key required - completely free.

This script fetches restaurants in Brussels and outputs them in a format
compatible with our existing pipeline.
"""

import requests
import json
import csv
from datetime import datetime

# Brussels bounding box (approximate)
# South, West, North, East
BRUSSELS_BBOX = "50.76,4.22,50.92,4.52"

# Overpass API endpoint
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def query_restaurants():
    """Query OpenStreetMap for restaurants in Brussels."""
    
    query = f"""
    [out:json][timeout:120];
    (
      // Restaurants
      node["amenity"="restaurant"]({BRUSSELS_BBOX});
      way["amenity"="restaurant"]({BRUSSELS_BBOX});
      
      // Cafes that serve food
      node["amenity"="cafe"]["cuisine"]({BRUSSELS_BBOX});
      way["amenity"="cafe"]["cuisine"]({BRUSSELS_BBOX});
      
      // Bars that serve food
      node["amenity"="bar"]["cuisine"]({BRUSSELS_BBOX});
      way["amenity"="bar"]["cuisine"]({BRUSSELS_BBOX});
      
      // Fast food
      node["amenity"="fast_food"]({BRUSSELS_BBOX});
      way["amenity"="fast_food"]({BRUSSELS_BBOX});
      
      // Biergarten/beer gardens
      node["amenity"="biergarten"]({BRUSSELS_BBOX});
      way["amenity"="biergarten"]({BRUSSELS_BBOX});
    );
    out center tags;
    """
    
    print("Querying Overpass API for Brussels restaurants...")
    response = requests.post(OVERPASS_URL, data={"data": query})
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        return []
    
    data = response.json()
    return data.get("elements", [])

def parse_osm_element(element):
    """Parse an OSM element into our restaurant format."""
    tags = element.get("tags", {})
    
    # Get coordinates (for ways, use center)
    if element["type"] == "node":
        lat = element.get("lat")
        lng = element.get("lon")
    else:
        center = element.get("center", {})
        lat = center.get("lat")
        lng = center.get("lon")
    
    if not lat or not lng:
        return None
    
    name = tags.get("name")
    if not name:
        return None
    
    # Build address
    address_parts = []
    if tags.get("addr:street"):
        street = tags.get("addr:street")
        housenumber = tags.get("addr:housenumber", "")
        address_parts.append(f"{street} {housenumber}".strip())
    if tags.get("addr:postcode"):
        address_parts.append(tags.get("addr:postcode"))
    if tags.get("addr:city"):
        address_parts.append(tags.get("addr:city"))
    
    address = ", ".join(address_parts) if address_parts else f"Brussels, Belgium"
    
    # Map cuisine to our format
    cuisine = tags.get("cuisine", "").split(";")[0].strip()
    cuisine_map = {
        "italian": "Italian",
        "french": "French",
        "belgian": "Belgian",
        "japanese": "Japanese",
        "chinese": "Chinese",
        "thai": "Thai",
        "indian": "Indian",
        "turkish": "Turkish",
        "moroccan": "Moroccan",
        "lebanese": "Lebanese",
        "greek": "Greek",
        "spanish": "Spanish",
        "mexican": "Mexican",
        "vietnamese": "Vietnamese",
        "korean": "Korean",
        "african": "African",
        "ethiopian": "Ethiopian",
        "congolese": "Congolese",
        "portuguese": "Portuguese",
        "american": "American",
        "burger": "American",
        "pizza": "Italian",
        "sushi": "Japanese",
        "seafood": "Seafood",
        "vegetarian": "Vegetarian",
        "vegan": "Vegan",
    }
    cuisine_normalized = cuisine_map.get(cuisine.lower(), cuisine.title() if cuisine else "Restaurant")
    
    # Amenity type
    amenity = tags.get("amenity", "restaurant")
    
    return {
        "osm_id": element["id"],
        "osm_type": element["type"],
        "name": name,
        "address": address,
        "lat": lat,
        "lng": lng,
        "cuisine": cuisine_normalized,
        "amenity": amenity,
        "website": tags.get("website", ""),
        "phone": tags.get("phone", ""),
        "opening_hours": tags.get("opening_hours", ""),
        "wheelchair": tags.get("wheelchair", ""),
        "outdoor_seating": tags.get("outdoor_seating", ""),
        # OSM doesn't have ratings - these would need to be enriched from Google
        "rating": None,
        "review_count": None,
    }

def save_restaurants(restaurants, output_file="data/osm_restaurants.json"):
    """Save restaurants to JSON file."""
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(restaurants)} restaurants to {output_file}")

def save_csv_for_manual_enrichment(restaurants, output_file="data/osm_restaurants_to_enrich.csv"):
    """
    Save restaurants to CSV for manual Google Maps data entry.
    This file can be opened in Excel/Sheets to add ratings manually.
    """
    fieldnames = [
        "osm_id", "name", "address", "lat", "lng", "cuisine",
        "google_rating", "google_review_count", "google_place_id", "notes"
    ]
    
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for r in restaurants:
            writer.writerow({
                "osm_id": r["osm_id"],
                "name": r["name"],
                "address": r["address"],
                "lat": r["lat"],
                "lng": r["lng"],
                "cuisine": r["cuisine"],
                "google_rating": "",  # To be filled manually
                "google_review_count": "",  # To be filled manually
                "google_place_id": "",  # Optional
                "notes": "",
            })
    
    print(f"Saved CSV for manual enrichment: {output_file}")
    print("Open this file in Excel/Google Sheets and add Google ratings manually.")

def main():
    print("=" * 60)
    print("OpenStreetMap Restaurant Collector for Brussels")
    print("=" * 60)
    print()
    
    # Fetch from OSM
    elements = query_restaurants()
    print(f"Found {len(elements)} elements from OSM")
    
    # Parse into our format
    restaurants = []
    for element in elements:
        parsed = parse_osm_element(element)
        if parsed:
            restaurants.append(parsed)
    
    print(f"Parsed {len(restaurants)} valid restaurants")
    
    # Remove duplicates by name + approximate location
    seen = set()
    unique = []
    for r in restaurants:
        key = (r["name"].lower(), round(r["lat"], 4), round(r["lng"], 4))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    
    print(f"After deduplication: {len(unique)} restaurants")
    
    # Save outputs
    save_restaurants(unique)
    save_csv_for_manual_enrichment(unique)
    
    # Print stats
    print()
    print("=" * 60)
    print("STATISTICS")
    print("=" * 60)
    
    cuisines = {}
    for r in unique:
        c = r["cuisine"]
        cuisines[c] = cuisines.get(c, 0) + 1
    
    print("\nTop cuisines:")
    for cuisine, count in sorted(cuisines.items(), key=lambda x: -x[1])[:15]:
        print(f"  {cuisine}: {count}")
    
    print()
    print("NEXT STEPS:")
    print("1. Open data/osm_restaurants_to_enrich.csv in Excel/Sheets")
    print("2. For each restaurant, search on Google Maps and add:")
    print("   - google_rating (e.g., 4.5)")
    print("   - google_review_count (e.g., 150)")
    print("3. Run the merge script to combine with existing data")

if __name__ == "__main__":
    main()

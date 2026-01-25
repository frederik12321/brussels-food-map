"""
Compare OSM restaurants with our existing dataset to find new ones.
Outputs a list of restaurants that need Google Maps data.
"""

import json
import csv
from math import radians, sin, cos, sqrt, atan2

def haversine(lat1, lng1, lat2, lng2):
    """Calculate distance between two points in meters."""
    R = 6371000  # Earth's radius in meters
    
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

def load_existing_restaurants():
    """Load our current restaurant dataset."""
    with open("data/brussels_restaurants.json", "r") as f:
        return json.load(f)

def load_osm_restaurants():
    """Load OSM restaurants."""
    with open("data/osm_restaurants.json", "r") as f:
        return json.load(f)

def normalize_name(name):
    """Normalize restaurant name for comparison."""
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [" restaurant", " café", " cafe", " bar", " brasserie", " bistro", " kitchen"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    # Remove special chars
    name = "".join(c for c in name if c.isalnum() or c == " ")
    return name

def find_match(osm_restaurant, existing_restaurants, threshold_meters=100):
    """Check if OSM restaurant matches any existing restaurant."""
    osm_name = normalize_name(osm_restaurant["name"])
    osm_lat = osm_restaurant["lat"]
    osm_lng = osm_restaurant["lng"]
    
    for existing in existing_restaurants:
        # Check distance first (faster)
        dist = haversine(osm_lat, osm_lng, existing["lat"], existing["lng"])
        if dist > threshold_meters:
            continue
        
        # Check name similarity
        existing_name = normalize_name(existing["name"])
        
        # Exact match
        if osm_name == existing_name:
            return existing
        
        # One contains the other
        if osm_name in existing_name or existing_name in osm_name:
            return existing
        
        # Very close location (within 30m) - likely same place
        if dist < 30:
            return existing
    
    return None

def main():
    print("Loading datasets...")
    existing = load_existing_restaurants()
    osm = load_osm_restaurants()
    
    print(f"Existing restaurants: {len(existing)}")
    print(f"OSM restaurants: {len(osm)}")
    
    # Find new restaurants (in OSM but not in existing)
    new_restaurants = []
    matched = 0
    
    for osm_r in osm:
        match = find_match(osm_r, existing)
        if match:
            matched += 1
        else:
            new_restaurants.append(osm_r)
    
    print(f"\nMatched with existing: {matched}")
    print(f"New restaurants found: {len(new_restaurants)}")
    
    # Filter out likely non-restaurants
    filtered = []
    skip_keywords = ["hotel", "hostel", "supermarket", "carrefour", "delhaize", "colruyt", 
                     "aldi", "lidl", "proxy", "night shop", "frituur", "friture"]
    
    for r in new_restaurants:
        name_lower = r["name"].lower()
        if any(kw in name_lower for kw in skip_keywords):
            continue
        if r["amenity"] == "fast_food" and r["cuisine"] in ["Sandwich", "Kebab", "Friture"]:
            continue  # Skip generic fast food
        filtered.append(r)
    
    print(f"After filtering: {len(filtered)} new restaurants worth checking")
    
    # Sort by cuisine diversity (prefer interesting cuisines)
    priority_cuisines = ["Congolese", "Ethiopian", "Vietnamese", "Korean", "Lebanese", 
                        "Moroccan", "Turkish", "Portuguese", "Greek", "Spanish"]
    
    def priority_score(r):
        if r["cuisine"] in priority_cuisines:
            return 0
        if r["cuisine"] not in ["Restaurant", "Sandwich", "Kebab", "Coffee_Shop"]:
            return 1
        return 2
    
    filtered.sort(key=priority_score)
    
    # Save to CSV for manual Google Maps lookup
    output_file = "data/new_restaurants_to_add.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["priority", "name", "address", "lat", "lng", "cuisine", 
                     "google_maps_link", "rating", "review_count", "added"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for i, r in enumerate(filtered[:500]):  # Top 500 candidates
            # Generate Google Maps search link
            search_query = f"{r['name']} {r['address']}".replace(" ", "+")
            google_link = f"https://www.google.com/maps/search/{search_query}"
            
            writer.writerow({
                "priority": priority_score(r),
                "name": r["name"],
                "address": r["address"],
                "lat": r["lat"],
                "lng": r["lng"],
                "cuisine": r["cuisine"],
                "google_maps_link": google_link,
                "rating": "",  # Fill manually
                "review_count": "",  # Fill manually
                "added": "",  # Mark 'yes' when added
            })
    
    print(f"\nSaved top 500 candidates to: {output_file}")
    print("\nTO ADD NEW RESTAURANTS:")
    print("1. Open the CSV in Excel/Google Sheets")
    print("2. Click each Google Maps link")
    print("3. Copy the rating and review count")
    print("4. Run the merge script to add them to the database")
    
    # Show sample of interesting finds
    print("\n" + "=" * 60)
    print("SAMPLE NEW RESTAURANTS (high priority cuisines):")
    print("=" * 60)
    
    for r in filtered[:20]:
        if r["cuisine"] in priority_cuisines:
            print(f"  {r['name']} ({r['cuisine']}) - {r['address'][:40]}...")

if __name__ == "__main__":
    main()

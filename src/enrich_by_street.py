#!/usr/bin/env python3
"""
Enrich restaurant data street by street.
Opens Google Maps for each street and lets you add ratings quickly.

Usage: python src/enrich_by_street.py
"""

import json
import webbrowser
import time
from collections import defaultdict

def load_restaurants():
    with open("data/brussels_restaurants.json", "r") as f:
        return json.load(f)

def save_restaurants(restaurants):
    with open("data/brussels_restaurants.json", "w", encoding="utf-8") as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)

def extract_street(address):
    """Extract street name from address."""
    if not address:
        return "Unknown"
    # Take first part before comma
    street = address.split(",")[0].strip()
    # Remove house numbers
    parts = street.split()
    # Keep only words (not numbers)
    street_parts = [p for p in parts if not p.isdigit()]
    return " ".join(street_parts) if street_parts else street

def group_by_street(restaurants):
    """Group restaurants by street."""
    streets = defaultdict(list)
    for r in restaurants:
        street = extract_street(r.get("address", ""))
        streets[street].append(r)
    return streets

def get_missing_data_restaurants(restaurants):
    """Find restaurants missing rating data."""
    missing = []
    for r in restaurants:
        if not r.get("rating") or not r.get("user_ratings_total"):
            missing.append(r)
    return missing

def main():
    print("=" * 60)
    print("ENRICH RESTAURANTS BY STREET")
    print("=" * 60)
    
    restaurants = load_restaurants()
    print(f"Total restaurants: {len(restaurants)}")
    
    # Find restaurants missing data
    missing = get_missing_data_restaurants(restaurants)
    print(f"Restaurants missing rating data: {len(missing)}")
    
    if not missing:
        print("\nAll restaurants have rating data!")
        return
    
    # Group by street
    streets = group_by_street(missing)
    
    # Sort streets by number of restaurants
    sorted_streets = sorted(streets.items(), key=lambda x: -len(x[1]))
    
    print(f"\nStreets with missing data: {len(sorted_streets)}")
    print("\nTop 20 streets with most restaurants to enrich:")
    for i, (street, rest_list) in enumerate(sorted_streets[:20], 1):
        print(f"  {i}. {street}: {len(rest_list)} restaurants")
    
    print("\n" + "=" * 60)
    choice = input("Enter street number (1-20) or street name, or 'q' to quit: ").strip()
    
    if choice.lower() == 'q':
        return
    
    # Find selected street
    selected_street = None
    selected_restaurants = None
    
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(sorted_streets):
            selected_street, selected_restaurants = sorted_streets[idx]
    else:
        # Search by name
        for street, rest_list in sorted_streets:
            if choice.lower() in street.lower():
                selected_street = street
                selected_restaurants = rest_list
                break
    
    if not selected_street:
        print("Street not found!")
        return
    
    print(f"\n{'=' * 60}")
    print(f"ENRICHING: {selected_street}")
    print(f"{'=' * 60}")
    print(f"Restaurants to enrich: {len(selected_restaurants)}")
    
    # Open Google Maps for the street
    search_query = f"{selected_street} Brussels restaurants".replace(" ", "+")
    maps_url = f"https://www.google.com/maps/search/{search_query}"
    
    print(f"\nOpening Google Maps: {maps_url}")
    webbrowser.open(maps_url)
    
    input("\nPress Enter when Google Maps is loaded...")
    
    # Process each restaurant
    updated = 0
    for i, r in enumerate(selected_restaurants, 1):
        print(f"\n[{i}/{len(selected_restaurants)}] {r['name']}")
        print(f"  Address: {r.get('address', 'N/A')}")
        print(f"  Current: {r.get('rating', 'N/A')} ({r.get('user_ratings_total', 'N/A')} reviews)")
        
        # Quick input
        data = input("  Enter 'rating,reviews' (e.g., 4.5,150) or Enter to skip: ").strip()
        
        if not data:
            continue
        
        try:
            parts = data.split(",")
            rating = float(parts[0].strip())
            reviews = int(parts[1].strip())
            
            # Update in main list
            for orig_r in restaurants:
                if orig_r.get("name") == r["name"] and orig_r.get("lat") == r.get("lat"):
                    orig_r["rating"] = rating
                    orig_r["user_ratings_total"] = reviews
                    updated += 1
                    print(f"  Updated: {rating} stars ({reviews} reviews)")
                    break
        except (ValueError, IndexError):
            print("  Invalid format, skipping")
    
    if updated > 0:
        save_restaurants(restaurants)
        print(f"\n{'=' * 60}")
        print(f"Saved {updated} updates to database!")
        print("Run the pipeline to update rankings:")
        print("  python src/features.py && python src/model.py && python src/brussels_reranking.py")

if __name__ == "__main__":
    main()

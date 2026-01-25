#!/usr/bin/env python3
"""
Add all restaurants from a specific street in Brussels.
Searches Google Maps for the street and lets you add restaurants one by one.

Usage: python src/add_street.py "Rue de Flandre"
"""

import json
import webbrowser
import sys

def load_restaurants():
    with open("data/brussels_restaurants.json", "r") as f:
        return json.load(f)

def save_restaurants(restaurants):
    with open("data/brussels_restaurants.json", "w", encoding="utf-8") as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)

def check_exists(name, lat, lng, restaurants):
    """Check if restaurant already exists."""
    name_lower = name.lower().strip()
    for r in restaurants:
        if r["name"].lower().strip() == name_lower:
            if abs(r["lat"] - lat) < 0.002 and abs(r["lng"] - lng) < 0.002:
                return True
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python src/add_street.py 'Street Name'")
        print("Example: python src/add_street.py 'Rue de Flandre'")
        return
    
    street_name = " ".join(sys.argv[1:])
    
    print("=" * 60)
    print(f"ADD RESTAURANTS FROM: {street_name}")
    print("=" * 60)
    
    restaurants = load_restaurants()
    print(f"Current database: {len(restaurants)} restaurants")
    
    # Open Google Maps
    search_query = f"restaurants {street_name} Brussels".replace(" ", "+")
    maps_url = f"https://www.google.com/maps/search/{search_query}"
    
    print(f"\nOpening Google Maps: {maps_url}")
    webbrowser.open(maps_url)
    
    print("\nInstructions:")
    print("1. In Google Maps, look at the restaurants on this street")
    print("2. For each one you want to add, copy the details below")
    print("3. Type 'done' when finished")
    print()
    
    added = 0
    
    while True:
        print("-" * 40)
        name = input("Restaurant name (or 'done'): ").strip()
        
        if name.lower() == 'done':
            break
        
        if not name:
            continue
        
        # Get coordinates
        print("Right-click on restaurant in Google Maps -> 'What's here?' for coordinates")
        coords = input("Coordinates (lat,lng e.g. 50.8467,4.3525): ").strip()
        
        try:
            lat, lng = map(float, coords.split(","))
        except:
            print("Invalid coordinates, skipping")
            continue
        
        # Check duplicate
        if check_exists(name, lat, lng, restaurants):
            print(f"'{name}' already exists in database, skipping")
            continue
        
        # Get rating info
        rating_input = input("Rating (e.g. 4.5): ").strip()
        reviews_input = input("Number of reviews: ").strip()
        
        try:
            rating = float(rating_input)
            reviews = int(reviews_input)
        except:
            print("Invalid rating/reviews, skipping")
            continue
        
        # Get cuisine
        cuisine = input("Cuisine (e.g. Belgian, Italian): ").strip() or "Restaurant"
        
        # Build address
        address = f"{street_name}, Brussels, Belgium"
        
        # Create restaurant
        new_restaurant = {
            "name": name,
            "address": address,
            "lat": lat,
            "lng": lng,
            "rating": rating,
            "review_count": reviews,
            "primary_type": "restaurant",
            "primary_type_display": "Restaurant",
            "types": ["restaurant"],
            "opening_hours": [],
            "website": "",
            "google_maps_url": f"https://www.google.com/maps/search/{name.replace(' ', '+')}+Brussels",
            "cuisine": cuisine,
        }
        
        restaurants.append(new_restaurant)
        added += 1
        print(f"+ Added: {name} ({rating}* - {reviews} reviews)")
    
    if added > 0:
        save_restaurants(restaurants)
        print(f"\n{'=' * 60}")
        print(f"Added {added} new restaurants!")
        print(f"Total now: {len(restaurants)} restaurants")
        print("\nTo update rankings, run:")
        print("  python src/features.py")
        print("  python src/model.py")
        print("  python src/brussels_reranking.py")
    else:
        print("\nNo restaurants added.")

if __name__ == "__main__":
    main()

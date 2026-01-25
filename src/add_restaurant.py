#!/usr/bin/env python3
"""
Manually add a single restaurant to the dataset.
Interactive script - prompts for Google Maps data.

Usage: python src/add_restaurant.py
"""

import json
import sys

def load_restaurants():
    with open("data/brussels_restaurants.json", "r") as f:
        return json.load(f)

def save_restaurants(restaurants):
    with open("data/brussels_restaurants.json", "w", encoding="utf-8") as f:
        json.dump(restaurants, f, indent=2, ensure_ascii=False)

def check_duplicate(name, lat, lng, existing):
    """Check if restaurant already exists."""
    name_lower = name.lower().strip()
    for r in existing:
        if r["name"].lower().strip() == name_lower:
            if abs(r["lat"] - lat) < 0.001 and abs(r["lng"] - lng) < 0.001:
                return r
    return None

def main():
    print("=" * 50)
    print("ADD NEW RESTAURANT TO BRUSSELS FOOD MAP")
    print("=" * 50)
    print()
    print("Get this info from Google Maps:")
    print("1. Search the restaurant on Google Maps")
    print("2. Copy the details below")
    print()
    
    restaurants = load_restaurants()
    
    # Get input
    name = input("Restaurant name: ").strip()
    if not name:
        print("Cancelled.")
        return
    
    address = input("Full address: ").strip()
    
    # Coordinates from Google Maps URL or right-click
    print("\nGet coordinates: Right-click on Google Maps → 'What's here?'")
    lat_str = input("Latitude (e.g., 50.8467): ").strip()
    lng_str = input("Longitude (e.g., 4.3525): ").strip()
    
    try:
        lat = float(lat_str)
        lng = float(lng_str)
    except ValueError:
        print("Invalid coordinates!")
        return
    
    # Check duplicate
    dup = check_duplicate(name, lat, lng, restaurants)
    if dup:
        print(f"\n⚠️  This restaurant already exists in the database!")
        print(f"   Name: {dup['name']}")
        print(f"   Rating: {dup.get('rating', 'N/A')}")
        return
    
    rating_str = input("Google rating (e.g., 4.5): ").strip()
    reviews_str = input("Number of reviews (e.g., 150): ").strip()
    
    try:
        rating = float(rating_str)
        reviews = int(reviews_str)
    except ValueError:
        print("Invalid rating/reviews!")
        return
    
    print("\nCuisine types: Italian, French, Belgian, Japanese, Chinese,")
    print("Thai, Indian, Turkish, Moroccan, Lebanese, Greek, Spanish,")
    print("Mexican, Vietnamese, Korean, African, Ethiopian, Congolese,")
    print("Portuguese, Seafood, or other...")
    cuisine = input("Cuisine type: ").strip() or "Restaurant"
    
    price_str = input("Price level (1=€, 2=€€, 3=€€€, 4=€€€€, or leave empty): ").strip()
    price_level = int(price_str) if price_str else None
    
    website = input("Website URL (optional): ").strip()
    
    # Create restaurant entry
    new_restaurant = {
        "name": name,
        "address": address,
        "lat": lat,
        "lng": lng,
        "rating": rating,
        "user_ratings_total": reviews,
        "cuisine": cuisine,
        "price_level": price_level,
        "types": ["restaurant"],
        "opening_hours": [],
        "website": website,
        "google_maps_url": f"https://www.google.com/maps/search/{name.replace(' ', '+')}+{address.replace(' ', '+')}",
    }
    
    # Confirm
    print("\n" + "=" * 50)
    print("CONFIRM NEW RESTAURANT:")
    print("=" * 50)
    print(f"Name: {name}")
    print(f"Address: {address}")
    print(f"Location: {lat}, {lng}")
    print(f"Rating: {rating}★ ({reviews} reviews)")
    print(f"Cuisine: {cuisine}")
    print(f"Price: {'€' * price_level if price_level else 'N/A'}")
    
    confirm = input("\nAdd this restaurant? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return
    
    # Add and save
    restaurants.append(new_restaurant)
    save_restaurants(restaurants)
    
    print(f"\n✅ Added {name} to the dataset!")
    print(f"   Total restaurants: {len(restaurants)}")
    print("\nTo update the rankings, run:")
    print("  python src/features.py")
    print("  python src/model.py")
    print("  python src/brussels_reranking.py")

if __name__ == "__main__":
    main()

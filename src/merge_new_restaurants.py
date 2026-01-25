"""
Merge manually enriched new restaurants into the main dataset.

Usage:
1. Fill in data/new_restaurants_to_add.csv with Google ratings
2. Run this script to add them to the pipeline
"""

import json
import csv
import sys

def load_enriched_csv(filepath="data/new_restaurants_to_add.csv"):
    """Load CSV with manually added Google data."""
    restaurants = []
    
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Only include rows with rating data
            if row.get("rating") and row.get("review_count"):
                try:
                    rating = float(row["rating"])
                    reviews = int(row["review_count"])
                    
                    if rating < 1 or rating > 5:
                        continue
                    if reviews < 5:  # Skip places with very few reviews
                        continue
                    
                    restaurants.append({
                        "name": row["name"],
                        "address": row["address"],
                        "lat": float(row["lat"]),
                        "lng": float(row["lng"]),
                        "rating": rating,
                        "user_ratings_total": reviews,
                        "cuisine": row["cuisine"],
                        "types": ["restaurant"],
                        "opening_hours": [],
                        "website": "",
                        "google_maps_url": row.get("google_maps_link", ""),
                    })
                except (ValueError, KeyError) as e:
                    print(f"Skipping {row.get('name')}: {e}")
    
    return restaurants

def load_existing():
    """Load existing restaurants."""
    with open("data/brussels_restaurants.json", "r") as f:
        return json.load(f)

def find_duplicate(new_r, existing):
    """Check if restaurant already exists."""
    for ex in existing:
        # Same name and close location
        if new_r["name"].lower() == ex["name"].lower():
            lat_diff = abs(new_r["lat"] - ex["lat"])
            lng_diff = abs(new_r["lng"] - ex["lng"])
            if lat_diff < 0.001 and lng_diff < 0.001:
                return True
    return False

def main():
    print("Loading enriched CSV...")
    new_restaurants = load_enriched_csv()
    print(f"Found {len(new_restaurants)} restaurants with complete data")
    
    if not new_restaurants:
        print("\nNo restaurants to add. Please fill in the CSV first:")
        print("  data/new_restaurants_to_add.csv")
        print("\nAdd rating and review_count for restaurants you want to include.")
        return
    
    print("\nLoading existing dataset...")
    existing = load_existing()
    print(f"Existing restaurants: {len(existing)}")
    
    # Filter out duplicates
    added = []
    for new_r in new_restaurants:
        if not find_duplicate(new_r, existing):
            added.append(new_r)
            existing.append(new_r)
    
    print(f"New restaurants to add: {len(added)}")
    
    if added:
        # Save updated dataset
        with open("data/brussels_restaurants.json", "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        
        print(f"\nAdded {len(added)} new restaurants:")
        for r in added[:10]:
            print(f"  + {r['name']} ({r['cuisine']}) - {r['rating']}★ ({r['user_ratings_total']} reviews)")
        if len(added) > 10:
            print(f"  ... and {len(added) - 10} more")
        
        print("\nNEXT STEPS:")
        print("1. Run: python src/features.py")
        print("2. Run: python src/model.py")
        print("3. Run: python src/brussels_reranking.py")
        print("4. Commit and push to deploy")
    else:
        print("No new restaurants to add (all were duplicates)")

if __name__ == "__main__":
    main()

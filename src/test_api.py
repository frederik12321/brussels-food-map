"""Quick test to verify API key works."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
BASE_URL = "https://places.googleapis.com/v1/places:searchNearby"

# Test with Brussels center
headers = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": API_KEY,
    "X-Goog-FieldMask": "places.displayName,places.rating,places.userRatingCount"
}

body = {
    "includedTypes": ["restaurant"],
    "maxResultCount": 5,
    "locationRestriction": {
        "circle": {
            "center": {"latitude": 50.8503, "longitude": 4.3517},
            "radius": 500
        }
    }
}

print(f"Testing API key: {API_KEY[:10]}...{API_KEY[-4:]}")
print("Making test request to Brussels center...\n")

response = requests.post(BASE_URL, headers=headers, json=body)

if response.status_code == 200:
    data = response.json()
    places = data.get("places", [])
    print(f"✓ Success! Found {len(places)} restaurants:\n")
    for p in places:
        name = p.get("displayName", {}).get("text", "Unknown")
        rating = p.get("rating", "N/A")
        reviews = p.get("userRatingCount", 0)
        print(f"  - {name}: {rating}★ ({reviews} reviews)")
    print("\n✓ API key is working! Ready to run full scrape.")
else:
    print(f"✗ Error {response.status_code}: {response.text}")

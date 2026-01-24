"""
Partial scraper to fetch opening hours for existing restaurants.

This script fetches only the regularOpeningHours field for restaurants
that already exist in the data, minimizing API costs.
"""

import os
import json
import time
import requests
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
DETAILS_URL = "https://places.googleapis.com/v1/places"


def get_opening_hours(place_id):
    """Fetch only opening hours for a place."""
    headers = {
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "id,regularOpeningHours"
    }

    url = f"{DETAILS_URL}/{place_id}"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return None

    return response.json()


def parse_opening_hours(data):
    """Parse opening hours data into closing times and days open."""
    opening_hours = data.get("regularOpeningHours", {})

    closing_times = {}
    days_open = set()
    weekday_descriptions = opening_hours.get("weekdayDescriptions", [])
    periods = opening_hours.get("periods", [])

    # Parse periods to get closing times and days open
    for period in periods:
        open_info = period.get("open", {})
        if open_info:
            day = open_info.get("day")
            if day is not None:
                days_open.add(day)

        close_info = period.get("close", {})
        if close_info:
            day = close_info.get("day", 0)
            hour = close_info.get("hour", 0)
            minute = close_info.get("minute", 0)
            closing_times[day] = f"{hour:02d}:{minute:02d}"

    return {
        "opening_hours": weekday_descriptions,
        "closing_times": closing_times,
        "days_open": sorted(list(days_open))
    }


def update_restaurants_with_hours(
    input_file="../data/brussels_restaurants.json",
    output_file="../data/brussels_restaurants.json",
    batch_size=100,
    delay=0.05
):
    """Update existing restaurant data with opening hours."""
    if not API_KEY:
        print("Error: GOOGLE_MAPS_API_KEY not set in environment")
        return

    # Load existing data
    with open(input_file, "r", encoding="utf-8") as f:
        restaurants = json.load(f)

    print(f"Loaded {len(restaurants)} restaurants")

    # Count how many already have hours
    has_hours = sum(1 for r in restaurants if r.get("closing_times"))
    print(f"Already have hours: {has_hours}")

    # Filter to only those missing hours
    to_update = [r for r in restaurants if not r.get("closing_times")]
    print(f"Need to fetch hours for: {len(to_update)} restaurants")

    if not to_update:
        print("All restaurants already have opening hours!")
        return

    # Create a lookup dict for quick updates
    restaurant_lookup = {r["id"]: r for r in restaurants}

    # Fetch hours in batches
    success_count = 0
    error_count = 0

    for restaurant in tqdm(to_update, desc="Fetching opening hours"):
        place_id = restaurant["id"]

        try:
            data = get_opening_hours(place_id)

            if data:
                hours_data = parse_opening_hours(data)
                # Update the restaurant in our lookup
                restaurant_lookup[place_id].update(hours_data)
                success_count += 1
            else:
                error_count += 1

        except Exception as e:
            print(f"\nError fetching {place_id}: {e}")
            error_count += 1

        time.sleep(delay)

        # Save progress every batch_size restaurants
        if (success_count + error_count) % batch_size == 0:
            restaurants = list(restaurant_lookup.values())
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(restaurants, f, ensure_ascii=False, indent=2)
            print(f"\nSaved progress: {success_count} updated, {error_count} errors")

    # Final save
    restaurants = list(restaurant_lookup.values())
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(restaurants, f, ensure_ascii=False, indent=2)

    print(f"\nComplete!")
    print(f"  Successfully updated: {success_count}")
    print(f"  Errors: {error_count}")
    print(f"Saved to {output_file}")

    # Show sample of updated data
    with_hours = [r for r in restaurants if r.get("closing_times")]
    if with_hours:
        sample = with_hours[0]
        print(f"\nSample - {sample['name']}:")
        print(f"  Opening hours: {sample.get('opening_hours', [])[:2]}...")
        print(f"  Closing times: {sample.get('closing_times', {})}")
        print(f"  Days open: {sample.get('days_open', [])}")


if __name__ == "__main__":
    update_restaurants_with_hours()

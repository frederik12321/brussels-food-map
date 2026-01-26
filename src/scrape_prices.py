"""
Brussels Restaurant Price Manager

Manages restaurant prices from TheFork and enriches existing restaurant data.
Since TheFork uses bot detection, this script works with manually collected
price data stored in thefork_prices.json.

Usage:
    # Enrich restaurants with existing price data:
    python src/scrape_prices.py

    # Add a new price entry:
    python src/scrape_prices.py --add "Restaurant Name" 25

    # Search for restaurants to add prices:
    python src/scrape_prices.py --search "pizza"
"""

import json
import re
import sys
import argparse
from pathlib import Path
from difflib import SequenceMatcher

# Constants
DATA_DIR = Path(__file__).parent.parent / "data"
BRUSSELS_RESTAURANTS_FILE = DATA_DIR / "brussels_restaurants.json"
PRICES_FILE = DATA_DIR / "thefork_prices.json"
ENRICHED_OUTPUT_FILE = DATA_DIR / "brussels_restaurants_with_prices.json"


def load_existing_restaurants():
    """Load existing Brussels restaurant data."""
    if BRUSSELS_RESTAURANTS_FILE.exists():
        with open(BRUSSELS_RESTAURANTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_prices():
    """Load existing price data."""
    if PRICES_FILE.exists():
        with open(PRICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_prices(prices):
    """Save price data."""
    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(prices)} price entries to {PRICES_FILE}")


def price_to_category(price_euro):
    """Convert euro price to price category."""
    if price_euro is None:
        return None

    if price_euro < 15:
        return {"level": 1, "symbol": "$", "label": "Cheap"}
    elif price_euro < 30:
        return {"level": 2, "symbol": "$$", "label": "Mid-range"}
    elif price_euro < 60:
        return {"level": 3, "symbol": "$$$", "label": "Upscale"}
    else:
        return {"level": 4, "symbol": "$$$$", "label": "Fine Dining"}


def normalize_name(name):
    """Normalize restaurant name for matching."""
    if not name:
        return ""

    name = name.lower()

    # Remove common prefixes/suffixes
    remove_words = ['restaurant', 'brasserie', 'cafe', 'café', 'bistro', 'bar', 'the', 'le', 'la', "l'", 'de', 'du']
    for word in remove_words:
        name = re.sub(rf'\b{word}\b', '', name)

    # Remove special characters and extra spaces
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def normalize_address(address):
    """Normalize address for matching."""
    if not address:
        return ""

    address = address.lower()

    # Standardize Belgian address formats
    replacements = {
        'chaussée': 'chau',
        'chaussee': 'chau',
        'chau.': 'chau',
        'avenue': 'av',
        'av.': 'av',
        'boulevard': 'bd',
        'bd.': 'bd',
        'rue': 'r',
        'straat': 'str',
        'laan': 'ln',
        'place': 'pl',
        'plein': 'pl',
        'saint-': 'st-',
        'sint-': 'st-',
        'belgium': '',
        'belgique': '',
        'belgië': '',
    }

    for old, new in replacements.items():
        address = address.replace(old, new)

    # Remove postal codes
    address = re.sub(r'\b\d{4}\b', '', address)

    # Remove special characters
    address = re.sub(r'[^\w\s]', ' ', address)
    address = re.sub(r'\s+', ' ', address).strip()

    return address


def calculate_match_score(rest1, rest2):
    """Calculate how well two restaurants match (0-1 score)."""
    # Name similarity (weight: 0.7)
    name1 = normalize_name(rest1.get('name', ''))
    name2 = normalize_name(rest2.get('name', ''))
    name_score = SequenceMatcher(None, name1, name2).ratio()

    # Address similarity (weight: 0.3)
    addr1 = normalize_address(rest1.get('address', ''))
    addr2 = normalize_address(rest2.get('address', ''))
    addr_score = SequenceMatcher(None, addr1, addr2).ratio()

    # Weighted average
    total_score = (name_score * 0.7) + (addr_score * 0.3)

    # Bonus for exact name match (after normalization)
    if name1 and name1 == name2:
        total_score = min(1.0, total_score + 0.2)

    return total_score


def match_restaurants(existing_restaurants, price_data, threshold=0.65):
    """Match price data with existing restaurant data."""
    matches = []
    unmatched = []

    print(f"Matching {len(price_data)} price entries with {len(existing_restaurants)} restaurants...")

    for price_entry in price_data:
        if not price_entry.get('name'):
            continue

        best_match = None
        best_score = 0

        for existing in existing_restaurants:
            score = calculate_match_score(price_entry, existing)

            if score > best_score and score >= threshold:
                best_score = score
                best_match = existing

        if best_match:
            matches.append({
                'existing': best_match,
                'price_data': price_entry,
                'match_score': best_score
            })
        else:
            unmatched.append(price_entry)

    print(f"Matched: {len(matches)}, Unmatched: {len(unmatched)}")
    return matches, unmatched


def enrich_restaurants_with_prices(existing_restaurants, matches):
    """Add price data to existing restaurants based on matches."""
    # Create lookup by name for faster matching
    match_lookup = {}
    for match in matches:
        existing_name = match['existing'].get('name', '').lower()
        match_lookup[existing_name] = match

    enriched = []
    prices_added = 0

    for restaurant in existing_restaurants:
        rest_copy = restaurant.copy()
        name_lower = restaurant.get('name', '').lower()

        if name_lower in match_lookup:
            match = match_lookup[name_lower]
            price_data = match['price_data']

            # Add price data
            if price_data.get('average_price'):
                rest_copy['average_price_eur'] = price_data['average_price']
                category = price_to_category(price_data['average_price'])
                if category:
                    rest_copy['price_category'] = category['label']
                    rest_copy['price_symbol'] = category['symbol']
                    # Update price_level if not set
                    if rest_copy.get('price_level') is None:
                        rest_copy['price_level'] = category['level']
                prices_added += 1

            # Add TheFork URL if available
            if price_data.get('thefork_url'):
                rest_copy['thefork_url'] = price_data['thefork_url']

            # Add TheFork rating if available
            if price_data.get('thefork_rating'):
                rest_copy['thefork_rating'] = price_data['thefork_rating']

        enriched.append(rest_copy)

    print(f"Added price data to {prices_added} restaurants")
    return enriched


def save_json(data, filepath):
    """Save data to JSON file."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Saved to {filepath}")


def search_restaurants(query, restaurants):
    """Search for restaurants by name."""
    query_lower = query.lower()
    results = []

    for r in restaurants:
        name = r.get('name', '')
        if query_lower in name.lower():
            results.append(r)

    return results[:20]  # Limit to 20 results


def add_price_entry(name, price, restaurants, prices):
    """Add a new price entry, matching to existing restaurant."""
    # Find matching restaurant
    best_match = None
    best_score = 0

    for r in restaurants:
        score = SequenceMatcher(None, name.lower(), r.get('name', '').lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = r

    if best_match and best_score > 0.6:
        new_entry = {
            'name': best_match['name'],
            'address': best_match.get('address', ''),
            'average_price': price
        }

        # Check if already exists
        existing_names = [p['name'].lower() for p in prices]
        if best_match['name'].lower() not in existing_names:
            prices.append(new_entry)
            print(f"Added: {best_match['name']} - €{price}")
            return True
        else:
            print(f"Already exists: {best_match['name']}")
            return False
    else:
        print(f"No match found for: {name}")
        print(f"Best guess: {best_match['name'] if best_match else 'None'} (score: {best_score:.2f})")
        return False


def main():
    """Main function to manage prices and enrich restaurant data."""
    parser = argparse.ArgumentParser(description='Brussels Restaurant Price Manager')
    parser.add_argument('--add', nargs=2, metavar=('NAME', 'PRICE'),
                        help='Add a price entry: --add "Restaurant Name" 25')
    parser.add_argument('--search', type=str, help='Search restaurants by name')
    parser.add_argument('--stats', action='store_true', help='Show price statistics')
    args = parser.parse_args()

    # Load data
    existing_restaurants = load_existing_restaurants()
    prices = load_prices()

    if args.search:
        # Search mode
        results = search_restaurants(args.search, existing_restaurants)
        print(f"\nFound {len(results)} restaurants matching '{args.search}':\n")
        for r in results:
            price_info = ""
            # Check if already has price
            for p in prices:
                if p['name'].lower() == r['name'].lower():
                    price_info = f" [€{p['average_price']}]"
                    break
            print(f"  - {r['name']}{price_info}")
            print(f"    {r.get('address', 'No address')}")
        return

    if args.add:
        # Add price mode
        name, price = args.add
        try:
            price = int(price)
        except ValueError:
            print("Price must be a number")
            return

        if add_price_entry(name, price, existing_restaurants, prices):
            save_prices(prices)
        return

    if args.stats:
        # Stats mode
        print("\n" + "=" * 60)
        print("PRICE STATISTICS")
        print("=" * 60)

        if prices:
            price_values = [p['average_price'] for p in prices if p.get('average_price')]
            print(f"Total price entries: {len(prices)}")
            print(f"Price range: €{min(price_values)} - €{max(price_values)}")
            print(f"Average price: €{sum(price_values)/len(price_values):.0f}")

            # Price distribution
            cheap = sum(1 for p in price_values if p < 15)
            mid = sum(1 for p in price_values if 15 <= p < 30)
            upscale = sum(1 for p in price_values if 30 <= p < 60)
            fine = sum(1 for p in price_values if p >= 60)

            print(f"\nDistribution:")
            print(f"  $ (Cheap, <€15): {cheap}")
            print(f"  $$ (Mid-range, €15-30): {mid}")
            print(f"  $$$ (Upscale, €30-60): {upscale}")
            print(f"  $$$$ (Fine Dining, €60+): {fine}")
        else:
            print("No price data available")
        return

    # Default: Enrich mode
    print("=" * 60)
    print("Brussels Restaurant Price Enrichment")
    print("=" * 60)

    print(f"\n1. Loaded {len(existing_restaurants)} restaurants")
    print(f"2. Loaded {len(prices)} price entries")

    if not prices:
        print("\nNo price data available. Add prices with:")
        print('  python src/scrape_prices.py --add "Restaurant Name" 25')
        return

    # Match restaurants
    print("\n3. Matching restaurants...")
    matches, unmatched = match_restaurants(existing_restaurants, prices)

    # Enrich with prices
    print("\n4. Enriching restaurant data with prices...")
    enriched = enrich_restaurants_with_prices(existing_restaurants, matches)

    # Save enriched data
    save_json(enriched, ENRICHED_OUTPUT_FILE)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Price entries: {len(prices)}")
    print(f"Restaurants matched: {len(matches)}")
    print(f"Restaurants with prices: {sum(1 for r in enriched if r.get('average_price_eur'))}")

    # Show matches
    if matches:
        print("\nMatches:")
        for match in matches:
            existing_name = match['existing'].get('name', 'Unknown')
            price = match['price_data'].get('average_price', 'N/A')
            score = match['match_score']
            print(f"  - {existing_name}: €{price} (score: {score:.2f})")

    if unmatched:
        print("\nUnmatched price entries:")
        for u in unmatched:
            print(f"  - {u.get('name', 'Unknown')}")

    print("\nDone!")


if __name__ == "__main__":
    main()

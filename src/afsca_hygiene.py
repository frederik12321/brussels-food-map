"""
AFSCA Hygiene Data Integration

Matches AFSCA (Belgian Food Safety Agency) Smiley certification data
with restaurant database. A "Smiley" indicates the establishment has
a certified self-checking hygiene system - the highest AFSCA rating.

Data source: https://favv-afsca.be/nl/open-data
"""

import os
import csv
import json
from difflib import SequenceMatcher
from collections import defaultdict

# Brussels postcodes (19 communes)
BRUSSELS_POSTCODES = {
    "1000", "1020", "1030", "1040", "1050", "1060", "1070", "1080",
    "1081", "1082", "1083", "1090", "1120", "1130", "1140", "1150",
    "1160", "1170", "1180", "1190", "1200", "1210"
}

# Cache for loaded data
_afsca_cache = None


def load_afsca_smiley_data():
    """
    Load AFSCA Smiley certification data from CSV.
    Returns dict: {normalized_name: smiley_info}
    """
    global _afsca_cache
    if _afsca_cache is not None:
        return _afsca_cache

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    csv_path = os.path.join(data_dir, "afsca_smiley_raw.csv")

    if not os.path.exists(csv_path):
        print(f"Warning: AFSCA data not found at {csv_path}")
        _afsca_cache = {}
        return _afsca_cache

    smiley_data = {}
    brussels_entries = []

    with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
        # CSV uses semicolon separator
        reader = csv.reader(f, delimiter=';')
        header = next(reader)  # Skip header

        for row in reader:
            if len(row) < 6:
                continue

            unique_id = row[0].strip('"')
            name = row[1].strip('"')
            street = row[2].strip('"')
            house_nr = row[3].strip('"')
            postcode = row[4].strip('"')
            municipality = row[5].strip('"')
            smiley_code = row[6].strip('"') if len(row) > 6 else ""
            valid_until = row[7].strip('"') if len(row) > 7 else ""

            # Only keep Brussels entries
            if postcode not in BRUSSELS_POSTCODES:
                continue

            entry = {
                'id': unique_id,
                'name': name,
                'street': street,
                'house_nr': house_nr,
                'postcode': postcode,
                'municipality': municipality,
                'smiley_code': smiley_code,
                'valid_until': valid_until,
                'has_smiley': True,  # All entries in smiley list have certification
            }

            brussels_entries.append(entry)

            # Index by normalized name for matching
            normalized = normalize_name(name)
            if normalized:
                smiley_data[normalized] = entry

    # Also create address-based index for better matching
    address_index = defaultdict(list)
    for entry in brussels_entries:
        addr_key = f"{entry['postcode']}_{normalize_street(entry['street'])}"
        address_index[addr_key].append(entry)

    _afsca_cache = {
        'by_name': smiley_data,
        'by_address': dict(address_index),
        'all_entries': brussels_entries,
    }

    return _afsca_cache


def normalize_name(name):
    """Normalize restaurant name for matching."""
    if not name:
        return ""

    # Lowercase and strip
    name = name.lower().strip()

    # Remove common suffixes/prefixes that vary
    remove_words = [
        'bvba', 'sprl', 'sa', 'nv', 'bv', 'srl',  # Company types
        'restaurant', 'resto', 'brasserie', 'cafe', 'café',
        'bistro', 'taverne', 'snack', 'frituur', 'friture',
    ]

    for word in remove_words:
        name = name.replace(f' {word}', '').replace(f'{word} ', '')

    # Remove punctuation
    import re
    name = re.sub(r'[^\w\s]', '', name)

    # Collapse whitespace
    name = ' '.join(name.split())

    return name


def normalize_street(street):
    """Normalize street name for matching."""
    if not street:
        return ""

    street = street.lower().strip()

    # Common street type abbreviations
    replacements = [
        ('rue ', 'r '), ('straat', 'str'), ('avenue ', 'av '),
        ('boulevard ', 'bd '), ('laan', 'ln'), ('place ', 'pl '),
        ('plein', 'pl'), ('chaussée ', 'ch '), ('steenweg', 'stw'),
    ]

    for old, new in replacements:
        street = street.replace(old, new)

    import re
    street = re.sub(r'[^\w\s]', '', street)
    return ' '.join(street.split())


def similarity_score(name1, name2):
    """Calculate similarity between two names (0-1)."""
    return SequenceMatcher(None, name1, name2).ratio()


def extract_postcode(address):
    """Extract Belgian postcode from address string."""
    if not address:
        return None
    import re
    match = re.search(r'\b(1\d{3})\b', address)
    return match.group(1) if match else None


def extract_street_name(address):
    """
    Extract just the street name from an address string.
    Examples:
        "Chau. de Waterloo 515, 1050 Bruxelles" → "Chau. de Waterloo"
        "Rue des Sablons 11, 1000 Bruxelles" → "Rue des Sablons"
    """
    if not address:
        return ""

    import re

    # Remove everything after the postcode
    address = re.sub(r'\b1\d{3}\b.*$', '', address)

    # Remove house number (digits at end, possibly with letters like 11A)
    address = re.sub(r'\s+\d+[A-Za-z]?\s*,?\s*$', '', address)
    address = re.sub(r',\s*$', '', address)

    return address.strip()


def match_restaurant(restaurant_name, restaurant_address=None, restaurant_postcode=None):
    """
    Try to match a restaurant with AFSCA Smiley data.

    IMPORTANT: AFSCA Smiley certification is per ESTABLISHMENT, not per company.
    Each location of a chain must be individually certified.
    We require address/postcode verification to avoid false positives for chains.

    Returns: (has_smiley: bool, confidence: float, match_info: dict or None)
    """
    data = load_afsca_smiley_data()

    if not data or not data.get('by_name'):
        return False, 0, None

    normalized = normalize_name(restaurant_name)

    # Extract postcode from address if not provided
    if not restaurant_postcode and restaurant_address:
        restaurant_postcode = extract_postcode(restaurant_address)

    # Check how many AFSCA entries exist with this name (fuzzy match)
    # If multiple exist, it's likely a chain and we need address verification
    # Use fuzzy matching because AFSCA may use variations like "Pain Quotidien Ixelles"
    matching_entries = [
        entry for entry in data.get('all_entries', [])
        if similarity_score(normalize_name(entry['name']), normalized) >= 0.7
        or normalized in normalize_name(entry['name'])
        or normalize_name(entry['name']) in normalized
    ]

    is_chain = len(matching_entries) > 1

    if is_chain:
        # For chains: require BOTH postcode AND street match to identify specific location
        # Multiple locations can exist in the same postcode (e.g., Le Pain Quotidien has
        # multiple locations in 1000 Bruxelles and 1050 Ixelles)
        if restaurant_postcode and restaurant_address:
            # Extract just the street name (without house number and city)
            restaurant_street = normalize_street(extract_street_name(restaurant_address))

            # First: try exact postcode + street match
            for entry in matching_entries:
                if entry['postcode'] == restaurant_postcode:
                    afsca_street = normalize_street(entry['street'])
                    # Check if streets match (fuzzy to handle abbreviations)
                    street_score = similarity_score(restaurant_street, afsca_street)
                    if street_score >= 0.6:
                        return True, 1.0, entry

            # No match found - this specific location is not certified
            return False, 0, None
        else:
            # No postcode/address available - can't verify which location
            # Don't assume all locations are certified
            return False, 0, None

    # For non-chains: exact name match is sufficient
    if normalized in data['by_name']:
        entry = data['by_name'][normalized]
        # Still boost confidence if postcode also matches
        confidence = 1.0 if (not restaurant_postcode or entry['postcode'] == restaurant_postcode) else 0.9
        return True, confidence, entry

    # Try fuzzy name matching (for typos, slight variations)
    best_match = None
    best_score = 0

    for smiley_name, smiley_info in data['by_name'].items():
        score = similarity_score(normalized, smiley_name)

        # Boost score if postcode matches
        if restaurant_postcode and smiley_info['postcode'] == restaurant_postcode:
            score += 0.15

        if score > best_score:
            best_score = score
            best_match = smiley_info

    # Require high confidence for fuzzy matches
    if best_score >= 0.85:  # Increased threshold for safety
        return True, best_score, best_match

    # Try address-based matching if we have address info
    if restaurant_postcode and restaurant_address:
        addr_key = f"{restaurant_postcode}_{normalize_street(restaurant_address)}"
        if addr_key in data['by_address']:
            # Found entries at same address - check if names are similar
            for entry in data['by_address'][addr_key]:
                name_score = similarity_score(normalized, normalize_name(entry['name']))
                if name_score >= 0.5:  # Lower threshold since address matches
                    return True, 0.9, entry

    return False, 0, None


def get_afsca_score(restaurant_name, restaurant_address=None, restaurant_postcode=None):
    """
    Get AFSCA hygiene score for a restaurant.

    Returns:
        1.0 if has certified Smiley
        0.0 if no match found (unknown status)

    Note: We can only identify places WITH certification.
    No match doesn't mean bad hygiene - just no public certification.
    """
    has_smiley, confidence, _ = match_restaurant(
        restaurant_name, restaurant_address, restaurant_postcode
    )

    if has_smiley and confidence >= 0.80:
        return 1.0

    return 0.0  # Unknown (not found in Smiley list)


def analyze_coverage(restaurants_df):
    """
    Analyze how many restaurants in our database match AFSCA data.
    """
    data = load_afsca_smiley_data()

    matches = []
    no_matches = []

    for _, row in restaurants_df.iterrows():
        name = row.get('name', '')
        address = row.get('address', '')

        # Extract postcode from address if available
        postcode = None
        if address:
            import re
            match = re.search(r'\b(1\d{3})\b', address)
            if match:
                postcode = match.group(1)

        has_smiley, confidence, match_info = match_restaurant(name, address, postcode)

        if has_smiley:
            matches.append({
                'restaurant': name,
                'afsca_name': match_info['name'] if match_info else None,
                'confidence': confidence,
            })
        else:
            no_matches.append(name)

    return {
        'total_restaurants': len(restaurants_df),
        'matches': len(matches),
        'match_rate': len(matches) / len(restaurants_df) if len(restaurants_df) > 0 else 0,
        'matched_restaurants': matches,
        'afsca_entries': len(data.get('all_entries', [])),
    }


if __name__ == "__main__":
    # Test the module
    data = load_afsca_smiley_data()
    print(f"Loaded {len(data.get('all_entries', []))} AFSCA Smiley entries for Brussels")

    # Print sample entries
    print("\nSample entries:")
    for entry in data.get('all_entries', [])[:10]:
        print(f"  - {entry['name']} ({entry['postcode']} {entry['municipality']})")

    # Test some matches
    test_names = [
        "Le Chemin des Vignes",
        "STEVE ICE CREAM",
        "Panos",
        "Comme Chez Soi",  # Likely won't match - too fancy for Smiley list
    ]

    print("\nTest matches:")
    for name in test_names:
        score = get_afsca_score(name)
        has_smiley, confidence, info = match_restaurant(name)
        status = "✓ SMILEY" if score > 0 else "? Unknown"
        matched = f"→ {info['name']}" if info else ""
        print(f"  {name}: {status} (conf: {confidence:.2f}) {matched}")

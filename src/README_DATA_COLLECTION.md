# Data Collection Without Google Maps API

Since we no longer have access to the Google Maps API, here are the methods to add new restaurants.

## Method 1: Add Single Restaurant (Recommended)

For adding individual restaurants you discover:

```bash
python src/add_restaurant.py
```

The script will prompt you for:
- Restaurant name
- Address
- Coordinates (from Google Maps right-click → "What's here?")
- Rating and review count (from Google Maps)
- Cuisine type
- Price level

## Method 2: Bulk Import from OpenStreetMap

To find potentially missing restaurants:

```bash
# 1. Fetch all Brussels restaurants from OpenStreetMap
python src/collect_osm_restaurants.py

# 2. Compare with existing data to find new ones
python src/find_new_restaurants.py
```

This creates `data/new_restaurants_to_add.csv` with Google Maps links.
Open the CSV, visit each link, and add ratings manually.

## Method 3: CSV Bulk Import

1. Create a CSV file with columns:
   - name, address, lat, lng, rating, review_count, cuisine

2. Run the merge script:
```bash
python src/merge_new_restaurants.py
```

## After Adding Restaurants

Re-run the pipeline to update rankings:

```bash
python src/features.py
python src/model.py  
python src/brussels_reranking.py
```

Then commit and push:
```bash
git add data/
git commit -m "Add new restaurants"
git push
```

## Data Sources

1. **OpenStreetMap** - Free, no API key
   - Good coverage of restaurant locations
   - Missing: ratings, review counts
   
2. **Google Maps (manual)** - For ratings only
   - Search restaurant name
   - Copy rating and review count
   - Right-click for coordinates

3. **Michelin Guide** - For guide recognition
   - Check https://guide.michelin.com/be/en/brussels-capital-region/restaurants

4. **Gault&Millau** - For guide recognition
   - Check https://be.gaultmillau.com/

## Notes

- OSM has ~3300 restaurants in Brussels area
- Our dataset has ~4700 (includes more detailed Google data)
- ~2500 restaurants match between both sources
- ~750 OSM restaurants might be missing from our data (but many are fast food, fritures, etc.)

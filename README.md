# Brussels Food Map - Hidden Gems

Discover algorithmically undervalued restaurants in Brussels using machine learning.

This project uses Google Maps data and gradient-boosted decision trees to identify restaurants that perform better than expected given their structural characteristics - revealing hidden gems that the algorithm might be undervaluing.

## How It Works

1. **Data Collection**: Scrapes 1000+ restaurants from Google Maps Places API covering the Brussels Capital Region
2. **Feature Engineering**: Extracts features like review counts (log-transformed), cuisine type, chain status, price level, and spatial grid position
3. **ML Prediction**: Trains a HistGradientBoostingRegressor to predict expected ratings
4. **Residual Analysis**: Restaurants with actual ratings higher than predicted are "undervalued"
5. **Spatial Clustering**: Groups neighborhoods using H3 hexagons and K-means clustering

## Setup

### 1. Get a Google Maps API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Places API (New)**
4. Go to Credentials and create an API key
5. (Recommended) Restrict the API key to Places API only

### 2. Configure Environment

```bash
cd brussels-food-map
cp .env.example .env
# Edit .env and add your API key
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Pipeline

```bash
# Step 1: Scrape restaurant data
python src/scraper.py

# Step 2: Train model and generate predictions
cd src && python model.py && cd ..

# Step 3: Start the web dashboard
cd src && python app.py
```

Then open http://localhost:5000 in your browser.

## Project Structure

```
brussels-food-map/
├── data/                          # Data files (generated)
│   ├── brussels_restaurants.json  # Raw scraped data
│   ├── restaurants_with_predictions.csv  # Processed with ML predictions
│   ├── hex_features.csv           # Neighborhood aggregations
│   └── summary.json               # Statistics
├── src/
│   ├── scraper.py                 # Google Maps Places API scraper
│   ├── features.py                # Feature engineering
│   ├── model.py                   # ML model training
│   └── app.py                     # Flask web application
├── templates/
│   └── index.html                 # Dashboard frontend
├── static/                        # Static assets
├── requirements.txt               # Python dependencies
└── .env.example                   # Environment template
```

## Features

- **Interactive Map**: Visualize restaurants colored by undervaluation score
- **Search & Filter**: Filter by cuisine, rating, name search
- **Hidden Gems Mode**: Show only algorithmically undervalued restaurants
- **Neighborhood View**: See H3 hexagonal clusters (Elite, Strong, Everyday, Emerging)
- **Restaurant Cards**: Click to fly to location, view details, link to Google Maps

## API Costs

The scraper stays within Google Maps API free tier ($200/month credit):
- Places Nearby Search: ~$0.032 per request
- Approximately 100-200 API calls to cover Brussels
- Total cost: ~$3-7 one-time scrape

## Credits

Inspired by [Lauren Leek's London Food Dashboard](https://laurenleek.substack.com/p/how-google-maps-quietly-allocates).

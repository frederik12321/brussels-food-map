# Local Food Map 🍴

**Discover hidden culinary gems using machine learning and local context.**

A web application that combines Google Maps data with a city-specific ranking algorithm to surface underrated restaurants that tourists and generic rating systems tend to overlook.

🔗 **Brussels Demo**: [brussels-food-map.up.railway.app](https://brussels-food-map.up.railway.app)

---

## 🌍 Adapt This for Your City

This project is designed to be easily adapted for any city. The core algorithm is city-agnostic—you just need to provide local context data.

### Quick Start for Your City

```bash
# 1. Fork this repo
git clone https://github.com/YOUR_USERNAME/local-food-map.git
cd local-food-map

# 2. Copy the city template
cp config/city_template.py config/your_city_config.py

# 3. Fill in your city's data (see below)
# 4. Run the pipeline
# 5. Deploy!
```

### What You Need to Configure

| Component | Description | Example |
|-----------|-------------|---------|
| **City Center** | Lat/lng coordinates | `(51.5074, -0.1278)` for London |
| **Tourist Epicenter** | Main tourist trap zone | Times Square, Eiffel Tower |
| **Districts** | Neighborhoods with tier classifications | Soho (mixed), Brick Lane (diaspora_hub) |
| **Local Streets** | Streets where locals eat | Not on tourist maps |
| **Chain Patterns** | Regex patterns for chains to penalize | Local fast food chains |
| **Michelin List** | Starred restaurants in your city | From Michelin Guide |
| **Reddit Subreddit** | Local community for endorsements | r/london, r/nyc |

See `config/city_template.py` for a complete template with examples.

---

## How It Works

### The Problem with Google Maps Ratings

Google Maps ratings favor:
- **Tourist-heavy locations** (more reviews from visitors)
- **Chain restaurants** (consistent, recognizable)
- **High-volume places** (more data = higher confidence)

This means authentic local spots, diaspora restaurants, and neighborhood gems often get buried.

### Our Solution: Two-Stage Reranking

#### Stage 1: ML-Based Undervaluation Detection

A **HistGradientBoostingRegressor** model predicts what rating a restaurant *should* have based on its structural characteristics:

- Review count (log-transformed)
- Price level
- Cuisine type
- Chain status
- Location (H3 hexagonal grid)
- Opening hours patterns

**Residual = Actual Rating - Predicted Rating**

Positive residual → Restaurant performs *better* than expected → Undervalued gem

#### Stage 2: Local Context Scoring

The final score combines multiple signals:

| Component | Weight | Description |
|-----------|--------|-------------|
| **Base Quality** | 30% | Normalized Google rating (0-5 → 0-1) |
| **ML Residual** | 25% | Undervaluation bonus from Stage 1 |
| **Saturation Curve** | -20% to +8% | Review count as proxy for commercialization |
| **Scarcity Score** | 15% | Limited hours/days = local favorite |
| **Independent Bonus** | 12% | Non-chain restaurants |
| **Tourist Trap Penalty** | -15% | High-volume mediocre places near tourist center |
| **Guide Recognition** | up to 12% | Michelin stars, local guides |
| **Community Endorsement** | up to 8% | Mentioned on local subreddit |
| **Local Street Bonus** | 6% | Known local foodie streets |
| **Perfection Penalty** | up to -4% | Statistically unlikely 5.0★ ratings |
| **Cuisine Specificity** | up to 3% | Regional cuisines over generic |

### Brussels Saturation Curve

In a mid-sized European capital (1.2M people), review count is a proxy for commercialization. Unlike NYC/London, Brussels locals don't generate 2000+ reviews for authentic spots.

| Review Count | Effect | Reasoning |
|-------------|--------|-----------|
| 0-35 | Penalty | Unreliable data |
| 35-100 | +5% | "Discovery" zone |
| 100-500 | +8% | "Sweet Spot" - locals/EU expats |
| 500-800 | +3% | "Famous Local" - institutions |
| 800-1500 | Neutral | Transition zone |
| 1500+ (tourist areas) | -10% to -20% | "Disneyfication" - tourist traps |
| 1500+ (local areas) | -5% to -12% | Could be delivery-optimized |

**Fritkot Exception**: Belgian friteries are high-turnover by design and exempt from high-volume penalties.

### Scarcity Score (The Secret Sauce)

Restaurants that are *hard to access* are often local favorites:

```
Scarcity = weighted sum of:
  - Hours scarcity (closes early = lunch spots)
  - Days scarcity (fewer days open = exclusive)
  - Schedule scarcity (closed weekends = local workers)
  - Cuisine scarcity (rare cuisines in your city)
```

A lunch-only spot open 4 days a week with 150 reviews? Probably a hidden gem that locals know about.

---

## Tier System

Restaurants are categorized into four tiers (Kitchen Confidential theme):

| Tier | Score | Icon | Description |
|------|-------|------|-------------|
| **Chef's Kiss** | ≥ 0.60 | 👑 | Exceptional craft, the real deal |
| **Kitchen Approved** | ≥ 0.50 | ❤️ | Would eat here off-shift |
| **Workable** | ≥ 0.40 | 🍴 | Feeds you right |
| **Line Cook Shrug** | < 0.40 | ● | Uninspired |

---

## Project Structure

```
local-food-map/
├── config/
│   ├── city_config_base.py     # Base configuration class
│   ├── brussels_config.py      # Brussels reference implementation
│   └── city_template.py        # Template for new cities
├── data/
│   ├── restaurants.json        # Raw scraped data
│   ├── restaurants_processed.csv
│   ├── restaurants_with_predictions.csv
│   ├── restaurants_reranked.csv  # Final ranked data
│   └── hex_features.csv        # Neighborhood aggregates
├── src/
│   ├── scraper.py              # Google Maps API scraper
│   ├── features.py             # Feature engineering
│   ├── model.py                # ML model training
│   ├── city_reranking.py       # City-specific scoring
│   ├── city_context.py         # Local knowledge
│   └── app.py                  # Flask web application
├── templates/
│   └── index.html              # Frontend (Leaflet.js map)
├── requirements.txt
├── Procfile                    # Railway/Heroku deployment
└── README.md
```

---

## Local Development

### Prerequisites

- Python 3.9+
- Google Maps API key (Places API enabled)

### Setup

```bash
# Clone the repository
git clone https://github.com/frederik12321/local-food-map.git
cd local-food-map

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GOOGLE_MAPS_API_KEY
```

### Run the Pipeline

```bash
# 1. Scrape restaurant data (requires API key)
python src/scraper.py

# 2. Engineer features
python src/features.py

# 3. Train ML model
python src/model.py

# 4. Apply city reranking
python src/city_reranking.py

# 5. Start web server
python src/app.py
```

Open http://localhost:5001 in your browser.

### Quick Start (Pre-processed Data)

```bash
python src/app.py
```

---

## Deployment

### Railway (Recommended)

1. Fork this repository
2. Connect to Railway
3. Add environment variable: `GOOGLE_MAPS_API_KEY` (optional)
4. **For persistent visitor stats:**
   - Create a volume in Railway dashboard
   - Mount it at `/data`
   - Add environment variable: `STATS_FILE_PATH=/data/stats.json`
5. Deploy

### Vercel / Render / Heroku

The `Procfile` and configuration files are pre-configured for common platforms.

```bash
gunicorn src.app:app --bind 0.0.0.0:$PORT
```

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Main web interface |
| `GET /api/restaurants` | JSON array of all restaurants |
| `GET /api/restaurants?cuisine=Japanese` | Filter by cuisine |
| `GET /api/restaurants?min_rating=4.5` | Filter by rating |
| `GET /api/restaurants?gems=true` | Top 100 only |
| `GET /api/hexagons` | GeoJSON neighborhood data |

---

## Technologies

- **Backend**: Flask, Python
- **ML**: scikit-learn (HistGradientBoostingRegressor)
- **Spatial**: H3 (Uber's hexagonal grid), K-means clustering
- **Frontend**: Leaflet.js, CartoDB tiles
- **Data**: Google Maps Places API
- **Deployment**: Railway, Vercel, Render

---

## Brussels Implementation Details

The Brussels version includes rich local context:

### Commune Classifications

| Tier | Areas |
|------|-------|
| **Tourist Heavy** | Bruxelles-Ville center |
| **Diaspora Hubs** | Saint-Gilles, Schaerbeek, Molenbeek, Saint-Josse |
| **Local Foodie** | Uccle, Woluwe, Auderghem |
| **Underexplored** | Anderlecht, Forest, Jette, Evere |

### Diaspora Cultural Context

Brussels is 75% foreign-origin population. Street-level diaspora hubs:

- **Matongé** → Congolese, Central African
- **Chaussée de Haecht** → Turkish, Moroccan
- **Rue de Brabant** → North African, Middle Eastern

### Guide Recognition

| Guide | Bonus |
|-------|-------|
| Michelin 2-star | +12% |
| Michelin 1-star | +8% |
| Bib Gourmand | +5% |
| Gault&Millau 15+ | +4% |
| r/brussels favorite | up to +8% |

---

## Data Quality Filtering

### Sentiment Analysis Pipeline

We implemented a sentiment-based quality control system to clean the restaurant dataset:

#### Stage 1: Structural Filtering
Automatically flagged and removed non-restaurants and low-quality entries:

| Category | Count | Examples |
|----------|-------|----------|
| **Non-restaurants** | 194 | Hotels, grocery stores, nightclubs, catering services |
| **Low-rated places** | 46 | Restaurants with <3.0★ and 10+ reviews |
| **Suspicious names** | 13 | Entries with "hotel" in name |

#### Stage 2: Sentiment Validation
Scraped Google Maps reviews and validated sentiment analysis accuracy:

- **TextBlob sentiment polarity** correlated with star ratings at **92.9% accuracy**
- Keyword-based flagging for "closed", "terrible", "racist" mentions
- Manual review of flagged entries to catch false positives

#### Results
- **239 entries removed** from original dataset
- **4,435 clean restaurants** in production
- False positive detection for edge cases (e.g., "scam" in "scampi", references to other closed restaurants)

---

## Inspiration & Credits

**Original Inspiration**: [Lauren Leek's London Food Dashboard](https://laurenleek.substack.com/p/how-google-maps-quietly-allocates) - The insight that ML residuals can identify undervalued restaurants.

### What We Kept ✅

- ML Residual Analysis
- Review Count Sweet Spot
- Chain Detection
- Spatial Clustering (H3)
- Tourist Trap Signals

### What We Added 🆕

- **Brussels Saturation Curve** - Review count as commercialization proxy
- **Fritkot Exception** - Belgian friteries exempt from volume penalties
- **Scarcity Score** - Limited hours = local favorite
- **Guide Recognition** - Michelin, local guides
- **Community Endorsement** - Reddit/local forums
- **Cuisine Specificity** - Regional > generic
- **Opening Hours Analysis** - Closes early, weekdays only
- **District Classification** - Diaspora hubs, tourist traps
- **Location-Aware Penalties** - Stronger penalties in tourist zones

### Not Implemented ❌

- Review Language Analysis (API limitation)
- Review Text Sentiment (scope)
- Photo Analysis (complexity)

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

### Adapting for a New City

We'd love to see this adapted for other cities! If you create a version for your city:

1. Create your city config in `config/your_city_config.py`
2. Document your local context data sources
3. Share your deployment link in Issues
4. Consider contributing city-agnostic improvements back upstream

---

## License

MIT License - feel free to adapt for your own city!

---

**Built with**: [Claude Code](https://claude.ai/code) as pair programming partner.

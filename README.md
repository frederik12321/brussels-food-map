# Brussels Food Map 🍴

**Discover hidden culinary gems in Brussels using machine learning and local context.**

A web application that combines Google Maps data with a Brussels-specific ranking algorithm to surface underrated restaurants that tourists and generic rating systems tend to overlook.

🔗 **Live Demo**: [brussels-food-map.up.railway.app](https://brussels-food-map.up.railway.app)

---

## How It Works

### The Problem with Google Maps Ratings

Google Maps ratings favor:
- **Tourist-heavy locations** (more reviews from visitors)
- **Chain restaurants** (consistent, recognizable)
- **High-volume places** (more data = higher confidence)

This means authentic local spots, diaspora restaurants, and neighborhood gems often get buried.

### Our Solution: Brussels-Specific Reranking

We built a two-stage ranking system:

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

#### Stage 2: Brussels Context Scoring

The final `brussels_score` combines multiple signals:

| Component | Weight | Description |
|-----------|--------|-------------|
| **Base Quality** | 30% | Normalized Google rating (0-5 → 0-1) |
| **ML Residual** | 25% | Undervaluation bonus from Stage 1 |
| **Scarcity Score** | 15% | Limited hours/days = local favorite |
| **Independent Bonus** | 10% | Non-chain restaurants |
| **Tourist Trap Penalty** | -15% | High-volume mediocre places near Grand Place |
| **Guide Recognition** | up to 12% | Michelin stars, Bib Gourmand, Gault&Millau |
| **Reddit Community** | up to 8% | Mentioned positively on r/brussels |
| **Local Street Bonus** | 6% | Known local foodie streets |
| **Other factors** | ~4% | Commune visibility, cold-start, rarity |

### Scarcity Score (The Secret Sauce)

Restaurants that are *hard to access* are often local favorites:

```
Scarcity = weighted sum of:
  - Review scarcity (50-500 reviews = sweet spot)
  - Hours scarcity (closes early = lunch spots)
  - Days scarcity (fewer days open = exclusive)
  - Schedule scarcity (closed weekends = local workers)
  - Cuisine scarcity (rare cuisines in Brussels)
```

A lunch-only spot open 4 days a week with 150 reviews? Probably a hidden gem that locals know about.

---

## Tier System

Restaurants are categorized into four tiers based on `brussels_score`:

| Tier | Score | Icon | Color | Description |
|------|-------|------|-------|-------------|
| **Must Try** | ≥ 0.60 | 👑 Crown | Gold #FFD700 | Top picks, exceptional quality |
| **Recommended** | ≥ 0.45 | ❤️ Heart | Green #2ECC71 | Solid choices, worth visiting |
| **Above Average** | ≥ 0.30 | 🍴 Utensils | Blue #3498DB | Better than typical |
| **Average** | < 0.30 | ● Dot | Gray #95A5A6 | Standard restaurants |

---

## Data Pipeline

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  scraper.py │ ──▶ │ features.py  │ ──▶ │  model.py   │ ──▶ │ brussels_    │
│             │     │              │     │             │     │ reranking.py │
│ Google Maps │     │ Feature      │     │ ML Model    │     │              │
│ Places API  │     │ Engineering  │     │ Training    │     │ Context      │
│             │     │              │     │ & Residuals │     │ Scoring      │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
       │                   │                    │                    │
       ▼                   ▼                    ▼                    ▼
brussels_restaurants   brussels_restaurants  restaurants_with    restaurants_
      .json              _processed.csv      _predictions.csv   _brussels_reranked.csv
```

### 1. Data Collection (`scraper.py`)

Scrapes restaurant data from Google Maps Places API:
- Name, rating, review count, price level
- Location (lat/lng), address
- Opening hours
- Cuisine type

### 2. Feature Engineering (`features.py`)

Transforms raw data into ML features:
- Log-transform review counts
- One-hot encode cuisines
- Extract opening hours patterns (closes early, weekdays only, etc.)
- Assign H3 hexagonal grid indices
- Detect chain restaurants

### 3. ML Model (`model.py`)

Trains HistGradientBoostingRegressor:
- Predicts expected rating based on features
- Calculates residuals (actual - predicted)
- Clusters neighborhoods using K-means on hex aggregates

### 4. Brussels Reranking (`brussels_reranking.py`)

Applies local context:
- Tourist trap detection (Grand Place proximity)
- Diaspora authenticity scoring
- Scarcity signals (hours, days, reviews)
- Guide recognition (Michelin, Gault&Millau)
- Local street bonuses

---

## Project Structure

```
brussels-food-map/
├── data/
│   ├── brussels_restaurants.json          # Raw scraped data
│   ├── brussels_restaurants_processed.csv # Cleaned & featured
│   ├── restaurants_with_predictions.csv   # ML predictions added
│   ├── restaurants_brussels_reranked.csv  # Final ranked data
│   ├── hex_features.csv                   # Neighborhood aggregates
│   └── summary.json                       # Statistics
├── src/
│   ├── scraper.py              # Google Maps API scraper
│   ├── features.py             # Feature engineering
│   ├── model.py                # ML model training
│   ├── brussels_reranking.py   # Brussels-specific scoring
│   ├── brussels_context.py     # Local knowledge (communes, streets)
│   └── app.py                  # Flask web application
├── templates/
│   └── index.html              # Frontend (Leaflet.js map)
├── requirements.txt
├── Procfile                    # Railway deployment
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
git clone https://github.com/frederik12321/brussels-food-map.git
cd brussels-food-map

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

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

# 4. Apply Brussels reranking
python src/brussels_reranking.py

# 5. Start web server
python src/app.py
```

Open http://localhost:5001 in your browser.

### Quick Start (Using Existing Data)

If you just want to run the app with pre-processed data:

```bash
python src/app.py
```

---

## Deployment

### Railway (Recommended)

1. Fork this repository
2. Connect to Railway
3. Add environment variable: `GOOGLE_MAPS_API_KEY` (optional, only for re-scraping)
4. Deploy

The `Procfile` and `railway.json` are pre-configured.

### Manual

```bash
gunicorn src.app:app --bind 0.0.0.0:$PORT
```

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Main web interface |
| `GET /api/restaurants` | JSON array of all restaurants |
| `GET /api/hexagons` | GeoJSON of neighborhood hexagons |

---

## Technologies

- **Backend**: Flask, Python
- **ML**: scikit-learn (HistGradientBoostingRegressor)
- **Spatial**: H3 (Uber's hexagonal grid), K-means clustering
- **Frontend**: Leaflet.js, CartoDB Voyager tiles
- **Data**: Google Maps Places API
- **Deployment**: Railway

---

## Brussels Context Knowledge

The algorithm incorporates local knowledge about Brussels:

### Commune Tiers

- **Tourist Heavy**: Bruxelles-Ville (center)
- **EU Bubble**: Etterbeek, parts of Ixelles
- **Diaspora Hubs**: Saint-Gilles, Schaerbeek, Molenbeek, Saint-Josse
- **Local Foodie**: Uccle, Woluwe-Saint-Lambert, Auderghem
- **Underexplored**: Anderlecht, Forest, Jette, Evere

### Known Local Streets

- Rue de Flandre (authentic Belgian)
- Chaussée de Charleroi (diverse)
- Rue Sainte-Catherine (seafood)
- Parvis de Saint-Gilles (trendy local)
- Place Jourdan (frites!)

### Tourist Trap Zones

- Grand Place (exponential penalty within 250m)
- Rue des Bouchers (heavy penalty)
- Manneken Pis area

---

## Data Coverage & Granularity

### What's Analyzed

| Level | Coverage | Detection Method |
|-------|----------|------------------|
| **Communes** | All 19 Brussels communes | Nearest center (approximate) |
| **Neighborhoods** | 13 special areas | 0.5km radius |
| **Local Streets** | 14 foodie streets | 120-200m radius |
| **Cuisines** | 11 diaspora types | Commune-based authenticity |
| **Guides** | ~100 restaurants | Name matching |

### Commune Classifications

| Tier | Communes |
|------|----------|
| **Tourist Heavy** (-15%) | Bruxelles |
| **EU Bubble** (-5%) | Etterbeek |
| **Diaspora Hub** (+15%) | Saint-Gilles, Schaerbeek, Molenbeek, Saint-Josse |
| **Local Foodie** (+10%) | Uccle, Woluwe-Saint-Lambert, Woluwe-Saint-Pierre, Auderghem, Watermael-Boitsfort |
| **Underexplored** (+12%) | Anderlecht, Forest, Jette, Evere, Ganshoren, Koekelberg, Berchem-Sainte-Agathe |
| **Mixed** (neutral) | Ixelles |

### Special Neighborhoods (0.5km radius)

**Local Foodie**: Matongé, Châtelain, Sainte-Catherine, Marolles, Saint-Boniface, Flagey, Parvis Saint-Gilles, Dansaert

**Mixed**: Sablon, Gare du Nord

**Tourist Trap**: Grand Place, Rue des Bouchers

**EU Bubble**: European Quarter

### Diaspora Authenticity

Restaurants get bonuses when their cuisine matches their commune:

- **Congolese/African** → Ixelles (Matongé), Saint-Gilles
- **Moroccan** → Molenbeek, Saint-Gilles, Saint-Josse, Schaerbeek
- **Turkish/Middle Eastern** → Saint-Josse, Schaerbeek
- **Portuguese** → Saint-Gilles
- **Ethiopian** → Bruxelles (Sainte-Catherine area)

### Guide Recognition

| Guide | Count | Bonus |
|-------|-------|-------|
| Michelin 2-star | 5 | +12% |
| Michelin 1-star | 11 | +8% |
| Bib Gourmand | ~30 | +5% |
| Gault&Millau 15+ | ~50 | +4% |

### Reddit Community Boost

Restaurants mentioned positively on r/brussels get a boost based on mention frequency:

| Mentions | Bonus | Label |
|----------|-------|-------|
| 10+ | +8% | r/brussels favorite |
| 5-9 | +6% | r/brussels favorite |
| 2-4 | +3% | r/brussels approved |

Hidden gems (< 200 reviews) get an additional 20% multiplier on their Reddit bonus.

### Limitations

- Commune detection uses nearest center, not official boundaries
- Neighborhood radius is fixed at 0.5km
- Guide lists are manually maintained and may become outdated

---

## Inspiration & Differences from Original

This project is inspired by **[Lauren Leek's London Food Dashboard](https://laurenleek.substack.com/p/how-google-maps-quietly-allocates)**, which brilliantly exposed how Google Maps ratings systematically undervalue certain restaurants.

### What We Kept from Lauren's Approach ✅

| Feature | Description |
|---------|-------------|
| **ML Residual Analysis** | Core concept: predict expected rating, find places that exceed it |
| **Review Count Sweet Spot** | Too few = unreliable, too many = tourist trap |
| **Chain Detection** | Penalize chain restaurants |
| **Spatial Clustering (H3)** | Hexagonal grid for neighborhood analysis |
| **Tourist Trap Signals** | Proximity-based penalties |

### What We Added for Brussels 🆕

| Feature | Description |
|---------|-------------|
| **Scarcity Score** | Limited hours/days = local favorite (lunch-only spots, weekday-only places) |
| **Guide Recognition** | Michelin stars, Bib Gourmand, Gault&Millau bonuses |
| **Reddit Community Boost** | Restaurants mentioned on r/brussels by locals get a boost |
| **Local Street Bonus** | Known foodie streets (Rue de Flandre, Parvis Saint-Gilles, etc.) |
| **EU Bubble Penalty** | Schuman area expat-targeted restaurant detection |
| **19 Commune Classification** | Each Brussels commune tagged by food scene type |
| **Café/Bar Detection** | Name-based classification to separate from restaurants |
| **Opening Hours Analysis** | Closes early, weekdays only, closed Sunday signals |
| **Restaurant Quality Tiers** | Must Try, Recommended, Above Average, Average based on score |

### What We Didn't Implement ❌

| Feature | Reason |
|---------|--------|
| **Review Language Analysis** | Google API doesn't provide this easily |
| **Review Text Sentiment** | Would require NLP pipeline, scope creep |
| **Photo Analysis** | Food photos vs selfies ratio - interesting but complex |
| **Time-based Review Patterns** | When locals vs tourists review - data not available |

### Design Philosophy Differences

Lauren's dashboard focused on **data visualization and exploration**. We focused on:

1. **Actionable Rankings** - Clear tier system (Must Try → Average)
2. **Mobile-First UX** - Optimized for on-the-go restaurant discovery
3. **Local Context** - Deep Brussels-specific knowledge baked into scoring
4. **Visual Identity** - Flemish feast painting aesthetic matching Brussels' rich culinary heritage

---

## Credits

**Original Inspiration**: [Lauren Leek](https://laurenleek.substack.com/) - Her article ["How Google Maps Quietly Allocates Fame"](https://laurenleek.substack.com/p/how-google-maps-quietly-allocates) sparked this entire project. The core insight that ML residuals can identify undervalued restaurants is brilliant.

**Brussels Adaptation**: Local context, scarcity scoring, guide recognition, and the Flemish feast UI.

**Built with**: Claude (Anthropic) - Pair programming partner for the entire codebase.

---

## License

MIT License - feel free to adapt for your own city!

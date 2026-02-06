# Brussels Food Map 🍴🇧🇪

**Find the restaurants Brussels locals actually eat at.**

An interactive map that uses machine learning and local knowledge to surface hidden gems that Google Maps buries under tourist traps and chain restaurants.

🔗 **Live**: [brussels-food-map.up.railway.app](https://brussels-food-map.up.railway.app)

---

## Why This Exists

Google Maps ratings are broken for finding good food in Brussels:

- **Tourist traps** near Grand Place have 4.0+ ratings from visitors who don't know better
- **Chain restaurants** score well because they're consistent (mediocre)
- **High-volume places** dominate because more reviews = higher confidence
- **Authentic diaspora spots** get buried because they don't optimize for tourists

This map fixes that by combining **machine learning** with **Brussels-specific cultural knowledge**.

---

## How Restaurants Are Ranked

Every restaurant gets a **Brussels Score** (0-100%) based on multiple signals. Here's exactly how it works:

### The Formula

```
Brussels Score = Quality Signals + Local Bonuses - Tourist Penalties
```

### Quality Signals (What Makes a Restaurant Good)

| Signal | Weight | How It Works |
|--------|--------|--------------|
| **Base Rating** | 32% | Google rating (4.5★ = 90% of weight) |
| **ML Undervaluation** | 18% | Is the rating higher than expected for this type of place? |
| **Scarcity** | 12% | Limited hours or days = locals know about it |
| **Independent** | 10% | Not a chain restaurant |
| **Guide Recognition** | 8% | Michelin stars, Bib Gourmand, Gault&Millau |
| **Diaspora Authenticity** | 7% | Turkish restaurant in Saint-Josse > Turkish restaurant near Grand Place |
| **Reddit Endorsed** | 5% | Mentioned positively on r/brussels |
| **Brussels Institution** | 4% | Potverdoemmeke, Fin de Siècle, etc. |
| **Family Name** | 2% | "Chez Marie" pattern |
| **Cuisine Specificity** | 2% | "Sichuan" > "Chinese" |

### Tourist Trap Penalties (What Lowers the Score)

| Penalty | Max Impact | Trigger |
|---------|------------|---------|
| **Tourist Location** | -15% | Within 150m of Grand Place with mediocre rating |
| **Chain Restaurant** | -10% | Bavet, Exki, Pizza Hut, etc. |
| **Over-commercialized** | -8% | 1500+ reviews in tourist areas |
| **EU Bubble** | -3% | Generic international near European Quarter |
| **Low Confidence** | -15% | Perfect 5.0 rating with only 20 reviews |

### The Secret Sauce: Confidence Weighting

**Ratings with few reviews count less.**

A 5.0★ restaurant with 15 reviews is probably friends and family. A 4.6★ with 300 reviews is statistically reliable.

We use Bayesian confidence weighting:
- 50 reviews = 29% confidence
- 200 reviews = 55% confidence
- 500 reviews = 70% confidence

This means a 4.5★ with 400 reviews often outranks a 4.9★ with 25 reviews.

### The Review Count Sweet Spot

In Brussels (1.2M people), review count tells you who's eating there:

| Reviews | What It Means | Effect |
|---------|---------------|--------|
| **0-25** | New or unknown | Penalty (unreliable data) |
| **25-150** | Discovery zone | Small bonus |
| **150-600** | Sweet spot | Bonus (locals + expats) |
| **600-1200** | Famous local | Neutral (could be institution) |
| **1200+** | Mass market | Penalty (probably tourists) |

**Exception**: Belgian friteries (Maison Antoine, etc.) can have 3000+ reviews and still be authentic - high turnover is the business model.

---

## The Tier System

Restaurants are sorted into four tiers displayed with colored markers:

| Tier | Score | Color | What It Means |
|------|-------|-------|---------------|
| **Gold** | 55%+ | 🟡 Amber | Must try - exceptional quality |
| **Silver** | 48-55% | ⚪ Gray | Great choice - highly recommended |
| **Bronze** | 30-48% | 🟤 Brown | Solid - decent option |
| **Unranked** | <30% | ⚫ Slate | Skip it |

Current distribution:
- Gold: ~6% of restaurants
- Silver: ~15%
- Bronze: ~47%
- Unranked: ~32%

---

## Brussels-Specific Knowledge

### Commune Classifications

| Type | Areas | What It Means |
|------|-------|---------------|
| **Tourist Heavy** | Grand Place, Sablon | Higher standards needed |
| **Diaspora Hubs** | Saint-Gilles, Schaerbeek, Molenbeek, Saint-Josse | Authentic ethnic food rewarded |
| **Local Foodie** | Uccle, Woluwe, Auderghem | Residential, locals know best |
| **Underexplored** | Anderlecht, Forest, Jette, Evere | Hidden gems likely |

### Diaspora Authenticity

Brussels is 75% foreign-origin population. We reward restaurants that match their community:

- **Congolese in Matongé** → Maximum bonus
- **Turkish on Chaussée de Haecht** → Maximum bonus
- **Moroccan in Molenbeek** → Maximum bonus
- **Turkish near Grand Place** → No bonus (probably tourist-facing)

### Guide Recognition

| Guide | Bonus |
|-------|-------|
| Michelin 2-star | +8% |
| Michelin 1-star | +6% |
| Bib Gourmand | +4% |
| Gault&Millau 15+ | +3% |
| r/brussels mentions | +5% |

---

## Technical Details

### Data Pipeline

1. **Scrape** - Google Maps Places API for Brussels restaurants
2. **Clean** - Remove non-restaurants, closed places, hotels
3. **ML Model** - HistGradientBoostingRegressor predicts "expected" rating
4. **Residual** - Actual rating - Expected rating = Undervaluation signal
5. **Brussels Scoring** - Apply all local context signals
6. **Rank** - Sort by Brussels Score

### Statistical Improvements

- **Sigmoid smoothing** - No hard cutoffs, smooth transitions
- **Confidence weighting** - Ratings weighted by sample size
- **Collinearity fixes** - Tourist penalty reduced if already penalized for reviews
- **Normalized weights** - All positive signals sum to exactly 1.0

### Data Quality Filtering

Before scoring, we removed:
- 194 non-restaurants (hotels, grocery stores)
- 46 low-rated places (<3.0★ with 10+ reviews)
- 13 suspicious entries (hotel names)

> **Note:** Due to limited scraping, sentiment analysis was used for quality control flagging rather than scoring.

---

## Features

- 📍 **GPS Location** - Find restaurants near you (tap to activate/deactivate)
- 🔍 **Filters** - Cuisine, commune, price, rating, tier
- 🏆 **Top 100** - Quick view of best restaurants
- 📊 **Score Breakdown** - See exactly why each restaurant ranks where it does
- 🔐 **Privacy-first** - No cookies, no tracking, location stays in your browser

---

## Development

```bash
# Clone
git clone https://github.com/frederik12321/brussels-food-map.git
cd brussels-food-map

# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run
cd src && python app.py
# Open http://localhost:5001
```

### Environment Variables

```bash
# Optional - for scraping new data
GOOGLE_MAPS_API_KEY=your_key

# Optional - for persistent visitor stats
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key
```

---

## Deployment

**Railway** (recommended):
1. Fork this repo
2. Connect to Railway
3. Add `SUPABASE_KEY` for persistent stats
4. Deploy

The `Procfile` is pre-configured for Railway/Heroku.

---

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/restaurants` | All restaurants with filters |
| `GET /api/restaurants?cuisine=Turkish` | Filter by cuisine |
| `GET /api/restaurants?commune=Ixelles` | Filter by commune |
| `GET /api/brussels_gems?limit=50` | Top N by Brussels score |

---

## Credits

**Inspiration**: [Lauren Leek's London Food Dashboard](https://laurenleek.substack.com/p/how-google-maps-quietly-allocates) - ML residuals to identify undervalued restaurants.

**Built with**: Python, Flask, scikit-learn, Leaflet.js, H3

**Pair programmed with**: [Claude Code](https://claude.ai/code)

---

## License

MIT License - feel free to adapt for your own city!

---

*Last updated: February 2025*

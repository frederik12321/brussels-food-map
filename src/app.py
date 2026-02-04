"""
Flask Web Application for Brussels Food Map

Interactive dashboard with map visualization, filters, and search.
Now with Brussels-specific reranking!
"""

import ast
import json
import math
import os
from datetime import datetime, date
from threading import Lock
import pandas as pd
import h3
import requests
from flask import Flask, render_template, jsonify, request

app = Flask(__name__, template_folder="../templates", static_folder="../static")

# Cache data at startup for faster responses
_cached_data = None
_cached_hex = None
_cached_summary = None

# Supabase configuration for persistent stats
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ijvhhxdfwisllokinsyi.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
_stats_lock = Lock()
_stats_cache = None


def safe_parse_hours(hours_str):
    """Safely parse opening hours string to list.

    Uses ast.literal_eval which only parses Python literals (safe),
    but validates the result is actually a list of strings.
    """
    if not hours_str or (isinstance(hours_str, float) and math.isnan(hours_str)):
        return None
    if isinstance(hours_str, list):
        return hours_str
    if not isinstance(hours_str, str):
        return None
    try:
        result = ast.literal_eval(hours_str)
        # Validate it's a list of strings (not arbitrary data)
        if isinstance(result, list) and all(isinstance(x, str) for x in result):
            return result
        return None
    except (ValueError, SyntaxError):
        return None


def _supabase_headers():
    """Get headers for Supabase API requests."""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }


def load_stats():
    """Load page view statistics from Supabase."""
    global _stats_cache
    if _stats_cache is not None:
        return _stats_cache

    if not SUPABASE_KEY:
        # Fallback if no Supabase configured
        return {"daily": {}, "total": 0}

    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/page_stats?id=eq.main&select=*",
            headers=_supabase_headers(),
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                row = data[0]
                _stats_cache = {
                    "daily": row.get("daily", {}),
                    "total": row.get("total", 0)
                }
                return _stats_cache
    except Exception:
        pass

    _stats_cache = {"daily": {}, "total": 0}
    return _stats_cache


def save_stats(stats):
    """Save page view statistics to Supabase."""
    global _stats_cache
    _stats_cache = stats

    if not SUPABASE_KEY:
        return

    try:
        requests.patch(
            f"{SUPABASE_URL}/rest/v1/page_stats?id=eq.main",
            headers=_supabase_headers(),
            json={
                "total": stats["total"],
                "daily": stats["daily"],
                "updated_at": datetime.utcnow().isoformat()
            },
            timeout=5
        )
    except Exception:
        pass  # Fail silently - stats are not critical


def increment_page_view():
    """Increment daily and total page view counters."""
    with _stats_lock:
        stats = load_stats()
        today = date.today().isoformat()
        stats["daily"][today] = stats["daily"].get(today, 0) + 1
        stats["total"] = stats.get("total", 0) + 1
        # Keep only last 90 days of daily stats
        if len(stats["daily"]) > 90:
            sorted_days = sorted(stats["daily"].keys())
            for old_day in sorted_days[:-90]:
                del stats["daily"][old_day]
        save_stats(stats)


def load_data():
    """Load processed restaurant data (cached after first load)."""
    global _cached_data
    if _cached_data is not None:
        return _cached_data.copy()
    try:
        _cached_data = pd.read_csv("../data/restaurants_brussels_reranked.csv")
        return _cached_data.copy()
    except FileNotFoundError:
        try:
            _cached_data = pd.read_csv("../data/restaurants_with_predictions.csv")
            return _cached_data.copy()
        except FileNotFoundError:
            return None


def load_hex_features():
    """Load hexagon neighborhood features (cached)."""
    global _cached_hex
    if _cached_hex is not None:
        return _cached_hex
    try:
        _cached_hex = pd.read_csv("../data/hex_features.csv")
        return _cached_hex
    except FileNotFoundError:
        return None


def load_summary():
    """Load summary statistics (cached)."""
    global _cached_summary
    if _cached_summary is not None:
        return _cached_summary
    try:
        with open("../data/summary.json", "r") as f:
            _cached_summary = json.load(f)
            return _cached_summary
    except FileNotFoundError:
        return {}


@app.route("/")
def index():
    """Main dashboard page."""
    # Count page view (privacy-friendly: no user data, just daily totals)
    increment_page_view()

    summary = load_summary()
    df = load_data()

    cuisines = []
    communes = []
    tiers = []

    if df is not None:
        cuisines = sorted(df["cuisine"].dropna().unique().tolist())
        if "commune" in df.columns:
            communes = sorted(df["commune"].dropna().unique().tolist())
        if "tier" in df.columns:
            tiers = df["tier"].dropna().unique().tolist()

    return render_template(
        "index.html",
        summary=summary,
        cuisines=cuisines,
        communes=communes,
        tiers=tiers
    )


@app.route("/privacy")
def privacy():
    """Privacy policy page."""
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    """Terms of service page."""
    return render_template("terms.html")


@app.route("/methodology")
def methodology():
    """Methodology page explaining the ranking system."""
    return render_template("methodology.html")


@app.route("/dashboard")
def dashboard():
    """Admin dashboard with visitor statistics."""
    return render_template("dashboard.html")


@app.route("/api/stats")
def api_stats():
    """
    Simple page view statistics (privacy-friendly).
    No user data, just daily totals.
    """
    stats = load_stats()
    daily = stats.get("daily", {})

    # Calculate some useful aggregates
    today = date.today().isoformat()
    today_views = daily.get(today, 0)

    # Last 7 days
    last_7_days = 0
    for i in range(7):
        d = (date.today() - pd.Timedelta(days=i)).isoformat()
        last_7_days += daily.get(d, 0)

    # Last 30 days
    last_30_days = 0
    for i in range(30):
        d = (date.today() - pd.Timedelta(days=i)).isoformat()
        last_30_days += daily.get(d, 0)

    return jsonify({
        "total": stats.get("total", 0),
        "today": today_views,
        "last_7_days": last_7_days,
        "last_30_days": last_30_days,
        "daily": daily
    })


@app.route("/api/restaurants")
def api_restaurants():
    """API endpoint for restaurant data with filtering."""
    df = load_data()

    if df is None:
        return jsonify({"error": "No data available. Run the scraper first."}), 404

    # Apply filters from query params
    min_rating = request.args.get("min_rating", type=float)
    max_rating = request.args.get("max_rating", type=float)
    cuisine = request.args.get("cuisine")
    min_reviews = request.args.get("min_reviews", type=int)
    brussels_gems = request.args.get("brussels_gems", type=lambda x: x.lower() == "true")
    search = request.args.get("search", "").lower()
    price_level = request.args.get("price_level", type=int)
    commune = request.args.get("commune")
    tier = request.args.get("tier")
    venue_type = request.args.get("venue_type")
    diaspora_only = request.args.get("diaspora_only", type=lambda x: x.lower() == "true")
    sort_by = request.args.get("sort_by", "brussels_score")  # Default to Brussels score
    guide_filter = request.args.get("guide")
    open_day = request.args.get("open_day")
    open_time = request.args.get("open_time", type=int)

    if min_rating:
        df = df[df["rating"] >= min_rating]

    if max_rating:
        df = df[df["rating"] <= max_rating]

    if cuisine and cuisine != "all":
        df = df[df["cuisine"] == cuisine]

    if min_reviews:
        df = df[df["review_count"] >= min_reviews]

    if commune and commune != "all" and "commune" in df.columns:
        df = df[df["commune"] == commune]

    if tier and tier != "all" and "tier" in df.columns:
        df = df[df["tier"] == tier]

    if venue_type and venue_type != "all" and "venue_type" in df.columns:
        df = df[df["venue_type"] == venue_type]

    if diaspora_only:
        diaspora_cuisines = ["Congolese", "African", "Moroccan", "Turkish", "Lebanese", "Ethiopian", "Middle Eastern"]
        df = df[df["cuisine"].isin(diaspora_cuisines)]

    if brussels_gems and "brussels_score" in df.columns:
        # Show top 100 by Brussels score
        df = df.nlargest(100, "brussels_score")

    if search:
        df = df[df["name"].str.lower().str.contains(search, na=False)]

    if price_level is not None:
        df = df[df["price_numeric"] == price_level]

    # Guide recognition filter
    if guide_filter:
        if guide_filter == "michelin":
            df = df[df["michelin_stars"] > 0]
        elif guide_filter == "bib":
            df = df[df["bib_gourmand"] == True]
        elif guide_filter == "gaultmillau":
            df = df[df["gault_millau"] == True]
        elif guide_filter == "reddit":
            df = df[df["reddit_mentions"] >= 2]
        elif guide_filter == "afsca":
            df = df[df["has_afsca_smiley"] == True]
        elif guide_filter == "any_guide":
            df = df[(df["michelin_stars"] > 0) | (df["bib_gourmand"] == True) | (df["gault_millau"] == True)]

    # Day/time filtering (done client-side for accuracy, but we can pre-filter here)
    # This is a basic server-side filter - more accurate filtering happens client-side
    if open_day and "opening_hours" in df.columns:
        def is_open_on_day(hours_str, day):
            hours = safe_parse_hours(hours_str)
            if not hours:
                return True  # Include unknowns
            for h in hours:
                if h and h.startswith(day):
                    return "Closed" not in h
            return False
        df = df[df["opening_hours"].apply(lambda x: is_open_on_day(x, open_day))]

    # Sort
    if sort_by == "brussels_score" and "brussels_score" in df.columns:
        df = df.sort_values("brussels_score", ascending=False)
    elif sort_by == "rating":
        df = df.sort_values("rating", ascending=False)
    elif sort_by == "residual":
        df = df.sort_values("residual", ascending=False)

    # Select columns for response
    columns = [
        "id", "name", "address", "lat", "lng", "rating", "review_count",
        "cuisine", "venue_type", "price_numeric", "is_chain",
        "predicted_rating", "residual", "google_maps_url",
        "commune", "neighborhood", "diaspora_street", "tier", "commune_tier", "brussels_score",
        "score_base_quality", "score_residual_score", "score_tourist_penalty", "score_scarcity_bonus",
        "score_diaspora_bonus", "score_perfection_penalty", "score_guide_bonus", "score_reddit_bonus",
        "closes_early", "typical_close_hour", "weekdays_only", "closed_sunday",
        "days_open_count", "is_rare_cuisine", "opening_hours",
        # Guide recognition
        "michelin_stars", "bib_gourmand", "gault_millau", "reddit_mentions", "has_afsca_smiley",
        # Scarcity sub-components for transparency
        "scarcity_review_scarcity", "scarcity_hours_scarcity", "scarcity_days_scarcity",
        "scarcity_schedule_scarcity", "scarcity_cuisine_scarcity"
    ]

    # Ensure columns exist
    columns = [c for c in columns if c in df.columns]

    # Replace NaN with None for JSON serialization
    result_df = df[columns].copy()

    # Convert to dict and replace NaN/None values properly
    result = result_df.to_dict(orient="records")

    # Clean up NaN values that pandas converts incorrectly
    # Also parse opening_hours from string to list
    for record in result:
        for key, value in record.items():
            if value is None or (isinstance(value, float) and math.isnan(value)):
                record[key] = None
            elif key == "opening_hours" and isinstance(value, str):
                record[key] = safe_parse_hours(value)

    return jsonify(result)


@app.route("/api/hexagons")
def api_hexagons():
    """API endpoint for hexagon neighborhood data."""
    hex_df = load_hex_features()

    if hex_df is None:
        return jsonify({"error": "No hexagon data available."}), 404

    # Generate GeoJSON for hexagons
    features = []

    for _, row in hex_df.iterrows():
        if pd.isna(row["h3_index"]):
            continue

        # Get hexagon boundary
        boundary = h3.cell_to_boundary(row["h3_index"])
        # Convert to GeoJSON format (lng, lat) and close the polygon
        coords = [[lng, lat] for lat, lng in boundary]
        coords.append(coords[0])  # Close the polygon

        feature = {
            "type": "Feature",
            "properties": {
                "h3_index": row["h3_index"],
                "mean_rating": round(row["mean_rating"], 2) if pd.notna(row["mean_rating"]) else None,
                "mean_residual": round(row["mean_residual"], 3) if pd.notna(row["mean_residual"]) else None,
                "restaurant_count": int(row["restaurant_count"]),
                "cluster_label": row["cluster_label"],
                "hub_score": round(row["hub_score"], 2) if pd.notna(row["hub_score"]) else None
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]
            }
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    return jsonify(geojson)


@app.route("/api/summary")
def api_summary():
    """API endpoint for summary statistics."""
    return jsonify(load_summary())


@app.route("/api/gems")
def api_gems():
    """API endpoint for top hidden gems."""
    df = load_data()

    if df is None:
        return jsonify({"error": "No data available."}), 404

    limit = min(request.args.get("limit", 50, type=int), 500)  # Cap at 500

    gems = df.nlargest(limit, "residual")[
        ["name", "address", "cuisine", "rating", "review_count",
         "predicted_rating", "residual", "lat", "lng", "google_maps_url"]
    ].copy()

    gems["undervaluation_pct"] = (gems["residual"] * 100).round(1)

    return jsonify(gems.to_dict(orient="records"))


@app.route("/api/brussels_gems")
def api_brussels_gems():
    """API endpoint for top restaurants by Brussels score."""
    df = load_data()

    if df is None:
        return jsonify({"error": "No data available."}), 404

    if "brussels_score" not in df.columns:
        return jsonify({"error": "Brussels reranking not available. Run brussels_reranking.py first."}), 404

    limit = min(request.args.get("limit", 50, type=int), 500)  # Cap at 500
    commune = request.args.get("commune")

    if commune and commune != "all":
        df = df[df["commune"] == commune]

    columns = ["name", "address", "cuisine", "rating", "review_count",
               "predicted_rating", "residual", "lat", "lng", "google_maps_url",
               "commune", "neighborhood", "tier", "brussels_score"]

    columns = [c for c in columns if c in df.columns]

    gems = df.nlargest(limit, "brussels_score")[columns].copy()

    return jsonify(gems.to_dict(orient="records"))


@app.route("/api/communes")
def api_communes():
    """API endpoint for commune statistics."""
    df = load_data()

    if df is None or "commune" not in df.columns:
        return jsonify({"error": "Commune data not available."}), 404

    commune_stats = df.groupby("commune").agg({
        "rating": "mean",
        "review_count": "sum",
        "brussels_score": "mean" if "brussels_score" in df.columns else "count",
        "name": "count"
    }).reset_index()

    commune_stats.columns = ["commune", "avg_rating", "total_reviews", "avg_brussels_score", "restaurant_count"]
    commune_stats = commune_stats.round(2)

    return jsonify(commune_stats.to_dict(orient="records"))


@app.route("/api/diaspora")
def api_diaspora():
    """API endpoint for diaspora restaurants."""
    df = load_data()

    if df is None:
        return jsonify({"error": "No data available."}), 404

    diaspora_cuisines = ["Congolese", "African", "Moroccan", "Turkish", "Lebanese", "Ethiopian", "Middle Eastern"]
    diaspora_df = df[df["cuisine"].isin(diaspora_cuisines)]

    if "brussels_score" in diaspora_df.columns:
        diaspora_df = diaspora_df.sort_values("brussels_score", ascending=False)
    else:
        diaspora_df = diaspora_df.sort_values("rating", ascending=False)

    columns = ["name", "address", "cuisine", "rating", "review_count",
               "lat", "lng", "google_maps_url", "commune", "brussels_score"]

    columns = [c for c in columns if c in diaspora_df.columns]

    return jsonify(diaspora_df[columns].head(50).to_dict(orient="records"))


if __name__ == "__main__":
    import os
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode, port=5001)

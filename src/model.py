"""
ML Model for Predicting Restaurant Ratings

Uses a gradient-boosted decision tree (HistGradientBoostingRegressor)
to predict expected ratings based on structural characteristics.
The residual identifies algorithmically undervalued restaurants.
"""

import json
import pickle
import pandas as pd
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
import h3

from features import load_data, engineer_features, prepare_ml_features


def train_rating_model(X, y):
    """Train the gradient boosting model to predict ratings."""
    model = HistGradientBoostingRegressor(
        max_iter=200,
        max_depth=8,
        learning_rate=0.1,
        min_samples_leaf=20,
        random_state=42
    )

    # Cross-validation to evaluate
    cv_scores = cross_val_score(model, X, y, cv=5, scoring="r2")
    print(f"Cross-validation R² scores: {cv_scores}")
    print(f"Mean R²: {cv_scores.mean():.3f} (+/- {cv_scores.std()*2:.3f})")

    # Train on full data
    model.fit(X, y)

    return model


def calculate_residuals(df, model, X):
    """Calculate residuals (actual - predicted) to find undervalued restaurants."""
    predictions = model.predict(X)
    df["predicted_rating"] = predictions
    df["residual"] = df["rating"] - predictions

    # Positive residual = performs better than expected (undervalued)
    # Negative residual = performs worse than expected (overvalued)

    return df


def cluster_neighborhoods(df):
    """
    Cluster neighborhoods using hexagonal aggregation and K-means.
    Creates hub scores for spatial analysis.
    """
    # Aggregate features by hexagon
    hex_features = df.groupby("h3_index").agg({
        "rating": "mean",
        "residual": "mean",
        "review_count": ["sum", "mean"],
        "is_chain": "mean",
        "price_numeric": "mean",
        "cuisine": lambda x: x.nunique(),  # Cuisine diversity
        "name": "count"  # Restaurant density
    }).reset_index()

    # Flatten column names
    hex_features.columns = [
        "h3_index", "mean_rating", "mean_residual",
        "total_reviews", "mean_reviews", "chain_share",
        "mean_price", "cuisine_diversity", "restaurant_count"
    ]

    # Features for clustering
    cluster_features = [
        "mean_rating", "mean_residual", "mean_reviews",
        "chain_share", "mean_price", "cuisine_diversity", "restaurant_count"
    ]

    X_cluster = hex_features[cluster_features].fillna(0)

    # Standardize
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_cluster)

    # PCA for hub score
    pca = PCA(n_components=1)
    hex_features["hub_score"] = pca.fit_transform(X_scaled)

    # K-means clustering into 4 types
    kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
    hex_features["cluster"] = kmeans.fit_predict(X_scaled)

    # Label clusters based on characteristics
    cluster_stats = hex_features.groupby("cluster").agg({
        "mean_rating": "mean",
        "mean_residual": "mean",
        "restaurant_count": "mean"
    }).reset_index()

    # Sort by rating to assign meaningful labels
    cluster_stats = cluster_stats.sort_values("mean_rating", ascending=False)
    cluster_labels = {
        cluster_stats.iloc[0]["cluster"]: "Elite",
        cluster_stats.iloc[1]["cluster"]: "Strong",
        cluster_stats.iloc[2]["cluster"]: "Everyday",
        cluster_stats.iloc[3]["cluster"]: "Emerging"
    }

    hex_features["cluster_label"] = hex_features["cluster"].map(cluster_labels)

    # Get hexagon center coordinates
    hex_features["hex_lat"] = hex_features["h3_index"].apply(
        lambda x: h3.cell_to_latlng(x)[0] if x else None
    )
    hex_features["hex_lng"] = hex_features["h3_index"].apply(
        lambda x: h3.cell_to_latlng(x)[1] if x else None
    )

    # Get hexagon boundary for visualization
    hex_features["boundary"] = hex_features["h3_index"].apply(
        lambda x: h3.cell_to_boundary(x) if x else None
    )

    return hex_features


def identify_gems(df, top_n=100):
    """Identify the most undervalued restaurants (hidden gems)."""
    gems = df.nlargest(top_n, "residual")[
        ["name", "address", "cuisine", "rating", "review_count",
         "predicted_rating", "residual", "lat", "lng", "google_maps_url"]
    ].copy()

    gems["undervaluation_score"] = (gems["residual"] * 100).round(1)

    return gems


def save_model_outputs(df, hex_features, model, output_dir="../data"):
    """Save all model outputs."""
    # Save full dataset with predictions
    df.to_csv(f"{output_dir}/restaurants_with_predictions.csv", index=False)
    print(f"Saved restaurant predictions to {output_dir}/restaurants_with_predictions.csv")

    # Save hexagon features
    hex_features_save = hex_features.drop(columns=["boundary"])  # Can't serialize easily
    hex_features_save.to_csv(f"{output_dir}/hex_features.csv", index=False)
    print(f"Saved hexagon features to {output_dir}/hex_features.csv")

    # Save model
    with open(f"{output_dir}/rating_model.pkl", "wb") as f:
        pickle.dump(model, f)
    print(f"Saved model to {output_dir}/rating_model.pkl")

    # Save summary statistics
    summary = {
        "total_restaurants": len(df),
        "mean_rating": float(df["rating"].mean()),
        "mean_predicted": float(df["predicted_rating"].mean()),
        "mean_residual": float(df["residual"].mean()),
        "std_residual": float(df["residual"].std()),
        "num_hexagons": len(hex_features),
        "cuisines": df["cuisine"].value_counts().to_dict(),
        "cluster_counts": hex_features["cluster_label"].value_counts().to_dict()
    }

    with open(f"{output_dir}/summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved summary to {output_dir}/summary.json")


def main():
    """Main pipeline to train model and generate insights."""
    print("Loading and processing data...")
    df = load_data()
    df = engineer_features(df)
    print(f"Working with {len(df)} restaurants")

    print("\nPreparing ML features...")
    X, y = prepare_ml_features(df)
    print(f"Feature matrix shape: {X.shape}")

    print("\nTraining rating prediction model...")
    model = train_rating_model(X, y)

    print("\nCalculating residuals...")
    df = calculate_residuals(df, model, X)

    print("\nClustering neighborhoods...")
    hex_features = cluster_neighborhoods(df)
    print(f"Identified {len(hex_features)} neighborhood cells")

    print("\nTop 10 Hidden Gems:")
    gems = identify_gems(df, top_n=10)
    for _, gem in gems.iterrows():
        print(f"  {gem['name']}: {gem['rating']:.1f} (expected {gem['predicted_rating']:.2f}, "
              f"+{gem['undervaluation_score']}% undervalued)")

    print("\nCluster distribution:")
    print(hex_features["cluster_label"].value_counts())

    print("\nSaving outputs...")
    save_model_outputs(df, hex_features, model)

    return df, hex_features, model


if __name__ == "__main__":
    main()

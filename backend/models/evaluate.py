"""
Evaluate the trained model against a held-out sample from MongoDB.

Usage:
    python3 -m backend.models.evaluate [--n 500] [--seed 42]
"""

import argparse
import joblib
import os

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

from backend.data.loader import fetch_properties
from backend.data.processor import build_features

SAVED_DIR = os.path.join(os.path.dirname(__file__), "saved")


def evaluate(n: int = 500, seed: int = 42) -> None:
    print("Fetching properties from MongoDB...")
    records = fetch_properties()
    if not records:
        raise RuntimeError("No properties found. Run ingestion first.")

    df = pd.DataFrame(records).sample(min(n, len(records)), random_state=seed)
    print(f"Sampled {len(df)} properties")

    print("Building features...")
    X, y = build_features(df)
    print(f"  {len(X)} rows after filtering, {X.shape[1]} features")

    model = joblib.load(os.path.join(SAVED_DIR, "model.pkl"))
    feature_cols = joblib.load(os.path.join(SAVED_DIR, "features.pkl"))

    # Align columns to training feature order
    for col in feature_cols:
        if col not in X.columns:
            X[col] = 0
    X = X[feature_cols]

    preds = np.expm1(model.predict(X))
    actuals = y.values

    mae = mean_absolute_error(actuals, preds)
    r2 = r2_score(actuals, preds)
    mape = np.mean(np.abs((actuals - preds) / actuals)) * 100

    print(f"\n--- Results (n={len(actuals)}) ---")
    print(f"MAE:   ${mae:,.0f}")
    print(f"MAPE:  {mape:.1f}%")
    print(f"R²:    {r2:.3f}")

    # Sample predictions
    results = pd.DataFrame({
        "actual":    actuals,
        "predicted": preds.round(0),
        "error":     (preds - actuals).round(0),
        "pct_error": ((preds - actuals) / actuals * 100).round(1),
    }).reset_index(drop=True)

    print("\n--- Sample predictions (10 random) ---")
    sample = results.sample(10, random_state=seed).sort_values("actual")
    for _, row in sample.iterrows():
        sign = "+" if row["error"] >= 0 else ""
        print(f"  actual: ${row['actual']:>10,.0f}  predicted: ${row['predicted']:>10,.0f}  ({sign}{row['pct_error']:.1f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=500, help="Number of properties to evaluate (default: 500)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    args = parser.parse_args()
    evaluate(n=args.n, seed=args.seed)

import os
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

from backend.data.loader import fetch_properties
from backend.data.processor import build_features


def save_model(model, filename: str):
    """Save a trained model locally (disk)."""
    path = os.path.join(os.path.dirname(__file__), "saved", filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    joblib.dump(model, path)
    print(f"Model saved to {path}")


def load_model(filename: str):
    """Load a saved model from disk."""
    path = os.path.join(os.path.dirname(__file__), "saved", filename)
    return joblib.load(path)


def train(model_type: str = "random_forest") -> None:
    print("Fetching properties from MongoDB...")
    records = fetch_properties()
    if not records:
        raise RuntimeError("No properties found in MongoDB. Run ingestion first.")

    df = pd.DataFrame(records)
    print(f"Loaded {len(df)} properties")

    print("Building features...")
    X, y = build_features(df)
    print(f"Training on {len(X)} rows with {X.shape[1]} features: {list(X.columns)}")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    if model_type == "gradient_boosting":
        model = HistGradientBoostingRegressor(max_iter=200, max_depth=5, learning_rate=0.1, random_state=42)
    else:
        model = RandomForestRegressor(n_estimators=200, max_depth=None, n_jobs=-1, random_state=42)

    print(f"Training {model_type}...")
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)
    print(f"MAE:  ${mae:,.0f}")
    print(f"R²:   {r2:.3f}")

    save_model(model, "model.pkl")

    # Save feature column order for use in predict.py
    feature_path = os.path.join(os.path.dirname(__file__), "saved", "features.pkl")
    joblib.dump(list(X.columns), feature_path)
    print(f"Feature list saved to {feature_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="random_forest", choices=["random_forest", "gradient_boosting"])
    args = parser.parse_args()
    train(args.model)

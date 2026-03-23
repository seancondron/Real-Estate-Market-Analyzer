import joblib
import os
import pandas as pd
from datetime import date

from backend.models.train import load_model

SAVED_DIR = os.path.join(os.path.dirname(__file__), "..", "models", "saved")


def run_prediction(input_data: dict, target_date: date | None = None) -> float:
    """
    Predict price for a single property.

    input_data: dict with keys like beds, baths, sqft, year_built,
                lot_sqft, median_income, garage, property_type, zip_code
    target_date: date to predict for (defaults to today)
    """
    if target_date is None:
        today = date.today()
        month = today.month % 12 + 1
        year = today.year + (1 if today.month == 12 else 0)
        target_date = date(year, month, 1)

    model = load_model("model.pkl")
    feature_cols = joblib.load(os.path.join(SAVED_DIR, "features.pkl"))

    df = pd.DataFrame([input_data])

    # Age
    if "year_built" in df.columns:
        df["age"] = 2024 - pd.to_numeric(df["year_built"], errors="coerce")
        df["age"] = df["age"].clip(0, 200)

    # Garage
    df["has_garage"] = int(bool(input_data.get("garage", False)))

    # Property type encoding
    property_type = str(input_data.get("property_type", "single family")).lower().strip()
    for pt in ["single_family", "townhouse", "condo", "multi-family"]:
        df[f"type_{pt}"] = int(property_type == pt.replace("_", " "))

    # Target date features
    df["sale_year"] = target_date.year
    df["sale_month"] = target_date.month

    df = df.apply(pd.to_numeric, errors="coerce")

    # Align to training feature columns, fill missing with 0
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0
    df = df[feature_cols]

    return float(model.predict(df)[0])

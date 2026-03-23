import pandas as pd
import numpy as np
from backend.db.schema import DFW_CITIES, RESIDENTIAL_TYPES
from backend.db.mongodb import db

CURRENT_YEAR = 2024

PROPERTY_TYPE_CATEGORIES = ["single family", "townhouse", "condo", "multi-family"]


def filter_dfw_homes(df: pd.DataFrame, zip_codes: list[str] | None = None) -> pd.DataFrame:
    """Keep only DFW-area residential home rows."""
    if "city" in df.columns:
        df = df[df["city"].str.lower().isin(DFW_CITIES)]
    if "property_type" in df.columns:
        df = df[df["property_type"].str.lower().isin(RESIDENTIAL_TYPES)]
    if zip_codes and "zip_code" in df.columns:
        normalized = [str(z).zfill(5) for z in zip_codes]
        df = df[df["zip_code"].isin(normalized)]
    return df.reset_index(drop=True)


def enrich_with_demographics(df: pd.DataFrame) -> pd.DataFrame:
    """Join median_income from zip_demographics collection."""
    zip_data = list(db["zip_demographics"].find({}, {"_id": 0, "zip_code": 1, "median_income": 1}))
    if not zip_data:
        return df
    zip_df = pd.DataFrame(zip_data)
    df = df.merge(zip_df, on="zip_code", how="left")
    return df


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Clean, engineer features, and return (X, y) ready for model training.
    Drops rows missing required fields. Does not mutate the input.
    """
    df = df.copy()

    # --- filter required fields first ---
    df = df.dropna(subset=["price", "sqft", "beds", "baths"])
    df = df[df["price"] > 10_000]
    df = df[df["price"] < 10_000_000]
    df = df[df["sqft"] > 100]
    df = df[df["beds"] > 0]
    df = df[df["baths"] > 0]
    df = df.reset_index(drop=True)

    # --- target ---
    y = df["price"].astype(float)

    # --- sale year and month ---
    if "date_posted" in df.columns:
        dates = pd.to_datetime(df["date_posted"], errors="coerce")
        df["sale_year"] = dates.dt.year.astype("Int64")
        df["sale_month"] = dates.dt.month.astype("Int64")
    else:
        df["sale_year"] = pd.NA
        df["sale_month"] = pd.NA

    # --- age ---
    if "year_built" in df.columns:
        df["age"] = CURRENT_YEAR - pd.to_numeric(df["year_built"], errors="coerce")
        df["age"] = df["age"].clip(0, 200)
    else:
        df["age"] = np.nan

    # --- price_per_sqft (drop if present to avoid leakage) ---
    df = df.drop(columns=["price_per_sqft"], errors="ignore")

    # --- zip median income ---
    if "median_income" not in df.columns:
        df = enrich_with_demographics(df)
    df["median_income"] = pd.to_numeric(df.get("median_income"), errors="coerce")

    # --- property type encoding ---
    df["property_type"] = df["property_type"].str.lower().str.strip() if "property_type" in df.columns else "single family"
    for pt in PROPERTY_TYPE_CATEGORIES:
        df[f"type_{pt.replace(' ', '_')}"] = (df["property_type"] == pt).astype(int)

    # --- garage ---
    if "garage" in df.columns:
        df["has_garage"] = df["garage"].fillna(False).astype(int)
    else:
        df["has_garage"] = 0

    # --- zip code (label encoded) ---
    if "zip_code" in df.columns:
        df["zip_code"] = df["zip_code"].astype(str).str.zfill(5)
        zip_categories = sorted(df["zip_code"].dropna().unique())
        df["zip_encoded"] = pd.Categorical(df["zip_code"], categories=zip_categories).codes
        df["zip_encoded"] = df["zip_encoded"].replace(-1, pd.NA).astype("Int64")

    # --- final feature columns ---
    feature_cols = [
        "beds", "baths", "sqft", "age", "lot_sqft",
        "median_income", "zip_encoded", "has_garage",
        "sale_year", "sale_month",
        "type_single_family", "type_townhouse", "type_condo", "type_multi-family",
    ]
    feature_cols = [c for c in feature_cols if c in df.columns]

    X = df[feature_cols].copy()
    X = X.apply(pd.to_numeric, errors="coerce")

    # Fill remaining nulls with column medians
    X = X.fillna(X.median())

    return X, y

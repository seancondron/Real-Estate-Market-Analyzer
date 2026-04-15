import pandas as pd
import numpy as np
from backend.db.schema import DFW_CITIES, RESIDENTIAL_TYPES
from backend.db.mongodb import db

CURRENT_YEAR = 2026

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
    """Join median_income and population from zip_demographics collection."""
    zip_data = list(db["zip_demographics"].find({}, {"_id": 0, "zip_code": 1, "median_income": 1, "population": 1}))
    if not zip_data:
        return df
    zip_df = pd.DataFrame(zip_data)
    df = df.merge(zip_df, on="zip_code", how="left")
    return df


def enrich_with_crime(df: pd.DataFrame) -> pd.DataFrame:
    """Join violent/property crime rates from crime_stats (city-level, most recent year per city)."""
    crime_data = list(db["crime_stats"].find(
        {"state": "TX"},
        {"_id": 0, "city": 1, "year": 1, "violent_crime_rate": 1, "property_crime_rate": 1}
    ))
    if not crime_data:
        return df
    crime_df = pd.DataFrame(crime_data)
    # Keep most recent year per city to avoid row explosion on merge
    crime_df = crime_df.sort_values("year", ascending=False).drop_duplicates(subset=["city"])
    crime_df = crime_df[["city", "violent_crime_rate", "property_crime_rate"]]
    crime_df["city"] = crime_df["city"].str.lower().str.strip()
    df = df.copy()
    city_lower = df["city"].str.lower().str.strip() if "city" in df.columns else pd.Series("", index=df.index)
    df = df.merge(crime_df, left_on=city_lower, right_on="city", how="left", suffixes=("", "_crime"))
    df = df.drop(columns=["city_crime"], errors="ignore")
    return df


def enrich_with_district_ratings(df: pd.DataFrame) -> pd.DataFrame:
    """Join district_score and rating_num from district_ratings collection (city-level)."""
    data = list(db["district_ratings"].find({}, {"_id": 0, "city": 1, "district_score": 1, "rating_num": 1}))
    if not data:
        return df
    dist_df = pd.DataFrame(data)
    dist_df["city"] = dist_df["city"].str.lower().str.strip()
    df = df.copy()
    city_lower = df["city"].str.lower().str.strip() if "city" in df.columns else pd.Series("", index=df.index)
    df = df.merge(dist_df, left_on=city_lower, right_on="city", how="left", suffixes=("", "_dist"))
    df = df.drop(columns=["city_dist"], errors="ignore")
    return df


def enrich_with_mortgage_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Join monthly 30-year fixed mortgage rate from mortgage_rates collection."""
    data = list(db["mortgage_rates"].find({}, {"_id": 0, "year": 1, "month": 1, "mortgage_rate_30y": 1}))
    if not data:
        return df
    rate_df = pd.DataFrame(data)
    df = df.copy()
    df = df.merge(rate_df, left_on=["sale_year", "sale_month"], right_on=["year", "month"], how="left")
    df = df.drop(columns=["year", "month"], errors="ignore")
    return df


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Clean, engineer features, and return (X, y) ready for model training.
    Drops rows missing required fields. Does not mutate input.
    """
    df = df.copy()

    # --- filter required fields first ---
    df = df.dropna(subset=["price", "sqft"])
    df = df[df["price"] > 10_000]
    df = df[df["price"] < 10_000_000]
    df = df[df["sqft"] > 100]
    df = df.reset_index(drop=True)

    # Impute beds/baths from sqft when missing (CAD sources don't always include them)
    sqft_tmp = pd.to_numeric(df["sqft"], errors="coerce")
    if "beds" not in df.columns:
        df["beds"] = pd.NA
    if "baths" not in df.columns:
        df["baths"] = pd.NA
    beds_null = df["beds"].isna() | (pd.to_numeric(df["beds"], errors="coerce") <= 0)
    baths_null = df["baths"].isna() | (pd.to_numeric(df["baths"], errors="coerce") <= 0)
    # Sqft-based imputation: roughly 1 bed per 600 sqft, capped at 6
    df.loc[beds_null, "beds"] = (sqft_tmp[beds_null] / 600).clip(1, 6).round().astype("Int64")
    df.loc[baths_null, "baths"] = (sqft_tmp[baths_null] / 800).clip(1, 5).round(1)

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

    # --- zip demographics (median_income, population) ---
    if "median_income" not in df.columns:
        df = enrich_with_demographics(df)
    df["median_income"] = pd.to_numeric(df.get("median_income"), errors="coerce")
    df["population"] = pd.to_numeric(df.get("population"), errors="coerce")

    # --- city crime rates ---
    if "violent_crime_rate" not in df.columns:
        df = enrich_with_crime(df)
    df["violent_crime_rate"] = pd.to_numeric(df.get("violent_crime_rate"), errors="coerce")
    df["property_crime_rate"] = pd.to_numeric(df.get("property_crime_rate"), errors="coerce")

    # --- mortgage rates (time-series join on sale_year + sale_month) ---
    if "mortgage_rate_30y" not in df.columns:
        df = enrich_with_mortgage_rates(df)
    df["mortgage_rate_30y"] = pd.to_numeric(df.get("mortgage_rate_30y"), errors="coerce")

    # --- school district ratings ---
    if "district_score" not in df.columns:
        df = enrich_with_district_ratings(df)
    df["district_score"] = pd.to_numeric(df.get("district_score"), errors="coerce")
    df["district_rating_num"] = pd.to_numeric(df.get("rating_num"), errors="coerce")

    # --- property type encoding ---
    # Kaggle dataset stores listing status ("for_sale", "sold") instead of home type — normalize to "single family"
    LISTING_STATUS_VALUES = {"for_sale", "sold", "for sale", "ready_to_build"}
    if "property_type" in df.columns:
        pt_col = df["property_type"].str.lower().str.strip()
        df["property_type"] = pt_col.where(~pt_col.isin(LISTING_STATUS_VALUES), "single family")
    else:
        df["property_type"] = "single family"
    for pt in PROPERTY_TYPE_CATEGORIES:
        df[f"type_{pt.replace(' ', '_')}"] = (df["property_type"] == pt).astype(int)

    # --- garage ---
    if "garage" in df.columns:
        df["has_garage"] = df["garage"].fillna(False).astype(int)
    else:
        df["has_garage"] = 0

    # --- pool ---
    if "has_pool" in df.columns:
        df["has_pool"] = df["has_pool"].fillna(False).astype(int)
    else:
        df["has_pool"] = 0

    # --- city-level target encoding (broader location signal) ---
    if "city" in df.columns:
        global_mean_city = y.mean()
        smoothing_city = 20
        city_lower = df["city"].str.lower().str.strip()
        city_stats = y.groupby(city_lower).agg(["mean", "count"])
        city_target = (city_stats["count"] * city_stats["mean"] + smoothing_city * global_mean_city) / (city_stats["count"] + smoothing_city)
        df["city_encoded"] = city_lower.map(city_target).fillna(global_mean_city)

    # --- zip code (target encoded: smoothed mean price per zip) ---
    if "zip_code" in df.columns:
        df["zip_code"] = df["zip_code"].astype(str).str.zfill(5)
        global_mean = y.mean()
        smoothing = 10
        zip_stats = y.groupby(df["zip_code"]).agg(["mean", "count"])
        zip_target = (zip_stats["count"] * zip_stats["mean"] + smoothing * global_mean) / (zip_stats["count"] + smoothing)
        df["zip_encoded"] = df["zip_code"].map(zip_target).fillna(global_mean)

    # --- log-scale size features ---
    df["log_sqft"] = np.log1p(pd.to_numeric(df["sqft"], errors="coerce"))
    if "lot_sqft" in df.columns:
        df["log_lot_sqft"] = np.log1p(pd.to_numeric(df["lot_sqft"], errors="coerce"))

    # --- interaction features ---
    sqft_num = pd.to_numeric(df["sqft"], errors="coerce")
    beds_num = pd.to_numeric(df["beds"], errors="coerce")
    baths_num = pd.to_numeric(df["baths"], errors="coerce")
    df["sqft_per_bed"] = (sqft_num / beds_num.replace(0, np.nan)).fillna(sqft_num)
    df["bath_bed_ratio"] = (baths_num / beds_num.replace(0, np.nan)).fillna(1.0)
    df["total_rooms"] = beds_num + baths_num
    df["income_per_sqft"] = df["median_income"] / sqft_num.replace(0, np.nan)
    # Affordability proxy: rate × income signal (higher rate compresses purchasing power)
    df["rate_x_income"] = df["mortgage_rate_30y"] * df["median_income"]

    # --- relative size vs zip median (how big is this home for its zip) ---
    if "zip_code" in df.columns:
        zip_median_sqft = sqft_num.groupby(df["zip_code"]).transform("median")
        df["sqft_vs_zip_median"] = sqft_num / zip_median_sqft.replace(0, np.nan)

    # --- age squared (captures nonlinear depreciation) ---
    if "age" in df.columns:
        df["age_sq"] = df["age"] ** 2

    # --- final feature columns ---
    feature_cols = [
        "beds", "baths", "sqft", "log_sqft", "age", "age_sq", "lot_sqft", "log_lot_sqft",
        "sqft_per_bed", "bath_bed_ratio", "total_rooms", "income_per_sqft", "sqft_vs_zip_median",
        "median_income", "population", "zip_encoded", "city_encoded", "has_garage",
        "violent_crime_rate", "property_crime_rate", "has_pool",
        "district_score", "district_rating_num",
        "mortgage_rate_30y", "rate_x_income",
        "sale_year", "sale_month",
        "type_single_family", "type_townhouse", "type_condo", "type_multi-family",
    ]
    feature_cols = [c for c in feature_cols if c in df.columns]

    X = df[feature_cols].copy()
    X = X.apply(pd.to_numeric, errors="coerce")

    # Fill remaining nulls with column medians
    X = X.fillna(X.median())

    return X, y

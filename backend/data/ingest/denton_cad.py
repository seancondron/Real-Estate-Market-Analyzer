"""
Denton Central Appraisal District

Covers: Denton, Lewisville, Flower Mound, Carrollton, The Colony, Little Elm,
        Corinth, Highland Village, Argyle, Northlake, Justin, Krum, etc.

Usage:
    python3 -m backend.data.ingest.denton_cad --file /path/to/denton_residential.csv
"""

import argparse
from datetime import datetime, timezone

import pandas as pd

from backend.db.mongodb import db

# Prodigy CAD typical column names — adjust if your export differs
COLUMN_MAP = {
    # Address fields
    "SitusAddress":      "address",
    "SitusCity":         "city",
    "SitusZip":          "zip_code",
    # Value
    "AppraisedValue":    "price",
    "MarketValue":       "price",          # fallback if AppraisedValue missing
    # Improvement details
    "LivingArea":        "sqft",
    "LotSize":           "lot_sqft",
    "YearBuilt":         "year_built",
    "Bedrooms":          "beds",
    "Bathrooms":         "baths",
    "Stories":           "stories",
    "GarageCapacity":    "garage_spaces",
    "PoolFlag":          "has_pool",
    "Pool":              "has_pool",       # alternate name
    # Alternate naming conventions
    "SITUS_ADDRESS":     "address",
    "SITUS_CITY":        "city",
    "SITUS_ZIP":         "zip_code",
    "APPRAISED_VALUE":   "price",
    "LIVING_AREA":       "sqft",
    "LOT_SIZE":          "lot_sqft",
    "YEAR_BUILT":        "year_built",
    "BED_ROOMS":         "beds",
    "BATH_ROOMS":        "baths",
    "GARAGE_CAP":        "garage_spaces",
}


def ingest(file_path: str) -> None:
    print(f"Loading {file_path}...")
    df = pd.read_csv(file_path, low_memory=False, dtype=str)
    print(f"  Loaded {len(df):,} rows")
    print(f"  Columns: {list(df.columns[:20])}{'...' if len(df.columns) > 20 else ''}")

    # Apply column map (only rename columns that exist)
    rename = {k: v for k, v in COLUMN_MAP.items() if k in df.columns}
    df.rename(columns=rename, inplace=True)

    # If multiple source cols mapped to same target, keep first non-null
    if "price" not in df.columns:
        raise ValueError(
            f"Could not find a price column. Available columns: {list(df.columns)}\n"
            "Update COLUMN_MAP in denton_cad.py to match your export."
        )

    df["state"] = "TX"
    df["property_type"] = "single family"

    # Cast numerics
    for col in ["price", "sqft", "lot_sqft", "year_built", "stories"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "beds" in df.columns:
        df["beds"] = pd.to_numeric(df["beds"], errors="coerce").astype("Int64")
    else:
        df["beds"] = pd.NA

    if "baths" in df.columns:
        df["baths"] = pd.to_numeric(df["baths"], errors="coerce")
    else:
        df["baths"] = pd.NA

    if "garage_spaces" in df.columns:
        df["garage"] = pd.to_numeric(df["garage_spaces"], errors="coerce") > 0
    else:
        df["garage"] = None

    if "has_pool" in df.columns:
        df["has_pool"] = df["has_pool"].map(
            lambda v: True if str(v).strip().upper() in ("TRUE", "T", "1", "YES", "Y") else False
        )
    else:
        df["has_pool"] = False

    if "zip_code" in df.columns:
        df["zip_code"] = df["zip_code"].astype(str).str.strip().str[:5].str.zfill(5)

    df = df.dropna(subset=["address", "city", "zip_code", "price", "sqft"])
    df = df[df["price"] > 50_000]
    df = df[df["sqft"] > 200]
    print(f"  After filtering: {len(df):,} records")

    now = datetime.now(timezone.utc).isoformat()
    df["ingested_at"] = now
    df["source"] = "denton_cad"

    keep_cols = ["address", "city", "state", "zip_code", "price", "sqft", "lot_sqft",
                 "year_built", "beds", "baths", "stories", "garage", "has_pool",
                 "property_type", "ingested_at", "source"]
    df = df[[c for c in keep_cols if c in df.columns]]

    collection = db["properties"]
    inserted = skipped = 0

    for doc in df.to_dict("records"):
        doc = {k: (None if pd.isna(v) else v) for k, v in doc.items()}
        result = collection.update_one(
            {"address": doc["address"], "city": doc["city"], "state": doc["state"]},
            {"$setOnInsert": doc},
            upsert=True,
        )
        if result.upserted_id:
            inserted += 1
        else:
            skipped += 1

    print(f"Done — inserted: {inserted:,}, skipped (duplicates): {skipped:,}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Denton CAD residential data")
    parser.add_argument("--file", required=True, help="Path to Denton CAD residential CSV export")
    args = parser.parse_args()
    ingest(args.file)

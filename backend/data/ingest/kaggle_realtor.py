"""
Kaggle - USA Real Estate Dataset
Source: https://www.kaggle.com/datasets/ahmedshahriarsakib/usa-real-estate-dataset
Download: realtor-data.zip.csv  (or realtor-data.csv)

Usage:
    python3 -m backend.data.ingest.kaggle_realtor --file /path/to/realtor-data.csv
"""

import argparse
from datetime import datetime, timezone

import pandas as pd

from backend.db.mongodb import db
from backend.data.processor import filter_dfw_homes

COLUMN_MAP = {
    "price":          "price",
    "bed":            "beds",
    "bath":           "baths",
    "house_size":     "sqft",
    "acre_lot":       "lot_sqft",
    "street":         "address",
    "city":           "city",
    "state":          "state",
    "zip_code":       "zip_code",
    "status":         "listing_type",
    "prev_sold_date": "date_posted",
}

RESIDENTIAL_TYPES = {"single family", "townhouse", "condo", "multi-family", "for_sale", "for sale"}


def ingest(file_path: str) -> None:
    print(f"Loading {file_path}...")
    df = pd.read_csv(file_path, low_memory=False)

    # Normalize column names (lowercase + strip) then rename to internal names
    df.columns = df.columns.str.lower().str.strip()
    df.rename(columns=COLUMN_MAP, inplace=True)

    # Filter to Texas before anything else (Kaggle uses full state names e.g. "Texas")
    if "state" in df.columns:
        df = df[df["state"].str.lower() == "texas"]

    # Normalize address to string (Kaggle uses numeric parcel IDs, not street addresses)
    if "address" in df.columns:
        df["address"] = df["address"].apply(lambda v: str(int(v)) if isinstance(v, float) and not pd.isna(v) else str(v) if pd.notna(v) else None)

    # Convert acre_lot → sqft
    if "lot_sqft" in df.columns:
        df["lot_sqft"] = (df["lot_sqft"] * 43_560).round().astype("Int64")

    # Filter to DFW residential homes
    df = filter_dfw_homes(df)

    # Cast types
    df["price"]    = pd.to_numeric(df["price"], errors="coerce")
    df["beds"]     = pd.to_numeric(df.get("beds"), errors="coerce").astype("Int64")
    df["baths"]    = pd.to_numeric(df.get("baths"), errors="coerce")
    df["sqft"]     = pd.to_numeric(df.get("sqft"), errors="coerce").astype("Int64")
    df["zip_code"] = pd.to_numeric(df["zip_code"], errors="coerce").dropna().astype(int).astype(str).str.zfill(5)
    df["zip_code"] = df["zip_code"].reindex(df.index)

    # Drop rows missing required fields
    df.dropna(subset=["address", "city", "state", "zip_code", "price"], inplace=True)

    df["state"] = "TX"

    now = datetime.now(timezone.utc).isoformat()
    df["ingested_at"] = now
    df["property_type"] = df.get("listing_type", "single family")

    inserted = 0
    skipped = 0
    collection = db["properties"]

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

    print(f"Done - inserted: {inserted}, skipped (duplicates): {skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to realtor-data.csv")
    args = parser.parse_args()
    ingest(args.file)

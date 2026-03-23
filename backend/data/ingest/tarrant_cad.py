"""
Tarrant Appraisal District - Residential Property Records
Source: https://www.tad.org/data-downloads/
Download: Request residential export (CSV) from tad.org

Usage:
    python3 -m backend.data.ingest.tarrant_cad --file /path/to/tad_residential.csv
"""

import argparse
from datetime import datetime, timezone

import pandas as pd

from backend.db.mongodb import db

# Tarrant CAD column names - adjust if your export differs
COLUMN_MAP = {
    "SitusAddress":    "address",
    "SitusCity":       "city",
    "SitusZip":        "zip_code",
    "AppraisedValue":  "price",
    "LivingArea":      "sqft",
    "LotSize":         "lot_sqft",
    "YearBuilt":       "year_built",
    "Bedrooms":        "beds",
    "Bathrooms":       "baths",
    "Stories":         "stories",
    "GarageCapacity":  "garage_spaces",
}


def ingest(file_path: str) -> None:
    print(f"Loading {file_path}...")
    df = pd.read_csv(file_path, low_memory=False, dtype=str)
    df.rename(columns=COLUMN_MAP, inplace=True)

    df["state"] = "TX"
    df["property_type"] = "single family"

    # Cast numerics
    for col in ["price", "sqft", "lot_sqft", "year_built", "stories"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "beds" in df.columns:
        df["beds"] = pd.to_numeric(df["beds"], errors="coerce").astype("Int64")
    if "baths" in df.columns:
        df["baths"] = pd.to_numeric(df["baths"], errors="coerce")
    if "garage_spaces" in df.columns:
        df["garage"] = df["garage_spaces"].notna() & (pd.to_numeric(df["garage_spaces"], errors="coerce") > 0)

    df["zip_code"] = df["zip_code"].astype(str).str.strip().str[:5].str.zfill(5)
    df.dropna(subset=["address", "city", "zip_code", "price"], inplace=True)

    now = datetime.now(timezone.utc).isoformat()
    df["ingested_at"] = now

    inserted = 0
    skipped = 0
    collection = db["properties"]

    for doc in df.to_dict("records"):
        doc = {k: (None if pd.isna(v) else v) for k, v in doc.items() if k != "garage_spaces"}
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
    parser.add_argument("--file", required=True, help="Path to TAD residential CSV")
    args = parser.parse_args()
    ingest(args.file)

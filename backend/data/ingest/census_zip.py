"""
US Census Bureau — ACS 5-Year Estimates (Zip Code Demographics)
Source: https://data.census.gov
Download:
  1. Go to data.census.gov
  2. Search "S1901" (income) and "S0101" (population) → Filter by Texas zip codes
  3. Download as CSV

Or use the direct ACS table downloads:
  https://www.census.gov/acs/www/data/data-tables-and-tools/

Expected CSV columns (ACS S1901 / S0101 combined or separate):
  - zip_code (or GEO_ID)
  - median_income
  - population

Usage:
    python3 -m backend.data.ingest.census_zip --file /path/to/acs_zip_data.csv
"""

import argparse
from datetime import datetime, timezone

import pandas as pd

from backend.db.mongodb import db
from backend.db.schema import DFW_CITIES

# DFW zip codes (common ones — Census data is keyed by zip, not city)
# The script filters by matching zips that appear in DFW properties already ingested
COLUMN_MAP = {
    "zip_code":      "zip_code",
    "ZIP":           "zip_code",
    "ZCTA":          "zip_code",
    "median_income": "median_income",
    "MedianIncome":  "median_income",
    "population":    "population",
    "Population":    "population",
}


def ingest(file_path: str) -> None:
    print(f"Loading {file_path}...")
    df = pd.read_csv(file_path, low_memory=False, dtype=str)

    # Normalize column names
    df.rename(columns={c: COLUMN_MAP[c] for c in df.columns if c in COLUMN_MAP}, inplace=True)

    if "zip_code" not in df.columns:
        raise ValueError("Could not find a zip code column. Expected: zip_code, ZIP, or ZCTA")

    df["zip_code"] = df["zip_code"].astype(str).str.strip().str.zfill(5)

    # Only keep zips already in our properties collection (i.e. DFW)
    existing_zips = db["properties"].distinct("zip_code")
    df = df[df["zip_code"].isin(existing_zips)]

    if "median_income" in df.columns:
        df["median_income"] = pd.to_numeric(df["median_income"], errors="coerce").astype("Int64")
    if "population" in df.columns:
        df["population"] = pd.to_numeric(df["population"], errors="coerce").astype("Int64")

    now = datetime.now(timezone.utc).isoformat()
    df["enriched_at"] = now

    inserted = 0
    skipped = 0
    collection = db["zip_demographics"]

    for doc in df[["zip_code", "median_income", "population", "enriched_at"]].to_dict("records"):
        doc = {k: (None if pd.isna(v) else v) for k, v in doc.items()}
        result = collection.update_one(
            {"zip_code": doc["zip_code"]},
            {"$set": doc},
            upsert=True,
        )
        if result.upserted_id:
            inserted += 1
        else:
            skipped += 1

    print(f"Done — inserted: {inserted}, updated: {skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to Census ACS CSV")
    args = parser.parse_args()
    ingest(args.file)

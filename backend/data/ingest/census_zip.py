"""
US Census Bureau - ACS 5-Year Estimates (Zip Code Demographics)
Source: https://data.census.gov
Download:
  1. Go to data.census.gov
  2. Search "S1901"
  3. Under Geography, select Zip Code Tabulation Area (ZCTA) → All ZCTAs in Texas
  4. Download as CSV

Expected format: ACS S1901 export with GEO_ID column (e.g. "860Z200US75001")

Usage:
    python3 -m backend.data.ingest.census_zip --file /path/to/ACSST5Y2024.S1901-Data.csv
"""

import argparse
from datetime import datetime, timezone

import pandas as pd

from backend.db.mongodb import db

# ACS S1901 column codes
ACS_COL_MAP = {
    "S1901_C01_012E": "median_income",  # Estimate: Households: Median income (dollars)
    "S1901_C01_001E": "population",     # Estimate: Households: Total
}


def ingest(file_path: str) -> None:
    print(f"Loading {file_path}...")
    # Row 0 is column codes, row 1 is human-readable labels - skip row 1
    df = pd.read_csv(file_path, low_memory=False, dtype=str, skiprows=[1])

    # Extract zip code from GEO_ID e.g. "860Z200US75001" → "75001"
    if "GEO_ID" not in df.columns:
        raise ValueError("Could not find GEO_ID column in Census file")
    df["zip_code"] = df["GEO_ID"].str.extract(r"(\d{5})$")

    # Rename ACS columns to internal names
    df.rename(columns=ACS_COL_MAP, inplace=True)

    df = df.dropna(subset=["zip_code"])

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

    print(f"Done - inserted: {inserted}, updated: {skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to Census ACS CSV")
    args = parser.parse_args()
    ingest(args.file)

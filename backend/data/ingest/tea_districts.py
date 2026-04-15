"""
Texas Education Agency (TEA) - 2025 District Accountability Summary
Source: Texas Education Agency accountability ratings CSV

Columns used:
  DISTNAME  - district name (e.g. "DALLAS ISD", "HURST-EULESS-BEDFORD ISD")
  CNTYNAME  - county name (e.g. "DALLAS", "TARRANT")
  D_RATING  - letter grade: A/B/C/D/F/Not Rated
  DDALLS    - overall numeric score 0-100

Inserts/updates a `district_ratings` collection keyed on city (lower-case).
One row per city extracted from the district name. Multi-city districts
(e.g. "HURST-EULESS-BEDFORD ISD") produce one row per city, all sharing
the same score.

Usage:
    python3 -m backend.data.ingest.tea_districts --file ~/Desktop/"2025 District Accountability Summary.csv"
"""

import argparse
import re
from datetime import datetime, timezone

import pandas as pd

from backend.db.mongodb import db

# DFW county names as they appear in CNTYNAME column
DFW_COUNTIES = {
    "COLLIN", "DALLAS", "DENTON", "TARRANT", "ROCKWALL",
    "KAUFMAN", "ELLIS", "JOHNSON", "PARKER", "WISE",
}

RATING_TO_NUM = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}

# Suffixes to strip from district names to get city names
SUFFIXES = re.compile(
    r"\s+(ISD|CISD|MSD|ISO|SCHOOL DISTRICT|CONSOLIDATED ISD|INDEPENDENT SCHOOL DISTRICT)$",
    re.IGNORECASE,
)


def parse_cities(distname: str) -> list[str]:
    """
    Extract one or more city names from a district name.
    'HURST-EULESS-BEDFORD ISD' → ['hurst', 'euless', 'bedford']
    'DALLAS ISD' → ['dallas']
    'GRAND PRAIRIE ISD' → ['grand prairie']
    """
    name = SUFFIXES.sub("", distname.strip())
    # Split on hyphen only if each part looks like a single word (not "GRAND PRAIRIE")
    parts = name.split("-")
    cities = []
    for part in parts:
        city = part.strip().lower()
        if city:
            cities.append(city)
    return cities


def ingest(file_path: str) -> None:
    print(f"Loading {file_path}...")
    df = pd.read_csv(file_path, dtype=str)
    print(f"  Loaded {len(df)} rows, columns: {list(df.columns)}")

    # Filter to DFW counties
    df = df[df["CNTYNAME"].str.upper().isin(DFW_COUNTIES)].copy()
    print(f"  DFW rows: {len(df)}")

    if df.empty:
        print("No DFW rows found. Check CNTYNAME column values.")
        return

    collection = db["district_ratings"]
    inserted = updated = skipped = 0
    now = datetime.now(timezone.utc).isoformat()

    for _, row in df.iterrows():
        distname = str(row.get("DISTNAME", "")).strip()
        d_rating = str(row.get("D_RATING", "")).strip()
        ddalls_raw = row.get("DDALLS", None)

        try:
            ddalls = float(ddalls_raw) if ddalls_raw and str(ddalls_raw).strip() not in ("", ".", "nan") else None
        except (TypeError, ValueError):
            ddalls = None

        rating_num = RATING_TO_NUM.get(d_rating.upper())

        cities = parse_cities(distname)
        if not cities:
            continue

        for city in cities:
            doc = {
                "city": city,
                "district_name": distname,
                "county": str(row.get("CNTYNAME", "")).strip().upper(),
                "d_rating": d_rating if d_rating else None,
                "rating_num": rating_num,
                "district_score": ddalls,
                "enriched_at": now,
            }
            result = collection.update_one(
                {"city": city},
                {"$set": doc},
                upsert=True,
            )
            if result.upserted_id:
                inserted += 1
            elif result.modified_count:
                updated += 1
            else:
                skipped += 1

    print(f"\nDone — inserted: {inserted}, updated: {updated}, unchanged: {skipped}")

    # Show sample of what was ingested
    sample = list(collection.find({}, {"_id": 0, "city": 1, "d_rating": 1, "district_score": 1}).limit(10))
    print("Sample records:")
    for s in sample:
        print(f"  {s['city']}: {s.get('d_rating')} / {s.get('district_score')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest TEA district accountability ratings for DFW")
    parser.add_argument("--file", required=True, help="Path to '2025 District Accountability Summary.csv'")
    args = parser.parse_args()
    ingest(args.file)

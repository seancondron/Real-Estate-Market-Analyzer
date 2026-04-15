

import argparse
from datetime import datetime, timezone

import requests
import pandas as pd

from backend.db.mongodb import db

SOCRATA_BASE = "https://data.texas.gov/resource/vtby-uz4n.json"
PAGE_SIZE = 50_000

# Texas DFW cities in Collin County
COLLIN_CITIES = {
    "allen", "anna", "celina", "farmersville", "frisco", "garland",
    "lavon", "lowry crossing", "lucas", "mckinney", "melissa",
    "murphy", "nevada", "new hope", "parker", "plano", "princeton",
    "prosper", "richardson", "royse city", "sachse", "st paul",
    "van alstyne", "weston", "wylie",
}


def fetch_all(year: int, limit: int) -> list[dict]:
    """Page through Socrata API and return all residential records."""
    records = []
    offset = 0
    where = f"propsubtype='Residential' AND propyear='{year}' AND imprvmainarea > '0'"
    print(f"Downloading Collin CAD {year} residential data...")

    while True:
        params = {
            "$where": where,
            "$limit": PAGE_SIZE,
            "$offset": offset,
            "$select": (
                "situsbldgnum,situsstreetname,situsstreetsuffix,situsunit,"
                "situsconcat,situscity,situszip,"
                "imprvmainarea,imprvyearbuilt,imprvpoolflag,"
                "landsizesqft,currvalappraised"
            ),
        }
        resp = requests.get(SOCRATA_BASE, params=params, timeout=60)
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        records.extend(page)
        offset += PAGE_SIZE
        print(f"  Fetched {len(records):,} rows...", end="\r")
        if limit and len(records) >= limit:
            records = records[:limit]
            break
        if len(page) < PAGE_SIZE:
            break

    print(f"\n  Total rows fetched: {len(records):,}")
    return records


def ingest(year: int = 2022, limit: int = 0) -> None:
    raw = fetch_all(year, limit)
    if not raw:
        print("No records returned.")
        return

    df = pd.DataFrame(raw)

    # --- address ---
    df["address"] = (
        df.get("situsbldgnum", pd.Series("", index=df.index)).fillna("").str.strip()
        + " "
        + df.get("situsstreetname", pd.Series("", index=df.index)).fillna("").str.strip()
        + " "
        + df.get("situsstreetsuffix", pd.Series("", index=df.index)).fillna("").str.strip()
    ).str.strip()

    # Fall back to full concat if address is blank
    if "situsconcat" in df.columns:
        blank = df["address"].str.strip() == ""
        df.loc[blank, "address"] = df.loc[blank, "situsconcat"].fillna("").str.strip()

    df["city"] = df.get("situscity", pd.Series("", index=df.index)).fillna("").str.strip().str.title()
    df["zip_code"] = df.get("situszip", pd.Series("", index=df.index)).fillna("").astype(str).str.strip().str.zfill(5)
    df["state"] = "TX"
    df["property_type"] = "single family"

    # --- numerics ---
    df["price"] = pd.to_numeric(df.get("currvalappraised"), errors="coerce")
    df["sqft"] = pd.to_numeric(df.get("imprvmainarea"), errors="coerce")
    df["lot_sqft"] = pd.to_numeric(df.get("landsizesqft"), errors="coerce")
    df["year_built"] = pd.to_numeric(df.get("imprvyearbuilt"), errors="coerce").astype("Int64")

    # Pool flag — new feature not in existing data
    pool_raw = df.get("imprvpoolflag", pd.Series(False, index=df.index))
    df["has_pool"] = pool_raw.map(lambda v: True if str(v).lower() in ("true", "1", "yes") else False)

    # No beds/baths in PTAD public export — left as null, imputed in build_features
    df["beds"] = pd.NA
    df["baths"] = pd.NA

    # --- filter ---
    df = df.dropna(subset=["address", "city", "zip_code", "price", "sqft"])
    df = df[df["price"] > 50_000]
    df = df[df["sqft"] > 200]
    print(f"  After filtering: {len(df):,} records")

    now = datetime.now(timezone.utc).isoformat()
    df["ingested_at"] = now
    df["source"] = f"collin_cad_{year}"

    collection = db["properties"]
    inserted = skipped = 0

    keep_cols = ["address", "city", "state", "zip_code", "price", "sqft", "lot_sqft",
                 "year_built", "has_pool", "beds", "baths", "property_type", "ingested_at", "source"]
    df = df[[c for c in keep_cols if c in df.columns]]

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
    parser = argparse.ArgumentParser(description="Ingest Collin CAD residential data via Texas Open Data Portal")
    parser.add_argument("--year", type=int, default=2022, help="Appraisal year (default: 2022)")
    parser.add_argument("--limit", type=int, default=0, help="Row limit for testing (0 = all)")
    args = parser.parse_args()
    ingest(year=args.year, limit=args.limit)

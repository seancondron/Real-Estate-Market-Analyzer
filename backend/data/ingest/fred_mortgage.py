"""
FRED - 30-Year Fixed Mortgage Rate (MORTGAGE30US)
Source: Federal Reserve Bank of St. Louis

Fetches weekly 30-year fixed mortgage rates, computes monthly averages,
and upserts into the `mortgage_rates` collection keyed on (year, month).

Usage:
    python3 -m backend.data.ingest.fred_mortgage
"""

from datetime import datetime, timezone

import pandas as pd
import requests

from backend.db.mongodb import db

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"


def ingest() -> None:
    print("Downloading FRED MORTGAGE30US series...")
    resp = requests.get(FRED_URL, timeout=30)
    resp.raise_for_status()

    from io import StringIO
    df = pd.read_csv(StringIO(resp.text))
    df.columns = ["date", "rate"]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
    df = df.dropna(subset=["rate"])

    print(f"  Downloaded {len(df)} weekly observations ({df['date'].min().date()} → {df['date'].max().date()})")

    # Monthly averages
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    monthly = df.groupby(["year", "month"])["rate"].mean().reset_index()
    monthly["rate"] = monthly["rate"].round(3)
    print(f"  Computed {len(monthly)} monthly averages")

    collection = db["mortgage_rates"]
    inserted = updated = skipped = 0
    now = datetime.now(timezone.utc).isoformat()

    for _, row in monthly.iterrows():
        doc = {
            "year": int(row["year"]),
            "month": int(row["month"]),
            "mortgage_rate_30y": float(row["rate"]),
            "enriched_at": now,
        }
        result = collection.update_one(
            {"year": doc["year"], "month": doc["month"]},
            {"$set": doc},
            upsert=True,
        )
        if result.upserted_id:
            inserted += 1
        elif result.modified_count:
            updated += 1
        else:
            skipped += 1

    print(f"Done — inserted: {inserted}, updated: {updated}, unchanged: {skipped}")

    # Show a few notable periods
    sample_years = [1981, 2000, 2008, 2020, 2022]
    for yr in sample_years:
        rows = monthly[monthly["year"] == yr]
        if not rows.empty:
            avg = rows["rate"].mean()
            print(f"  {yr} avg rate: {avg:.2f}%")


if __name__ == "__main__":
    ingest()

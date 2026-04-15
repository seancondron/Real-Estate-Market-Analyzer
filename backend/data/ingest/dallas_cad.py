"""
Dallas Central Appraisal District
Source: https://www.dallascad.org/AcctDetailRes.aspx (bulk export)

Usage:
    python3 -m backend.data.ingest.dallas_cad \
        --account /path/to/ACCOUNT_APPRL_YEAR.csv \
        --res     /path/to/RES_DETAIL.csv
"""

import argparse
from datetime import datetime, timezone

import pandas as pd

from backend.db.mongodb import db

# Dallas CAD column names vary by export year - adjust if needed
ACCOUNT_COL_MAP = {
    "ACCOUNT_NUM":   "account_num",
    "SITUS_NUM":     "street_num",
    "SITUS_STREET":  "street_name",
    "SITUS_APT":     "unit",
    "SITUS_CITY":    "city",
    "SITUS_ZIP":     "zip_code",
    "APPRAISED_VAL": "price",
}

RES_COL_MAP = {
    "ACCOUNT_NUM":  "account_num",
    "LIVING_AREA":  "sqft",
    "BED_RMS":      "beds",
    "BATH":         "baths",
    "YEAR_BUILT":   "year_built",
    "NUM_STORY":    "stories",
    "GAR_CAPACITY": "garage_spaces",
    "LOT_SIZE":     "lot_sqft",
}


def ingest(account_file: str, res_file: str) -> None:
    print("Loading Dallas CAD account file...")
    acct = pd.read_csv(account_file, low_memory=False, dtype=str)
    acct.rename(columns=ACCOUNT_COL_MAP, inplace=True)
    acct = acct[[c for c in ACCOUNT_COL_MAP.values() if c in acct.columns]]

    print("Loading Dallas CAD residential detail file...")
    res = pd.read_csv(res_file, low_memory=False, dtype=str)
    res.rename(columns=RES_COL_MAP, inplace=True)
    res = res[[c for c in RES_COL_MAP.values() if c in res.columns]]

    df = acct.merge(res, on="account_num", how="inner")

    # Build address
    df["address"] = (
        df.get("street_num", "").fillna("").str.strip()
        + " "
        + df.get("street_name", "").fillna("").str.strip()
        + df.get("unit", "").fillna("").apply(lambda u: f" #{u}" if u else "")
    ).str.strip()

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

    df["zip_code"] = df["zip_code"].astype(str).str.strip().str.zfill(5)
    df.dropna(subset=["address", "city", "zip_code", "price"], inplace=True)

    now = datetime.now(timezone.utc).isoformat()
    df["ingested_at"] = now

    inserted = 0
    skipped = 0
    collection = db["properties"]

    for doc in df.to_dict("records"):
        doc = {k: (None if pd.isna(v) else v) for k, v in doc.items() if k != "account_num"}
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
    parser.add_argument("--account", required=True, help="Path to ACCOUNT_APPRL_YEAR.csv")
    parser.add_argument("--res",     required=True, help="Path to RES_DETAIL.csv")
    args = parser.parse_args()
    ingest(args.account, args.res)

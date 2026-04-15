"""
FBI Crime Data Explorer - City-Level Crime Rates for DFW


Fetches violent and property crime rates per 100k population for each DFW city,
then upserts into the crime_stats collection keyed on (city, state, year).

Usage:
    python3 -m backend.data.ingest.fbi_crime --api-key YOUR_KEY [--years 2019,2020,2021,2022,2023]
"""

import argparse
import time
from datetime import datetime, timezone

import requests

from backend.db.mongodb import db
from backend.db.schema import DFW_CITIES

BASE_URL = "https://cde.fbi.gov/api"
REQUEST_DELAY = 0.3  # seconds between API calls to avoid rate limiting


def get(url: str, api_key: str, params: dict = None) -> dict | list | None:
    headers = {"X-API-Key": api_key}
    try:
        resp = requests.get(url, headers=headers, params=params or {}, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError as e:
        print(f"  HTTP {e.response.status_code} for {url}")
        return None
    except Exception as e:
        print(f"  Request failed: {e}")
        return None


def fetch_tx_agencies(api_key: str) -> list[dict]:
    """Return all law enforcement agencies in Texas."""
    print("Fetching Texas agencies from FBI CDE...")
    data = get(f"{BASE_URL}/agency/byStateAbbr/TX", api_key)
    if not data:
        raise RuntimeError("Failed to fetch TX agencies. Check your API key.")
    agencies = data if isinstance(data, list) else data.get("results", [])
    print(f"  Found {len(agencies)} agencies in TX")
    return agencies


def filter_dfw_agencies(agencies: list[dict]) -> list[dict]:
    """Keep only agencies whose city is in DFW_CITIES."""
    dfw = []
    for a in agencies:
        city = (a.get("city_name") or a.get("city") or "").strip().lower()
        if city in DFW_CITIES and a.get("ori"):
            dfw.append({"ori": a["ori"], "city": city, "agency_name": a.get("agency_name", "")})
    print(f"  Matched {len(dfw)} DFW agencies")
    return dfw


def fetch_agency_crime(ori: str, year: int, api_key: str) -> dict | None:
    """Fetch summarized offense counts for one agency and year."""
    url = f"{BASE_URL}/summarized/agencies/{ori}/all-offenses/{year}/{year}"
    data = get(url, api_key)
    if not data:
        return None
    results = data if isinstance(data, list) else data.get("results", data.get("data", []))
    if not results:
        return None
    # API returns a list; grab the entry matching our year
    for row in results:
        if str(row.get("year", "")) == str(year):
            return row
    return results[0] if results else None


def safe_int(val) -> int | None:
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def safe_float(val) -> float | None:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def ingest(api_key: str, years: list[int]) -> None:
    agencies = fetch_tx_agencies(api_key)
    dfw_agencies = filter_dfw_agencies(agencies)

    if not dfw_agencies:
        print("No DFW agencies found. Verify DFW_CITIES matches FBI city name spellings.")
        return

    # city → year → aggregated stats (sum counts, weighted average rates)
    city_year_data: dict[tuple, dict] = {}

    total = len(dfw_agencies) * len(years)
    done = 0

    for agency in dfw_agencies:
        ori = agency["ori"]
        city = agency["city"]

        for year in years:
            done += 1
            print(f"  [{done}/{total}] {city} / {agency['agency_name']} ({year})", end="\r")

            row = fetch_agency_crime(ori, year, api_key)
            time.sleep(REQUEST_DELAY)

            if not row:
                continue

            pop = safe_int(row.get("population"))
            key = (city, year)

            if key not in city_year_data:
                city_year_data[key] = {
                    "city": city,
                    "state": "TX",
                    "year": year,
                    "population": 0,
                    "violent_crime_total": 0,
                    "property_crime_total": 0,
                    "murder": 0,
                    "rape": 0,
                    "robbery": 0,
                    "aggravated_assault": 0,
                    "burglary": 0,
                    "larceny": 0,
                    "motor_vehicle_theft": 0,
                }

            entry = city_year_data[key]
            entry["population"] += pop or 0

            for field in ["violent_crime", "property_crime", "murder", "rape",
                          "robbery", "aggravated_assault", "burglary", "larceny",
                          "motor_vehicle_theft"]:
                # FBI API may use 'actual' nested or flat field names
                val = safe_int(row.get(field) or row.get(f"{field}_actual"))
                db_field = field if field.endswith("_crime") else field
                if val is not None:
                    entry[f"{db_field}_total" if field.endswith("_crime") else db_field] = (
                        entry.get(f"{db_field}_total" if field.endswith("_crime") else db_field, 0) + val
                    )

    print()  # newline after \r progress

    # Compute rates per 100k and upsert
    collection = db["crime_stats"]
    inserted = updated = skipped = 0
    now = datetime.now(timezone.utc).isoformat()

    for (city, year), entry in city_year_data.items():
        pop = entry["population"]
        if pop and pop > 0:
            entry["violent_crime_rate"] = round(entry["violent_crime_total"] / pop * 100_000, 2)
            entry["property_crime_rate"] = round(entry["property_crime_total"] / pop * 100_000, 2)
        else:
            entry["violent_crime_rate"] = None
            entry["property_crime_rate"] = None

        entry["enriched_at"] = now

        result = collection.update_one(
            {"city": city, "state": "TX", "year": year},
            {"$set": entry},
            upsert=True,
        )
        if result.upserted_id:
            inserted += 1
        elif result.modified_count:
            updated += 1
        else:
            skipped += 1

    print(f"\nDone — inserted: {inserted}, updated: {updated}, unchanged: {skipped}")
    print(f"Cities with data: {sorted({c for c, _ in city_year_data})}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest FBI crime stats for DFW cities")
    parser.add_argument("--api-key", required=True, help="FBI CDE API key (get free at api.data.gov/signup)")
    parser.add_argument(
        "--years",
        default="2019,2020,2021,2022,2023",
        help="Comma-separated list of years to fetch (default: 2019-2023)",
    )
    args = parser.parse_args()
    year_list = [int(y.strip()) for y in args.years.split(",")]
    ingest(api_key=args.api_key, years=year_list)

import pandas as pd
from backend.db.mongodb import db
from backend.db.schema import DFW_CITIES, RESIDENTIAL_TYPES


def fetch_properties(zip_codes: list[str] | None = None) -> list[dict]:
    """Fetch DFW residential home listings from MongoDB."""
    query = {
        "city": {"$in": [c.title() for c in DFW_CITIES]},
        "property_type": {"$in": list(RESIDENTIAL_TYPES)},
    }
    if zip_codes:
        query["zip_code"] = {"$in": [str(z).zfill(5) for z in zip_codes]}
    return list(db["properties"].find(query, {"_id": 0}))


def fetch_data(collection_name: str, query: dict | None = None) -> list[dict]:
    """Fetch documents from any collection with an optional query filter."""
    return list(db[collection_name].find(query or {}, {"_id": 0}))

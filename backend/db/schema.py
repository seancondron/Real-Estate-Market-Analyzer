from backend.db.mongodb import client, db, MONGODB_DB

# Cities and towns within the Dallas-Fort Worth metroplex (Texas)
DFW_CITIES = {
    "dallas", "fort worth", "arlington", "plano", "garland", "irving",
    "grand prairie", "mckinney", "frisco", "mesquite", "carrollton",
    "denton", "richardson", "lewisville", "allen", "flower mound",
    "euless", "bedford", "grapevine", "southlake", "colleyville",
    "coppell", "rowlett", "wylie", "mansfield", "cedar hill",
    "duncanville", "desoto", "lancaster", "balch springs", "farmers branch",
    "the colony", "little elm", "prosper", "celina", "anna",
    "rockwall", "rowlett", "sachse", "murphy", "fate",
    "royse city", "forney", "kaufman", "waxahachie", "midlothian",
    "burleson", "cleburne", "azle", "keller", "hurst",
    "north richland hills", "watauga", "haltom city", "richland hills",
    "white settlement", "saginaw", "haslet",
}

# Residential property types - non-residential (commercial, land, etc.) are excluded
RESIDENTIAL_TYPES = {"single family", "townhouse", "condo", "multi-family"}


def setup_schema():
    existing = db.list_collection_names()

    # --- properties collection ---
    # Scoped to DFW-area residential homes only.
    if "properties" not in existing:
        db.create_collection(
            "properties",
            validator={
                "$jsonSchema": {
                    "bsonType": "object",
                    "required": ["address", "city", "state", "zip_code", "price"],
                    "properties": {
                        "address":        {"bsonType": "string"},
                        "city":           {"bsonType": "string"},
                        "state":          {"bsonType": "string", "enum": ["TX"]},
                        "zip_code":       {"bsonType": "string"},
                        # Homes only - single family, townhouse, condo, multi-family
                        "property_type":  {"bsonType": ["string", "null"]},
                        "listing_type":   {"bsonType": ["string", "null"]},
                        "date_posted":    {"bsonType": ["string", "null"]},
                        "price":          {"bsonType": ["int", "long", "double"]},
                        "beds":           {"bsonType": ["int", "null"]},
                        "baths":          {"bsonType": ["double", "int", "null"]},
                        "sqft":           {"bsonType": ["int", "null"]},
                        "lot_sqft":       {"bsonType": ["int", "null"]},
                        "year_built":     {"bsonType": ["int", "null"]},
                        "stories":        {"bsonType": ["int", "null"]},
                        "garage":         {"bsonType": ["bool", "null"]},
                        "days_on_market": {"bsonType": ["int", "null"]},
                        "price_per_sqft": {"bsonType": ["double", "int", "null"]},
                        "latitude":       {"bsonType": ["double", "int", "null"]},
                        "longitude":      {"bsonType": ["double", "int", "null"]},
                        "ingested_at":    {"bsonType": ["string", "null"]},
                    },
                }
            },
        )
        print("Created collection: properties")

    db["properties"].create_index(
        [("address", 1), ("city", 1), ("state", 1)],
        unique=True,
        name="address_city_state_unique",
    )
    db["properties"].create_index([("zip_code", 1)], name="zip_code_idx")
    db["properties"].create_index([("city", 1), ("state", 1)], name="city_state_idx")
    db["properties"].create_index([("property_type", 1)], name="property_type_idx")
    print("Indexes ensured: properties")

    # --- zip_demographics collection ---
    if "zip_demographics" not in existing:
        db.create_collection(
            "zip_demographics",
            validator={
                "$jsonSchema": {
                    "bsonType": "object",
                    "required": ["zip_code"],
                    "properties": {
                        "zip_code":       {"bsonType": "string"},
                        "median_income":  {"bsonType": ["int", "long", "null"]},
                        "population":     {"bsonType": ["int", "long", "null"]},
                        "enriched_at":    {"bsonType": ["string", "null"]},
                    },
                }
            },
        )
        print("Created collection: zip_demographics")

    db["zip_demographics"].create_index(
        [("zip_code", 1)],
        unique=True,
        name="zip_code_unique",
    )
    db["zip_demographics"].create_index([("state", 1)], name="state_idx")
    print("Indexes ensured: zip_demographics")


    # --- crime_stats collection ---
    # Source: FBI Crime Data Explorer API (free key at https://cde.fbi.gov/api)
    # Keyed on (city, state, year) - city-level annual crime rates
    if "crime_stats" not in existing:
        db.create_collection(
            "crime_stats",
            validator={
                "$jsonSchema": {
                    "bsonType": "object",
                    "required": ["city", "state", "year"],
                    "properties": {
                        "city":                   {"bsonType": "string"},
                        "state":                  {"bsonType": "string"},
                        "year":                   {"bsonType": "int"},
                        # Violent crime (murder, rape, robbery, aggravated assault)
                        "violent_crime_total":    {"bsonType": ["int", "null"]},
                        "violent_crime_rate":     {"bsonType": ["double", "null"]},  # per 100k population
                        # Property crime (burglary, larceny, motor vehicle theft)
                        "property_crime_total":   {"bsonType": ["int", "null"]},
                        "property_crime_rate":    {"bsonType": ["double", "null"]},  # per 100k population
                        # Breakdown
                        "murder":                 {"bsonType": ["int", "null"]},
                        "rape":                   {"bsonType": ["int", "null"]},
                        "robbery":                {"bsonType": ["int", "null"]},
                        "aggravated_assault":     {"bsonType": ["int", "null"]},
                        "burglary":               {"bsonType": ["int", "null"]},
                        "larceny":                {"bsonType": ["int", "null"]},
                        "motor_vehicle_theft":    {"bsonType": ["int", "null"]},
                        "population":             {"bsonType": ["int", "null"]},
                        "enriched_at":            {"bsonType": ["string", "null"]},
                    },
                }
            },
        )
        print("Created collection: crime_stats")

    db["crime_stats"].create_index(
        [("city", 1), ("state", 1), ("year", 1)],
        unique=True,
        name="city_state_year_unique",
    )
    db["crime_stats"].create_index([("city", 1), ("state", 1)], name="city_state_idx")
    print("Indexes ensured: crime_stats")


    # --- school_ratings collection ---
    # Source: GreatSchools API (free tier, key at greatschools.org/api)
    # One document per school. Feature engineering computes avg rating within X miles of a property.
    if "school_ratings" not in existing:
        db.create_collection(
            "school_ratings",
            validator={
                "$jsonSchema": {
                    "bsonType": "object",
                    "required": ["nces_id", "name", "city", "state"],
                    "properties": {
                        "nces_id":          {"bsonType": "string"},   # National Center for Ed Stats ID - stable unique key
                        "name":             {"bsonType": "string"},
                        "city":             {"bsonType": "string"},
                        "state":            {"bsonType": "string"},
                        "zip_code":         {"bsonType": ["string", "null"]},
                        "latitude":         {"bsonType": ["double", "null"]},
                        "longitude":        {"bsonType": ["double", "null"]},
                        "school_type":      {"bsonType": ["string", "null"]},  # "public" | "private" | "charter"
                        "level":            {"bsonType": ["string", "null"]},  # "elementary" | "middle" | "high"
                        "grades":           {"bsonType": ["string", "null"]},  # e.g. "K-5"
                        "rating":           {"bsonType": ["int", "null"]},     # GreatSchools 1–10 scale
                        "num_students":     {"bsonType": ["int", "null"]},
                        "student_teacher_ratio": {"bsonType": ["double", "null"]},
                        "enriched_at":      {"bsonType": ["string", "null"]},
                    },
                }
            },
        )
        print("Created collection: school_ratings")

    db["school_ratings"].create_index(
        [("nces_id", 1)],
        unique=True,
        name="nces_id_unique",
    )
    # 2dsphere index enables geo queries: find all schools within X miles of a property
    db["school_ratings"].create_index(
        [("location", "2dsphere")],
        name="location_geo",
        sparse=True,
    )
    db["school_ratings"].create_index([("city", 1), ("state", 1)], name="city_state_idx")
    db["school_ratings"].create_index([("zip_code", 1)], name="zip_code_idx")
    print("Indexes ensured: school_ratings")


if __name__ == "__main__":
    setup_schema()
    print(f"Schema setup complete for database: {MONGODB_DB}")

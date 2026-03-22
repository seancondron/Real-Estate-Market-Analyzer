import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "real_estate")

if not MONGODB_URI:
    raise ValueError("Missing MONGODB_URI in .env")

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]

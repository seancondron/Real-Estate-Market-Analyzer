import pandas as pd
import numpy as np
from backend.db.schema import DFW_CITIES, RESIDENTIAL_TYPES


def filter_dfw_homes(df: pd.DataFrame, zip_codes: list[str] | None = None) -> pd.DataFrame:
    """Keep only DFW-area residential home rows."""
    if "city" in df.columns:
        df = df[df["city"].str.lower().isin(DFW_CITIES)]
    if "property_type" in df.columns:
        df = df[df["property_type"].str.lower().isin(RESIDENTIAL_TYPES)]
    if zip_codes and "zip_code" in df.columns:
        normalized = [str(z).zfill(5) for z in zip_codes]
        df = df[df["zip_code"].isin(normalized)]
    return df.reset_index(drop=True)


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to DFW homes, then clean and preprocess."""
    df = filter_dfw_homes(df)
    df = df.dropna()
    return df

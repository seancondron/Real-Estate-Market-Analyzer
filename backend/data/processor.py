import pandas as pd
import numpy as np

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and preprocess a DataFrame."""
    df = df.dropna()
    return df

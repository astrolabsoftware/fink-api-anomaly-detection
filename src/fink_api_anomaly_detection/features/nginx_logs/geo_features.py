"""Geographical feature group E."""

import pandas as pd

from .common import empty_aggregate, prepare_windowed_dataframe

GEO_FEATURES = ["unique_country_count", "top_country_share"]


def build_geo_features(geo_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate country diversity and the most common country's traffic share."""
    frame = prepare_windowed_dataframe(geo_df,required_columns=("country",),source_name="geo")
    if frame.empty: return empty_aggregate(GEO_FEATURES)

    countries = frame["country"].astype("string").str.strip()
    frame["_country"] = countries.mask(countries.isna() | countries.eq("") | countries.eq("-"))

    valid_countries = frame.loc[frame["_country"].notna()]

    if valid_countries.empty:
        result = pd.DataFrame(index=pd.DatetimeIndex([], name="timestamp"))
    else:
        country_counts = valid_countries.groupby(["timestamp", "_country"], sort=True).size()
        by_window = country_counts.groupby(level="timestamp")
        result = pd.DataFrame({"unique_country_count": by_window.size(),"top_country_share": by_window.max() / by_window.sum(),})
        result.index.name = "timestamp"

    all_windows = pd.Index(frame["timestamp"].unique(), name="timestamp")
    result = result.reindex(all_windows)
    result["unique_country_count"] = result["unique_country_count"].fillna(0)
    result["top_country_share"] = result["top_country_share"].fillna(0)
    
    return result.reset_index()[["timestamp", *GEO_FEATURES]]

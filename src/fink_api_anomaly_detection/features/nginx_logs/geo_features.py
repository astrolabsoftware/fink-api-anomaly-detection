"""Geographical feature group E."""

import pandas as pd

from .common import empty_aggregate, prepare_windowed_dataframe

GEO_FEATURES = ["unique_country_count","top_country_share","top_country_share_without_france"]


def build_geo_features(geo_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate country diversity and country traffic shares."""
    frame = prepare_windowed_dataframe(geo_df,required_columns=("country",),source_name="geo")
    if frame.empty: return empty_aggregate(GEO_FEATURES)

    countries = frame["country"].astype("string").str.strip()
    country_keys = countries.str.casefold()
    frame["_country"] = country_keys.mask(
        countries.isna() | countries.eq("") | countries.eq("-")
    )

    valid_countries = frame.loc[frame["_country"].notna()]

    if valid_countries.empty:
        result = pd.DataFrame(
            index=pd.DatetimeIndex([], name="timestamp"),
            columns=GEO_FEATURES,
            dtype="float64",
        )
    else:
        country_counts = valid_countries.groupby(["timestamp", "_country"], sort=True).size()
        by_window = country_counts.groupby(level="timestamp")
        result = pd.DataFrame(
            {
                "unique_country_count": by_window.size(),
                "top_country_share": by_window.max() / by_window.sum(),
            }
        )

        non_france = valid_countries.loc[~valid_countries["_country"].eq("france")]
        non_france_counts = non_france.groupby(["timestamp", "_country"], sort=True).size()
        non_france_by_window = non_france_counts.groupby(level="timestamp")
        result["top_country_share_without_france"] = (non_france_by_window.max() / non_france_by_window.sum())
        result.index.name = "timestamp"

    all_windows = pd.Index(frame["timestamp"].unique(), name="timestamp")
    result = result.reindex(all_windows)
    result["unique_country_count"] = result["unique_country_count"].fillna(0)
    result["top_country_share"] = result["top_country_share"].fillna(0)
    result["top_country_share_without_france"] = result["top_country_share_without_france"].fillna(0)

    return result.reset_index()[["timestamp", *GEO_FEATURES]]

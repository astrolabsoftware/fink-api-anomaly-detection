"""Nginx error-log feature group F."""

import pandas as pd

from .common import empty_aggregate, prepare_windowed_dataframe

ERROR_FEATURES = ["nginx_error_count", "nginx_critical_count", "nginx_timeout_count", "nginx_connection_reset_count", "nginx_broken_pipe_count"]


def build_error_features(errors_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate Nginx errors and selected critical connection conditions."""
    frame = prepare_windowed_dataframe(errors_df,required_columns=("error_level", "error_message", "error_description"),source_name="errors")
    if frame.empty: return empty_aggregate(ERROR_FEATURES)

    levels = frame["error_level"].astype("string").str.strip().str.casefold()
    messages = (
        frame[["error_message", "error_description"]]
        .fillna("")
        .astype("string")
        .agg(" ".join, axis=1)
        .str.casefold()
    )
    frame["_critical"] = levels.eq("crit")
    frame["_timeout"] = messages.str.contains(r"\btimeout\b|\btimed out\b|\btime out\b", regex=True, na=False)
    frame["_connection_reset"] = messages.str.contains(r"\bconnection reset\b", regex=True, na=False)
    frame["_broken_pipe"] = messages.str.contains(r"\bbroken pipe\b", regex=True, na=False)

    aggregated = frame.groupby("timestamp", sort=True).agg(
        nginx_error_count=("timestamp", "size"),
        nginx_critical_count=("_critical", "sum"),
        nginx_timeout_count=("_timeout", "sum"),
        nginx_connection_reset_count=("_connection_reset", "sum"),
        nginx_broken_pipe_count=("_broken_pipe", "sum"),
    )
    
    return aggregated.reset_index()[["timestamp", *ERROR_FEATURES]]

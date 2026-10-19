"""Shared utilities for temporal aggregation of Nginx logs."""

from collections.abc import Iterable

import pandas as pd

WINDOW_SIZE = "5min"


def prepare_windowed_dataframe(dataframe: pd.DataFrame,required_columns: Iterable[str] | None = None, source_name: str = "log",) -> pd.DataFrame:
    """Select requested columns and floor UTC timestamps to the feature window.

    If ``required_columns`` is ``None``, preserve all input columns. Otherwise,
    retain only ``timestamp`` and the requested columns.
    """
    selected_columns = (None if required_columns is None else list(dict.fromkeys(("timestamp", *required_columns))))
    missing_columns = (set() if selected_columns is None else set(selected_columns).difference(dataframe.columns))
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"{source_name} DataFrame is missing required columns: {missing}")
    if "timestamp" not in dataframe.columns:
        raise ValueError(f"{source_name} DataFrame is missing required column: timestamp")

    result = (dataframe.copy() if selected_columns is None else dataframe[selected_columns].copy())
    timestamps = pd.to_datetime(result["timestamp"], utc=True, errors="raise")
    if timestamps.isna().any():
        raise ValueError(f"{source_name} DataFrame contains missing timestamps")

    result["timestamp"] = timestamps.dt.floor(WINDOW_SIZE)

    return result


def build_time_grid(*dataframes: pd.DataFrame) -> pd.DataFrame:
    """Build a complete UTC WINDOW_SIZE grid spanning all supplied log sources"""
    windowed = [
        prepare_windowed_dataframe(dataframe, required_columns=())
        for dataframe in dataframes
        if not dataframe.empty
    ]
    if not windowed:
        return pd.DataFrame(
            {"timestamp": pd.Series([], dtype="datetime64[ns, UTC]")}
        )

    start = min(dataframe["timestamp"].min() for dataframe in windowed)
    end = max(dataframe["timestamp"].max() for dataframe in windowed)
    return pd.DataFrame(
        {"timestamp": pd.date_range(start=start, end=end, freq=WINDOW_SIZE)}
    )


def empty_aggregate(columns: Iterable[str]) -> pd.DataFrame:
    """Create a correctly shaped empty aggregation result."""
    return pd.DataFrame(
        {
            "timestamp": pd.Series([], dtype="datetime64[ns, UTC]"),
            **{column: pd.Series(dtype="float64") for column in columns},
        }
    )

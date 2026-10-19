"""Temporal feature assembly and experiment feature subsets"""

import pandas as pd

from .common import build_time_grid
from .access_features import build_access_features
from .error_features import ERROR_FEATURES, build_error_features
from .geo_features import GEO_FEATURES, build_geo_features

# features groups 
TRAFFIC_FEATURES = ["request_count", "get_count", "post_count"]
RELIABILITY_FEATURES = ["http_4xx_count","http_5xx_count","http_4xx_rate","http_5xx_rate"]
CLIENT_VOLUME_FEATURES = ["unique_client_count", "bytes_sent_sum"]
NGINX_FEATURES = ERROR_FEATURES.copy()
GEOGRAPHY_FEATURES = GEO_FEATURES.copy()
ENDPOINT_FEATURES = ["endpoint_api_count","endpoint_unrecognized_count","unique_endpoint_count"]
TEMPORAL_FEATURES = ["request_count_delta","http_5xx_rate_delta","nginx_error_count_delta"]


# feature subsets constructed from the above groups, in order of increasing complexity
BASELINE_FEATURES = TRAFFIC_FEATURES + RELIABILITY_FEATURES + CLIENT_VOLUME_FEATURES
BASELINE_NGINX_FEATURES = BASELINE_FEATURES + NGINX_FEATURES
BASELINE_NGINX_GEOGRAPHY_FEATURES = BASELINE_NGINX_FEATURES + GEOGRAPHY_FEATURES
BASELINE_NGINX_GEOGRAPHY_ENDPOINT_FEATURES = BASELINE_NGINX_GEOGRAPHY_FEATURES + ENDPOINT_FEATURES
ALL_FEATURES = BASELINE_NGINX_GEOGRAPHY_ENDPOINT_FEATURES + TEMPORAL_FEATURES

# feature subsets dictionary for experiment selection
FEATURE_SUBSETS = {
    "baseline": BASELINE_FEATURES,
    "baseline_nginx": BASELINE_NGINX_FEATURES,
    "baseline_nginx_geography": BASELINE_NGINX_GEOGRAPHY_FEATURES,
    "baseline_nginx_geography_endpoints": BASELINE_NGINX_GEOGRAPHY_ENDPOINT_FEATURES,
    "all": ALL_FEATURES,
}


def build_temporal_features(access_df: pd.DataFrame, geo_df: pd.DataFrame, errors_df: pd.DataFrame) -> pd.DataFrame:
    """Build one row per WINDOW_SIZE interval from the three independent log sources.

    The returned frame contains ``timestamp`` and 22 numeric features. The
    complete grid spans the earliest through latest timestamp found in any
    non-empty source.
    """
    access_features = build_access_features(access_df)
    geo_features = build_geo_features(geo_df)
    error_features = build_error_features(errors_df)
    result = build_time_grid(access_df, geo_df, errors_df)

    if result.empty: return result.reindex(columns=["timestamp", *ALL_FEATURES])

    for features in (access_features, geo_features, error_features):
        result = result.merge(features,on="timestamp",how="left",validate="one_to_one")

    count_features = [
        feature
        for feature in ALL_FEATURES
        if not feature.endswith(("_rate", "_share", "_delta"))
    ]
    result[count_features] = result[count_features].fillna(0).astype("int64")
    rate_features = ["http_4xx_rate", "http_5xx_rate", "top_country_share"]
    result[rate_features] = result[rate_features].fillna(0.0)

    result["request_count_delta"] = result["request_count"].diff().fillna(0)
    result["http_5xx_rate_delta"] = result["http_5xx_rate"].diff().fillna(0)
    result["nginx_error_count_delta"] = result["nginx_error_count"].diff().fillna(0)

    return result[["timestamp", *ALL_FEATURES]]


def build_feature_subsets(dataframe: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return independent copies for each documented (doc/02_features_engineering_stategy.md) experiment configuration"""

    missing = set(FEATURE_SUBSETS["all"]).difference(dataframe.columns)
    if missing:raise ValueError("Feature DataFrame is missing required columns: "+ ", ".join(sorted(missing)))
    
    return {
        name: dataframe[features].copy()
        for name, features in FEATURE_SUBSETS.items()
    }

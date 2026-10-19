"""Access-log feature groups A, B, C, D, and G."""

import pandas as pd

from .common import empty_aggregate, prepare_windowed_dataframe

ACCESS_FEATURES = [
    "request_count",
    "get_count",
    "post_count",
    "http_4xx_count",
    "http_5xx_count",
    "http_4xx_rate",
    "http_5xx_rate",
    "unique_client_count",
    "bytes_sent_sum",
    "endpoint_api_count",
    "endpoint_unrecognized_count",
    "unique_endpoint_count"
]


def build_access_features(access_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate traffic, reliability, client, response, and endpoint features."""
    
    frame = prepare_windowed_dataframe(
        access_df,
        required_columns=(
            "method",
            "status_code",
            "client_ip",
            "bytes_sent",
            "endpoint",
        ),
        source_name="access",
    )
    if frame.empty: return empty_aggregate(ACCESS_FEATURES)

    methods = frame["method"].astype("string").str.upper()
    statuses = pd.to_numeric(frame["status_code"], errors="raise")
    endpoints = frame["endpoint"].astype("string")
    frame["_get"] = methods.eq("GET").fillna(False)
    frame["_post"] = methods.eq("POST").fillna(False)
    frame["_http_4xx"] = statuses.ge(400) & statuses.lt(500)
    frame["_http_5xx"] = statuses.ge(500) & statuses.lt(600)
    frame["_endpoint_api"] = endpoints.eq("/api/v1").fillna(False) | endpoints.str.startswith("/api/v1/", na=False)

    aggregated = frame.groupby("timestamp", sort=True).agg(
        request_count=("timestamp", "size"),
        get_count=("_get", "sum"),
        post_count=("_post", "sum"),
        http_4xx_count=("_http_4xx", "sum"),
        http_5xx_count=("_http_5xx", "sum"),
        unique_client_count=("client_ip", "nunique"),
        bytes_sent_sum=("bytes_sent", lambda values: values.sum(min_count=1)),
        endpoint_api_count=("_endpoint_api", "sum"),
        unique_endpoint_count=("endpoint", "nunique"),
    )
    aggregated["endpoint_unrecognized_count"] = (aggregated["request_count"] - aggregated["endpoint_api_count"])
    aggregated["bytes_sent_sum"] = aggregated["bytes_sent_sum"].fillna(0)
    aggregated["http_4xx_rate"] = (aggregated["http_4xx_count"] / aggregated["request_count"])
    aggregated["http_5xx_rate"] = (aggregated["http_5xx_count"] / aggregated["request_count"])

    return aggregated.reset_index()[["timestamp", *ACCESS_FEATURES]]

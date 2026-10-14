"""Parsing utilities for Nginx geo logs"""

from pathlib import Path
from typing import Iterable

import pandas as pd

from common import (
    iter_log_lines,
    parse_nginx_timestamp,
)

def parse_geo_log_line(line: str) -> dict | None:
    """
    Parse one Nginx geo log line.

    Expected format:
        timestamp@country@status_code@endpoint, example : 03/Oct/2026:00:01:04 +0000@France@200@/api/v1/conesearch

    Returns:
        A dictionary of parsed fields, or None if the line is invalid.
    """
    parts = line.strip().split("@", maxsplit=3)

    if len(parts) != 4: return None

    timestamp_str, country, status_str, endpoint = parts

    if not timestamp_str or not country or not status_str or not endpoint: return None

    try:
        timestamp = parse_nginx_timestamp(timestamp_str)
        status_code = int(status_str)

        if not 100 <= status_code <= 599: return None

    except (ValueError, TypeError):
        return None

    return {
        "timestamp": timestamp,
        "country": country,
        "status_code": status_code,
        "endpoint": endpoint,
    }


def build_geo_dataframe(log_files: Iterable[str | Path],) -> pd.DataFrame:
    """
    Parse Nginx geo log files into a structured DataFrame.

    Invalid lines are skipped and recorded in DataFrame attributes.
    Source file and line number are preserved for traceability.
    """
    records = []
    invalid_lines = []

    for log_file in log_files:
        path = Path(log_file)

        for line_number, line in iter_log_lines(path):
            if not line.strip():
                invalid_lines.append({"source_file": path.name,"source_line_number": line_number,"reason": "empty_line",})
                continue

            parsed = parse_geo_log_line(line)

            if parsed is None:
                invalid_lines.append({"source_file": path.name,"source_line_number": line_number,"reason": "unrecognized_format",})
                continue

            parsed["source_file"] = path.name
            parsed["source_line_number"] = line_number
            records.append(parsed)

    columns = ["timestamp","country","status_code","endpoint","source_file","source_line_number",]

    df = pd.DataFrame(records, columns=columns)

    if not df.empty:
        df["status_code"] = df["status_code"].astype("Int64")
        df["source_line_number"] = df["source_line_number"].astype("Int64")

    df.attrs["invalid_lines"] = invalid_lines
    df.attrs["invalid_line_count"] = len(invalid_lines)
    df.attrs["parsed_line_count"] = len(records)

    return df
"""Shared utilities for parsing and validating Nginx logs

This module will centralize functions common to the three log (access,geo,errors) categories:
- Reading lines from compressed .gz files.
- Preserving provenance information to trace back to each source line.
- Normalizing timestamps to UTC.
- Basic DataFrame validation.
"""

import gzip
from pathlib import Path
from typing import Iterator

import pandas as pd


def iter_log_lines(log_file: str | Path,encoding: str = "utf-8",) -> Iterator[tuple[int, str]]:
    """
    Iterate over a log file, yielding its line number and content.

    Supports compressed (.gz) and uncompressed text files.

    Args:
        log_file: Path to the log file.
        encoding: Text encoding used to decode the file.

    Yields:
        Tuples containing (line_number, line_content).
        Line numbers start at 1.
    """

    path = Path(log_file)

    if not path.is_file(): raise FileNotFoundError(f"Log file not found: {path}")

    opener = gzip.open if path.suffix == ".gz" else open

    with opener(path, "rt", encoding=encoding, errors="replace") as file:
        for line_number, line in enumerate(file, start=1):
            yield line_number, line.rstrip("\r\n")


def parse_nginx_timestamp(value: str) -> pd.Timestamp:
    """
    Parse a timestamp value (from an Nginx access, geo, or error log).

    Supported formats:
        Access/geo: 03/Oct/2026:00:00:59 +0000
        Error:      2026/10/03 00:20:33

    Returns:
        A timezone-aware pandas Timestamp normalized to UTC.

    Raises:
        ValueError: If the timestamp cannot be parsed.
    """

    value = value.strip().strip("[]")

    formats = (
        "%d/%b/%Y:%H:%M:%S %z",
        "%Y/%m/%d %H:%M:%S",
    )

    for timestamp_format in formats: 
        try: 
            timestamp = pd.to_datetime(value, format=timestamp_format, errors="raise", utc=True)
            return pd.Timestamp(timestamp)
        except (ValueError, TypeError):
            continue 

    raise ValueError(f"Unsupported timestamp format: {value!r}")



def validate_dataframe(df: pd.DataFrame) -> dict:
    """
    Return basic data quality metrics for a DataFrame df.

    Missing values are counted per column. Duplicate rows are counted
    across all columns.
    """
    return {
        "row_count": len(df),
        "column_count": len(df.columns),
        "duplicate_rows": int(df.duplicated().sum()),
        "missing_values": df.isna().sum().astype(int).to_dict(),
        "column_types": df.dtypes.astype(str).to_dict(),
    }



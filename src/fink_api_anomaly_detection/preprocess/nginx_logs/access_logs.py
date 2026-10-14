"""Parsing utilities for Nginx access logs"""

import re
from pathlib import Path
from typing import Iterable

import pandas as pd

from .common import (
    iter_log_lines,
    parse_nginx_timestamp,
)


# Expected Nginx access log structure : IP - USER [TIMESTAMP] "METHOD PATH PROTOCOL" STATUS BYTES "REFERER" "USER_AGENT" "X_FORWARDED_FOR"
ACCESS_LOG_PATTERN = re.compile(
    r'^(?P<client_ip>\S+)\s+'
    r'(?P<ident>\S+)\s+'
    r'(?P<remote_user>\S+)\s+'
    r'\[(?P<timestamp>[^\]]+)\]\s+'
    r'"(?P<request>[^"]*)"\s+'
    r'(?P<status_code>\d{3})\s+'
    r'(?P<bytes_sent>\S+)\s+'
    r'"(?P<http_referer>[^"]*)"\s+'
    r'"(?P<user_agent>[^"]*)"\s+'
    r'"(?P<x_forwarded_for>[^"]*)"\s*$'
)

def parse_access_log_line(line: str) -> dict | None:
    """
    Parse one Nginx access log line.

    Returns:
        A dictionary of parsed fields, or None if the line does not
        match the expected format.
    """

    match = ACCESS_LOG_PATTERN.match(line.strip())

    if match is None: return None

    fields = match.groupdict()

    # Parse the HTTP request field
    request_match = re.fullmatch(
        r"(?P<method>\S+)\s+(?P<endpoint>\S+)\s+(?P<protocol>\S+)",
        fields["request"],
    )

    if request_match is None: return None

    try:
        timestamp = parse_nginx_timestamp(fields["timestamp"])
        status_code = int(fields["status_code"])
        bytes_sent = (
            int(fields["bytes_sent"])
            if fields["bytes_sent"].isdigit()
            else None
        )
    except (ValueError, TypeError):
        return None

    return {
        "timestamp": timestamp,
        "client_ip": fields["client_ip"],
        "ident": fields["ident"],
        "remote_user": (
            None if fields["remote_user"] == "-" else fields["remote_user"]
        ),
        "method": request_match.group("method"),
        "endpoint": request_match.group("endpoint"),
        "protocol": request_match.group("protocol"),
        "status_code": status_code,
        "bytes_sent": bytes_sent,
        "http_referer": (
            None if fields["http_referer"] == "-" else fields["http_referer"]
        ),
        "user_agent": (
            None if fields["user_agent"] == "-" else fields["user_agent"]
        ),
        "x_forwarded_for": (
            None
            if fields["x_forwarded_for"] == "-"
            else fields["x_forwarded_for"]
        ),
    }

def build_access_dataframe(log_files: Iterable[str | Path],) -> pd.DataFrame:
    """
    Parse Nginx access log files into a structured DataFrame.

    Invalid lines are skipped but counted in DataFrame attributes.
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

            parsed = parse_access_log_line(line)

            if parsed is None:
                invalid_lines.append({"source_file": path.name,"source_line_number": line_number,"reason": "unrecognized_format",})
                continue

            parsed["source_file"] = path.name
            parsed["source_line_number"] = line_number
            records.append(parsed)

    columns = ["timestamp","client_ip","ident","remote_user","method","endpoint","protocol","status_code","bytes_sent","http_referer","user_agent","x_forwarded_for","source_file","source_line_number"]

    df = pd.DataFrame(records, columns=columns)

    if not df.empty:
        df["status_code"] = df["status_code"].astype("Int64")
        df["bytes_sent"] = df["bytes_sent"].astype("Int64")
        df["source_line_number"] = df["source_line_number"].astype("Int64")

    df.attrs["invalid_lines"] = invalid_lines
    df.attrs["invalid_line_count"] = len(invalid_lines)
    df.attrs["parsed_line_count"] = len(records)

    return df


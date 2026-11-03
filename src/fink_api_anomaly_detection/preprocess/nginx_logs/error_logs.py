"""Parsing utilities for Nginx error logs."""

import re
from pathlib import Path
from typing import Iterable

import pandas as pd

from .common import (
    iter_log_lines,
    parse_nginx_timestamp,
)


# Example:
# 2026/10/03 00:48:59 [error] 1596#1596: *965920
# writev() failed (32: Broken pipe) while sending request to upstream,
# client: 157.136.253.253, server: api.ztf.fink-portal.org,
# request: "POST /api/v1/objects HTTP/1.1",
# upstream: "http://unix:/run/fink_object_api.sock:/api/v1/objects",
# host: "api.ztf.fink-portal.org"

ERROR_LOG_HEADER_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})"
    r"\s+\[(?P<error_level>[^\]]+)\]"
    r"\s+(?P<worker_pid>\d+)#(?P<worker_tid>\d+):"
    r"(?:\s+\*(?P<connection_id>\d+))?"
    r"\s+(?P<details>.*)$"
)

CLIENT_IP_PATTERN = re.compile(
    r"(?:^|,\s*)client:\s*(?P<client_ip>[^,\s]+)"
)

SERVER_PATTERN = re.compile(
    r"(?:^|,\s*)server:\s*(?P<server>[^,\s]+)"
)

REQUEST_PATTERN = re.compile(
    r'(?:^|,\s*)request:\s*"'
    r'(?P<request>[^"]*)"'
)

UPSTREAM_PATTERN = re.compile(
    r'(?:^|,\s*)upstream:\s*"'
    r'(?P<upstream>[^"]*)"'
)

HOST_PATTERN = re.compile(
    r'(?:^|,\s*)host:\s*"'
    r'(?P<host>[^"]*)"'
)

ERROR_CODE_PATTERN = re.compile(
    r"\((?P<error_code>\d+):\s*"
    r"(?P<error_description>[^)]+)\)"
)

REQUEST_DETAILS_PATTERN = re.compile(
    r"(?P<method>\S+)\s+"
    r"(?P<endpoint>\S+)\s+"
    r"(?P<protocol>\S+)"
)


def _extract_field(pattern: re.Pattern,text: str,) -> str | None:
    """Extract a field using a regular expression"""
    match = pattern.search(text)
    return match.group(1) if match else None


def parse_error_log_line(line: str) -> dict | None:
    """
    Parse one Nginx error log line.

    Returns:
        A dictionary of parsed fields, or None if the line does not
        match the expected Nginx error log header.
    """
    line = line.strip()

    if not line: return None

    header_match = ERROR_LOG_HEADER_PATTERN.match(line)

    if header_match is None: return None

    fields = header_match.groupdict()
    details = fields["details"]

    try:
        timestamp = parse_nginx_timestamp(fields["timestamp"])
    except (ValueError, TypeError):
        return None

    # Extract the error message before the optional contextual fields.
    error_message = re.split(
        r",\s+(?=(?:client|server|request|upstream|host):)",
        details,
        maxsplit=1,
    )[0]

    error_code_match = ERROR_CODE_PATTERN.search(error_message)

    error_code = None
    error_description = None

    if error_code_match:
        error_code = int(error_code_match.group("error_code"))
        error_description = error_code_match.group("error_description")

    # Extract the HTTP request
    request = _extract_field(REQUEST_PATTERN, details)

    method = None
    endpoint = None
    protocol = None

    if request:
        request_match = REQUEST_DETAILS_PATTERN.fullmatch(request)

        if request_match:
            method = request_match.group("method")
            endpoint = request_match.group("endpoint")
            protocol = request_match.group("protocol")

    return {
        "timestamp": timestamp,
        "error_level": fields["error_level"],
        "worker_pid": int(fields["worker_pid"]),
        "worker_tid": int(fields["worker_tid"]),
        "connection_id": (
            int(fields["connection_id"])
            if fields["connection_id"] is not None
            else None
        ),
        "error_message": error_message,
        "error_code": error_code,
        "error_description": error_description,
        "client_ip": _extract_field(CLIENT_IP_PATTERN, details),
        "server": _extract_field(SERVER_PATTERN, details),
        "method": method,
        "endpoint": endpoint,
        "protocol": protocol,
        "upstream": _extract_field(UPSTREAM_PATTERN, details),
        "host": _extract_field(HOST_PATTERN, details),
    }


def build_error_dataframe(log_files: Iterable[str | Path],) -> pd.DataFrame:
    """
    Parse Nginx error log files into a structured DataFrame.

    Invalid lines are skipped and recorded in DataFrame attributes.
    Source file and line number are preserved for traceability.
    """
    def file_lines() -> Iterable[tuple[str, int, str]]:
        for log_file in log_files:
            path = Path(log_file)
            for line_number, line in iter_log_lines(path):
                yield path.name, line_number, line

    return _build_error_dataframe(file_lines())


def build_error_dataframe_from_lines(lines: Iterable[str]) -> pd.DataFrame:
    """Build the canonical error-log DataFrame from raw request-window lines."""
    return _build_error_dataframe(
        ("window-payload", line_number, line)
        for line_number, line in enumerate(lines, start=1)
    )


def _build_error_dataframe(
    lines: Iterable[tuple[str, int, str]],
) -> pd.DataFrame:
    records = []
    invalid_lines = []

    for source_file, line_number, line in lines:
        if not line.strip():
            invalid_lines.append({"source_file": source_file,"source_line_number": line_number,"reason": "empty_line",})
            continue

        parsed = parse_error_log_line(line)

        if parsed is None:
            invalid_lines.append({"source_file": source_file,"source_line_number": line_number,"reason": "unrecognized_format",})
            continue

        parsed["source_file"] = source_file
        parsed["source_line_number"] = line_number
        records.append(parsed)

    columns = ["timestamp","error_level","worker_pid","worker_tid","connection_id","error_message","error_code","error_description","client_ip","server","method","endpoint","protocol","upstream","host","source_file","source_line_number"]

    df = pd.DataFrame(records, columns=columns)

    if not df.empty:
        integer_columns = ["worker_pid","worker_tid","connection_id","error_code","source_line_number",]

        for column in integer_columns:
            df[column] = df[column].astype("Int64")

    df.attrs["invalid_lines"] = invalid_lines
    df.attrs["invalid_line_count"] = len(invalid_lines)
    df.attrs["parsed_line_count"] = len(records)

    return df

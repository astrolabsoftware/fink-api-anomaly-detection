"""Send UTC-aligned 5-minute Nginx log windows to the inference API anomaly detection."""

from __future__ import annotations

import gzip
import json
import logging
import math
import re
import signal
import sys
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
LOG_NAMES = ("access_logs", "geo_logs", "error_logs")
WINDOW = timedelta(minutes=5)
GRACE_PERIOD = timedelta(seconds=15)
RETRY_DELAY_SECONDS = 15
ACCESS_TIMESTAMP = re.compile(r"\[([^\]]+)\]")
ERROR_TIMESTAMP = re.compile(r"^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})")
RESPONSE_FIELDS = {
    "source_id",
    "window_start",
    "window_end",
    "reconstruction_error",
    "threshold",
    "is_anomaly",
    "anomaly_score",
    "severity",
    "alert_status",
    "parse_warnings",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def window_for(timestamp: datetime) -> datetime:
    timestamp = timestamp.astimezone(timezone.utc)
    minute = timestamp.minute - timestamp.minute % 5
    return timestamp.replace(minute=minute, second=0, microsecond=0)


def parse_log_timestamp(log_name: str, line: str) -> datetime | None:
    if log_name == "access_logs":
        match = ACCESS_TIMESTAMP.search(line)
        timestamp_text = match.group(1) if match else None
        timestamp_format = "%d/%b/%Y:%H:%M:%S %z"
    elif log_name == "geo_logs":
        timestamp_text = line.split("@", maxsplit=1)[0].strip()
        timestamp_format = "%d/%b/%Y:%H:%M:%S %z"
    else:
        match = ERROR_TIMESTAMP.match(line)
        timestamp_text = match.group(1) if match else None
        timestamp_format = "%Y/%m/%d %H:%M:%S"

    if not timestamp_text:
        return None

    try:
        parsed = datetime.strptime(timestamp_text, timestamp_format)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def log_files(base_path: Path, window_start: datetime) -> list[Path]:
    candidates = [base_path] if base_path.is_file() else []
    for pattern in (f"{base_path.name}.*", f"{base_path.name}-*"):
        candidates.extend(
            path
            for path in base_path.parent.glob(pattern)
            if path.is_file()
        )
    window_epoch = window_start.timestamp()
    return sorted(
        {
            path.resolve()
            for path in candidates
            if path == base_path or path.stat().st_mtime >= window_epoch
        }
    )


def collect_window(config: dict[str, Any],window_start: datetime,cursors: dict[tuple[int, int], int] | None = None) -> dict[str, Any] | None:
    cursors = cursors if cursors is not None else {}
    window_start = window_start.astimezone(timezone.utc)
    window_end = window_start + WINDOW
    payload: dict[str, Any] = {
        "source_id": config["source_id"],
        "window_id": utc_isoformat(window_start),
        "window_start": utc_isoformat(window_start),
        "window_end": utc_isoformat(window_end),
        **{name: [] for name in LOG_NAMES},
    }
    complete = True
    active_file_keys: set[tuple[int, int]] = set()

    logging.info("Collecting window %s to %s.",payload["window_start"],payload["window_end"])
    for log_name in LOG_NAMES:
        try:
            paths = log_files(Path(config["log_files"][log_name]), window_start)
        except OSError:
            logging.exception("Could not inspect %s files near %s.",log_name,config["log_files"][log_name])
            complete = False
            continue
        if not paths:
            logging.error("No %s file found at %s.", log_name, config["log_files"][log_name])
            complete = False
            continue

        for path in paths:
            try:
                stat = path.stat()
                file_key = (stat.st_dev, stat.st_ino)
                active_file_keys.add(file_key)
                opener = gzip.open if path.suffix == ".gz" else open
                with opener(path, "rb") as log_file:
                    offset = cursors.get(file_key, 0)
                    if path.suffix != ".gz" and stat.st_size < offset:
                        logging.warning("Log file was truncated; restarting at its beginning: %s", path)
                        offset = 0
                    if offset:
                        log_file.seek(offset)
                    while True:
                        line_offset = log_file.tell()
                        raw_line = log_file.readline()
                        if not raw_line:
                            break
                        if not raw_line.endswith(b"\n"):
                            log_file.seek(line_offset)
                            break
                        line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                        timestamp = parse_log_timestamp(log_name, line)
                        if timestamp is None:
                            logging.warning(
                                "Ignoring malformed %s line at byte %s in %s.",
                                log_name,
                                line_offset,
                                path,
                            )
                            continue
                        if window_start <= timestamp < window_end:
                            payload[log_name].append(line)
                    cursors[file_key] = log_file.tell()
            except (OSError, EOFError, gzip.BadGzipFile):
                logging.exception("Could not read %s file %s.", log_name, path)
                complete = False

        logging.info("Collected %s %s line(s).", len(payload[log_name]), log_name)

    for file_key in set(cursors) - active_file_keys:
        del cursors[file_key]

    if not complete:
        logging.error(
            "Skipping window %s because log collection was incomplete.",
            payload["window_id"],
        )
        return None

    logging.info("Created payload for window %s.", payload["window_id"])
    return payload


def _parse_response(body: bytes, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"API response is not valid JSON: {error}") from error
    if not isinstance(response, dict) or not RESPONSE_FIELDS.issubset(response):
        raise ValueError("API response is missing required prediction fields.")
    try:
        response_start = datetime.fromisoformat(
            response["window_start"].replace("Z", "+00:00")
        )
        response_end = datetime.fromisoformat(
            response["window_end"].replace("Z", "+00:00")
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("API response contains invalid window timestamps.") from error
    if (
        response_start.tzinfo is None
        or response_start.utcoffset() is None
        or response_end.tzinfo is None
        or response_end.utcoffset() is None
    ):
        raise ValueError("API response timestamps must include a timezone.")
    if (
        response["source_id"] != payload["source_id"]
        or utc_isoformat(response_start) != payload["window_start"]
        or utc_isoformat(response_end) != payload["window_end"]
    ):
        raise ValueError("API response does not correspond to the submitted window.")
    numeric_fields = ("reconstruction_error", "threshold", "anomaly_score")
    if (
        not isinstance(response["source_id"], str)
        or not isinstance(response["is_anomaly"], bool)
        or not isinstance(response["severity"], str)
        or not isinstance(response["alert_status"], str)
        or not isinstance(response["parse_warnings"], list)
        or not all(isinstance(warning, str) for warning in response["parse_warnings"])
        or not all(
            isinstance(response[field], (int, float))
            and not isinstance(response[field], bool)
            and math.isfinite(response[field])
            for field in numeric_fields
        )
    ):
        raise ValueError("API response contains invalid prediction fields.")
    return response


def deliver_window(config: dict[str, Any], payload: dict[str, Any], stop_event: threading.Event) -> bool:
    request = urllib.request.Request(
        config["api_url"],
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-API-Token": config["api_token"],
        },
        method="POST",
    )
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(
                request,
                timeout=float(config["request_timeout_seconds"]),
            ) as response:
                if not 200 <= response.status < 300:
                    raise ValueError(f"API returned HTTP {response.status}.")
                result = _parse_response(response.read(), payload)
            logging.info(
                "Delivered window %s on attempt %s (anomaly=%s, severity=%s).",
                payload["window_id"],
                attempt,
                result["is_anomaly"],
                result["severity"],
            )
            return True
        except (
            OSError,
            TimeoutError,
            urllib.error.URLError,
            TypeError,
            ValueError,
        ) as error:
            logging.error(
                "Delivery attempt %s of 2 failed for window %s: %s",
                attempt,
                payload["window_id"],
                error,
            )
            if attempt == 1:
                logging.info("Retrying window %s in 15 seconds.", payload["window_id"])
                if stop_event.wait(RETRY_DELAY_SECONDS):
                    logging.info("Retry cancelled during shutdown.")
                    return False

    logging.error(
        "Abandoning window %s after two failed HTTP attempts.",
        payload["window_id"],
    )
    return False


def wait_until(deadline: datetime, stop_event: threading.Event) -> bool:
    while not stop_event.is_set():
        remaining = (deadline - utc_now()).total_seconds()
        if remaining <= 0:
            return not stop_event.is_set()
        if stop_event.wait(remaining):
            return False
    return False


def run_forever(config: dict[str, Any], stop_event: threading.Event) -> None:
    logging.info("Nginx log exporter started.")
    cursors: dict[tuple[int, int], int] = {}
    while not stop_event.is_set():
        window_start = window_for(utc_now())
        window_end = window_start + WINDOW
        deadline = window_end + GRACE_PERIOD
        logging.info(
            "Current window is %s to %s.",
            utc_isoformat(window_start),
            utc_isoformat(window_end),
        )
        if not wait_until(deadline, stop_event):
            break
        if stop_event.is_set():
            break
        try:
            payload = collect_window(config, window_start, cursors)
            if payload is not None:
                deliver_window(config, payload, stop_event)
        except Exception:
            logging.exception(
                "Unexpected error while processing window %s.",
                utc_isoformat(window_start),
            )
    logging.info("Nginx log exporter stopped.")


def load_config() -> dict[str, Any]:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not config.get("api_token") or config["api_token"] == "CHANGE_ME":
        raise ValueError(f"Set api_token in {CONFIG_PATH}.")
    if not config.get("api_url", "").startswith(("http://", "https://")):
        raise ValueError("api_url must be an HTTP(S) URL.")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", config.get("source_id", "")):
        raise ValueError("source_id must match the API's 1-128 character identifier format.")
    for name in LOG_NAMES:
        if name not in config.get("log_files", {}):
            raise ValueError(f"log_files.{name} must be configured.")
    if float(config["request_timeout_seconds"]) <= 0:
        raise ValueError("request_timeout_seconds must be greater than zero.")
    return config


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    config = load_config()
    stop_event = threading.Event()
    signal.signal(signal.SIGTERM, lambda _signum, _frame: stop_event.set())
    signal.signal(signal.SIGINT, lambda _signum, _frame: stop_event.set())
    run_forever(config, stop_event)


if __name__ == "__main__":
    main()

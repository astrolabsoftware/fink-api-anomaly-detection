"""FastAPI prediction endpoint for Nginx  raw log windows"""

from __future__ import annotations

import json
import logging
import math
import os
import secrets
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from uvicorn import lifespan

# preprocess and feature extraction modules
from fink_api_anomaly_detection.preprocess.nginx_logs.access_logs import build_access_dataframe_from_lines
from fink_api_anomaly_detection.preprocess.nginx_logs.error_logs import build_error_dataframe_from_lines
from fink_api_anomaly_detection.preprocess.nginx_logs.geo_logs import build_geo_dataframe_from_lines
from fink_api_anomaly_detection.features.nginx_logs.temporal_features import build_temporal_features, ALL_FEATURES

# autoencoder inference module
from fink_api_anomaly_detection.models import Autoencoder


LOGGER = logging.getLogger(__name__)

WINDOW_DURATION = timedelta(minutes=5)


class PredictionRequest(BaseModel):
    """Complete raw-log payload for one UTC-aligned inference window (5 minutes raw log blocks)"""

    model_config = ConfigDict(extra="forbid")

    # source id is a unique identifier for the source of the logs (e.g., ztf.api.fink-portal.org)
    source_id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9._-]+$")

    window_id: str = Field(min_length=1, max_length=160)

    window_start: datetime
    window_end: datetime

    # log data for the window
    access_logs: list[str] = Field(default_factory=list)
    geo_logs: list[str] = Field(default_factory=list)
    error_logs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_window(self) -> PredictionRequest:
        if self.window_start.tzinfo is None or self.window_end.tzinfo is None:
            raise ValueError("Window timestamps must include a timezone.")

        start = self.window_start.astimezone(timezone.utc)
        end = self.window_end.astimezone(timezone.utc)

        if start != _floor_window(start):
            raise ValueError("window_start must align to a five-minute UTC boundary.")

        if end - start != WINDOW_DURATION:
            raise ValueError("window_end must be exactly 5 minutes after window_start.")

        if self.window_id != _utc_isoformat(start):
            raise ValueError("window_id must equal window_start in UTC ISO-8601 format.")

        return self


class PredictionResponse(BaseModel):
    """Prediction and human-readable context for one completed 5-minute window"""

    source_id: str
    window_start: datetime
    window_end: datetime
    reconstruction_error: float
    threshold: float
    is_anomaly: bool
    anomaly_score: float
    severity: str
    alert_status: str
    parse_warnings: list[str] = Field(default_factory=list)


@dataclass(slots=True)
class LogWindow:
    source_id: str
    window_start: datetime
    access_logs: list[str] = field(default_factory=list)
    geo_logs: list[str] = field(default_factory=list)
    error_logs: list[str] = field(default_factory=list)

    @property
    def window_end(self) -> datetime:
        return self.window_start + WINDOW_DURATION


def _utc_isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _floor_window(timestamp: datetime) -> datetime:
    timestamp = timestamp.astimezone(timezone.utc)
    minute = timestamp.minute - timestamp.minute % 5

    return timestamp.replace(minute=minute, second=0, microsecond=0)


def _read_log_frames(window: LogWindow) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:

    # assigne to each log type a dataframe for parsed logs and a list of warnings for unparsed lines
    frames = [
        ("access", build_access_dataframe_from_lines(window.access_logs)),
        ("geo", build_geo_dataframe_from_lines(window.geo_logs)),
        ("error", build_error_dataframe_from_lines(window.error_logs))
    ]
    warnings: list[str] = []

    valid_frames: list[pd.DataFrame] = []
    for source_name, frame in frames:
        for invalid in frame.attrs.get("invalid_lines", []):
            warning = (
                f"{source_name}_logs line {invalid['source_line_number']} "
                f"could not be parsed ({invalid['reason']})."
            )
            warnings.append(warning)
            LOGGER.warning("%s", warning)

        if frame.empty:
            valid_frames.append(frame)
            continue

        in_window = frame["timestamp"].map(lambda t: window.window_start<= t.to_pydatetime()< window.window_end)

        for line_number in frame.loc[~in_window, "source_line_number"]:
            warning = (f"{source_name}_logs line {line_number} is outside the assigned window.")
            warnings.append(warning)
            LOGGER.warning("%s", warning)

        filtered = frame.loc[in_window].copy()
        filtered.attrs["out_of_window_line_count"] = int((~in_window).sum())
        filtered.attrs["parsed_line_count"] = len(filtered)
        valid_frames.append(filtered)

    return valid_frames[0], valid_frames[1], valid_frames[2], warnings


def _build_summary_labels(access_df: pd.DataFrame, geo_df: pd.DataFrame ) -> dict[str, Any]:
    """Extract categorical labels that are not represented in numeric features """
    
    labels: dict[str, Any] = {
        "top_non_france_country": None,
        "top_unrecognized_endpoint": None,
        "top_unrecognized_endpoint_count": 0,
        "geo_entry_count": len(geo_df),
        "geo_input_line_count": int(geo_df.attrs.get("input_line_count", len(geo_df))),
        "geo_invalid_line_count": int(geo_df.attrs.get("invalid_line_count", 0)),
        "geo_out_of_window_line_count": int(geo_df.attrs.get("out_of_window_line_count", 0)),
        "geo_valid_country_count": 0,
        "geo_foreign_entry_count": 0,
        "geo_foreign_share": None,
        "geo_unique_country_count": 0,
    }

    if not access_df.empty:
        endpoints = access_df["endpoint"].astype("string")
        is_api = endpoints.eq("/api/v1").fillna(False) | endpoints.str.startswith("/api/v1/",na=False,)
        unexpected = endpoints.loc[~is_api & endpoints.notna()]
        if not unexpected.empty:
            endpoint_counts = unexpected.value_counts()
            labels["top_unrecognized_endpoint"] = str(endpoint_counts.index[0]).split("?",maxsplit=1)[0][:80]
            labels["top_unrecognized_endpoint_count"] = int(endpoint_counts.iloc[0])

    if not geo_df.empty:
        countries = geo_df["country"].astype("string").str.strip()
        country_keys = countries.str.casefold()
        valid = countries.notna() & countries.ne("") & countries.ne("-")
        valid_countries = countries.loc[valid]
        valid_keys = country_keys.loc[valid]
        non_france = valid_keys.loc[valid_keys.ne("france")]

        labels["geo_valid_country_count"] = len(valid_countries)
        labels["geo_foreign_entry_count"] = len(non_france)
        labels["geo_unique_country_count"] = int(valid_keys.nunique())
        if len(valid_countries):
            labels["geo_foreign_share"] = len(non_france) / len(valid_countries)

        if not non_france.empty:
            country_counts = non_france.value_counts()
            top_country_key = country_counts.index[0]
            labels["top_non_france_country"] = str(
                valid_countries.loc[valid_keys.eq(top_country_key)].iloc[0]
            )

    return labels


def _build_anomaly_summary( features: dict[str, Any],labels: dict[str, Any],*, 
        source_id:str, window : LogWindow,
        is_anomaly: bool, severity: str, anomaly_score: float ) -> dict[str, Any]:

    request_count = int(features["request_count"])
    http_4xx_count = int(features["http_4xx_count"])
    http_5xx_count = int(features["http_5xx_count"])
    http_4xx_rate = float(features["http_4xx_rate"])
    http_5xx_rate = float(features["http_5xx_rate"])
    api_count = int(features["endpoint_api_count"])
    unrecognized_count = int(features["endpoint_unrecognized_count"])
    unrecognized_rate = (unrecognized_count / request_count if request_count else 0.0)
    nginx_count = int(features["nginx_error_count"])

    severity_colors = {"High": "#E01E5A", "Medium": "#ECB22E","Low": "#36A64F"}
    color = severity_colors.get(severity, "#808080")

    status_icon = "🚨" if is_anomaly else "✅"
    status_text = "Anomaly detected" if is_anomaly else "No anomaly detected"
    blocks: list[dict[str, Any]] = []
    # Notify everyone (@channel) only for HIGH and MEDIUM severity
    if severity.upper() in {"HIGH", "MEDIUM"}:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "<!channel>",
            },
        })

    blocks.extend([
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": (
                    f"🚨 {severity} Nginx anomaly detected - Log source: {source_id} \n "
                    f"{_utc_isoformat(window.window_start)} - "
                    f"{_utc_isoformat(window.window_end)}"
                ),
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Status*\n{status_text}"},
                {"type": "mrkdwn", "text": f"*Severity*\n{severity}"},
                {"type": "mrkdwn", "text": f"*Anomaly score*\n`{anomaly_score:.3f}`"},
                {"type": "mrkdwn", "text": f"*Nb Requests in the window*\n`{request_count}`"},
            ],
        },
        {"type": "divider"},
    ])

    traffic_lines = [
        f"• HTTP 4xx: *{http_4xx_count}* ({http_4xx_rate:.2%})",
        f"• HTTP 5xx: *{http_5xx_count}* ({http_5xx_rate:.2%})"
    ]

    endpoint_lines = ["*🔎 Endpoint activity*"]

    if request_count:
        endpoint_lines.extend([
            (
                f"• `/api/v1`: *{api_count}/{request_count}* "
                f"({api_count / request_count:.2%})"
            ),
            (
                f"• Outside `/api/v1`: *{unrecognized_count}/{request_count}* "
                f"({unrecognized_rate:.2%})"
            ),
        ])
    else:
        endpoint_lines.append("• No HTTP requests observed.")

    if unrecognized_rate > 0 and is_anomaly:
        top_endpoint = labels["top_unrecognized_endpoint"]

        if top_endpoint:
            top_count = int(labels["top_unrecognized_endpoint_count"])

            endpoint_lines.append(
                f"• Most frequent identifiable path: `{top_endpoint}` "
                f"({top_count} request(s))"
            )
            endpoint_lines.append(
                " > Possible invalid or probing endpoint."
            )

        if request_count < 10:
            endpoint_lines.append(
                "⚠️ Small sample: interpret this analysis with caution."
            )

    nginx_lines = ["*🖥️ Nginx error analysis*"]

    if nginx_count:

        if request_count:
            nginx_lines.append(
                f"• Error/request ratio: *{nginx_count}/{request_count}*"
            )

        error_details = [
            ("Critical", "nginx_critical_count"),
            ("Timeout", "nginx_timeout_count"),
            ("Connection reset", "nginx_connection_reset_count"),
            ("Broken pipe", "nginx_broken_pipe_count"),
        ]

        for label, feature_name in error_details:
            count = int(features[feature_name])

            if count:
                nginx_lines.append(f"• {label}: *{count}*")

    else:
        nginx_lines.append("• No Nginx error log entries.")

    raw_non_france_share = features.get("top_country_share_without_france")
    non_france_share: float | None = None
    if raw_non_france_share is not None:
        try:
            candidate_share = float(raw_non_france_share)
        except (TypeError, ValueError):
            candidate_share = math.nan
        if math.isfinite(candidate_share) and 0 <= candidate_share <= 1:
            non_france_share = candidate_share

    geo_entry_count = int(labels.get("geo_entry_count", 0))
    valid_country_count = int(labels.get("geo_valid_country_count", 0))
    foreign_entry_count = int(labels.get("geo_foreign_entry_count", 0))
    country = labels.get("top_non_france_country")

    geography_lines = ["*🌍 Geography*"]

    if geo_entry_count == 0:
        input_line_count = int(labels.get("geo_input_line_count", 0))
        invalid_line_count = int(labels.get("geo_invalid_line_count", 0))
        out_of_window_count = int(labels.get("geo_out_of_window_line_count", 0))
        if out_of_window_count:
            geography_lines.append(
                "• No valid geographic entries were in this window; "
                f"{out_of_window_count} parsed line(s) were outside it."
            )
        elif input_line_count == 0:
            geography_lines.append(
                "• No geographic entries were received; foreign traffic cannot be determined."
            )
        elif invalid_line_count:
            geography_lines.append(
                "• Geographic lines were received, but none could be parsed; "
                "foreign traffic cannot be determined."
            )
        else:
            geography_lines.append(
                "• No valid geographic entries were available for this window; "
                "foreign traffic cannot be determined."
            )
    elif valid_country_count == 0:
        entry_text = (
            "1 geographic entry was"
            if geo_entry_count == 1
            else f"{geo_entry_count} geographic entries were"
        )
        geography_lines.append(
            f"• {entry_text} received, "
            "but none had a valid country; foreign traffic cannot be determined."
        )
    elif foreign_entry_count == 0:
        geography_lines.append(
            "• No traffic outside France was observed among "
            f"{valid_country_count} entries with valid countries."
        )
    else:
        if country is not None:
            geography_lines.append(
                f"• Traffic - Top country outside France: *{country}*"
            )
        else:
            geography_lines.append(
                "• Foreign traffic was present, but its leading country is unavailable."
            )

        if non_france_share is not None and non_france_share > 0 and country is not None:
            geography_lines.append(
                f"• Share of {country} traffic from non-France (foreign) traffic: *{non_france_share:.2%}*"
            )
            if is_anomaly and non_france_share == 1.0:
                geography_lines.append(
                    "⚠️ All observed requests outside France "
                    f"came from one country ({country}). This alone is not evidence "
                    "of a datacenter or scan."
                )
        else:
            geography_lines.append(
                "• The top-country share among foreign entries is unavailable "
                "or inconsistent with the parsed geographic records."
            )

    blocks.append({
        "type": "section",
        "fields": [
            {
                "type": "mrkdwn",
                "text": "*📊 Traffic analysis*\n" + "\n".join(traffic_lines),
            },
            {
                "type": "mrkdwn",
                "text": "\n".join(endpoint_lines),
            },
            {
                "type": "mrkdwn",
                "text": "\n".join(nginx_lines),
            },
            {
                "type": "mrkdwn",
                "text": "\n".join(geography_lines),
            },
        ],
    })


    if request_count < 20 and request_count > 0:
        blocks.extend([
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            "⚠️ *Low traffic volume:* only "
                            f"{request_count} request(s) scanned. "
                            "Interpret the results with caution."
                        ),
                    }
                ],
            },
        ])

    return {
        "attachments": [
            {
                "color": color,
                "blocks": blocks,
            }
        ]
    }


# Main inference service class that handles the autoencoder model, prediction and alerting logic
class InferenceService:
    """
    Handle real-time anomaly detection on 5-minute Nginx log windows.

    Parse incoming raw logs (blocks of 5 minutes raw logs), build model features, compute Autoencoder
    reconstruction errors and classify anomalies using a fixed threshold (Anomaly if reconstruction error > threshold).

    When an anomaly is detected, generate a traffic summary and send a Slack notification.
    """

    def __init__(self, autoencoder: Any, threshold: float,slack_webhook_url: str | None = None) -> None:

        if not math.isfinite(threshold) or threshold <= 0:
            raise ValueError("The anomaly threshold must be a finite positive number.")

        self.autoencoder = autoencoder
        self.threshold = threshold
        self.slack_webhook_url = slack_webhook_url
        self.feature_names = list(autoencoder.feature_names_)

        if not self.feature_names or len(self.feature_names) != len(set(self.feature_names)):
            raise ValueError("The loaded model must expose a non-empty, unique feature_names_ list.")

    @classmethod
    def from_environment(cls) -> InferenceService:
        package_root = Path(__file__).resolve().parents[2]
        model_path = Path(os.getenv("AE_MODEL_PATH", package_root / "artifacts" / "ae"))
        threshold = float(os.getenv("ANOMALY_THRESHOLD", "0.3608"))
        autoencoder = Autoencoder.load(model_path)

        return cls(autoencoder=autoencoder,threshold=threshold,slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"))

    def predict(self, window: LogWindow) -> PredictionResponse:
        start = window.window_start
  
        features_df, parse_warnings, labels = self._build_features(window)
        features = features_df.iloc[0].to_dict()
        model_input = pd.DataFrame([{name: features[name] for name in self.feature_names}])

        # anomaly prediction is based on reconstruction error from the autoencoder
        reconstruction_error = float(self.autoencoder.decision_function(model_input).iloc[0])
        is_anomaly = self.autoencoder.predict(X = model_input, threshold=self.threshold).iloc[0] 

        # anomaly score is a reconstruction error normalized value between 0 and 1, where higher values indicate more anomalous behavior
        # RError Reference Q75 from candidate-normal training windows
        normal_q75 = 0.025692

        # Logarithmic anomaly score between 0 and 1
        anomaly_score = (
            np.log1p(reconstruction_error / normal_q75)
            / (1 + np.log1p(reconstruction_error / normal_q75))
        )

        # Severity
        if is_anomaly:
            if anomaly_score < 0.55:
                severity = "Low"
            elif anomaly_score < 0.80:
                severity = "Medium"
            else:
                severity = "High"
        else:
            severity = "None"

        summary = _build_anomaly_summary(features,labels, is_anomaly=bool(is_anomaly), source_id=window.source_id, window=window, severity=severity,anomaly_score=anomaly_score)
        alert_status = "not_an_anomaly"

        if is_anomaly:
            alert_status = self._send_alert(source_id=window.source_id,window=window, severity=severity, anomaly_score=anomaly_score,summary=summary)

        result = PredictionResponse(
            source_id=window.source_id,
            window_start=start,
            window_end=window.window_end,
            reconstruction_error=reconstruction_error,
            threshold=self.threshold,
            is_anomaly=bool(is_anomaly),
            anomaly_score=anomaly_score,
            severity=severity,
            alert_status=alert_status,
            parse_warnings=parse_warnings,
        )

        return result


    @staticmethod
    def _build_features(window: LogWindow,) -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
        access_df, geo_df, error_df, parse_warnings = _read_log_frames(window)
        labels = _build_summary_labels(access_df, geo_df)
        features = build_temporal_features(access_df, geo_df, error_df)

        if features.empty:
            values = {name: 0 for name in ALL_FEATURES}
            values["timestamp"] = pd.Timestamp(window.window_start)
            features = pd.DataFrame([values])

        if len(features) != 1:
            raise ValueError("Logs must belong to exactly one 5-minute window.")

        return features, parse_warnings, labels

    def _send_alert(self, source_id: str, window: LogWindow, severity: str, anomaly_score: float, summary: str) -> str:

        if not self.slack_webhook_url:
            return "not_configured"

        payload = {**summary}

        try:
            request = urllib.request.Request(
                self.slack_webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=5) as response:
                if 200 <= response.status < 300:
                    return "sent"
                
                LOGGER.warning("Slack webhook returned HTTP %s.", response.status)
                return "failed"
            
        except urllib.error.HTTPError as error:
            LOGGER.warning("Slack webhook returned HTTP %s.", error.code)
            return "failed"
        except urllib.error.URLError:
            LOGGER.warning("Could not reach the configured Slack webhook.")
            return "failed"
        except TimeoutError:
            LOGGER.warning("The configured Slack webhook timed out.")
            return "failed"
        except ValueError:
            LOGGER.warning("The configured Slack webhook URL is invalid.")
            return "failed"


# Main function to create the FastAPI application
def create_app( service: InferenceService | None = None, api_token: str | None = None) -> FastAPI:

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configured_token = api_token if api_token is not None else os.getenv("API_TOKEN")

        if not configured_token:
            raise RuntimeError("API_TOKEN must be configured before starting the inference API.")

        inference_service = service or InferenceService.from_environment()
        application.state.api_token = configured_token
        application.state.inference_service = inference_service
        yield

    application = FastAPI(
        title="API Fink - Nginx Log Anomaly Detection API (Autoencoder)",
        version="0.3.0",
        root_path=os.getenv("API_ROOT_PATH", ""),
        lifespan=lifespan,
    )

    def verify_api_token(request: Request, x_api_token: Annotated[str | None, Header(alias="X-API-Token")] = None) -> None:
        expected_token = request.app.state.api_token

        if x_api_token is None or not secrets.compare_digest(
            x_api_token.encode("utf-8"),
            expected_token.encode("utf-8"),
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API token.")

    # Health check endpoint to verify that the API is running
    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Prediction endpoint for a single 5-minute raw log, protected by API token authentication
    @application.post("/predict", response_model=PredictionResponse, dependencies=[Depends(verify_api_token)])
    def predict_window(payload: PredictionRequest,request: Request,) -> PredictionResponse:
        window_start = payload.window_start.astimezone(timezone.utc)
        window = LogWindow(
            source_id=payload.source_id,
            window_start=window_start,
            access_logs=payload.access_logs,
            geo_logs=payload.geo_logs,
            error_logs=payload.error_logs,
        )
        try:
            return request.app.state.inference_service.predict(window)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail=str(error)) from error

    return application


app = create_app()

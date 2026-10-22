"""Evaluation metrics for timestamped baseline anomaly predictions."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class EvaluationMetricsReport:
    """Computed alert-volume, sequence, temporal, and signal-consistency metrics."""

    sequence_metrics: dict[str, str | int | float]
    sequences: pd.DataFrame
    daily_concentration: pd.DataFrame
    period_concentration: pd.DataFrame
    feature_counts: pd.DataFrame
    indicator_overlap: pd.DataFrame


def report_evaluation_metrics(feature_flags: pd.DataFrame, window_minutes: int = 5) -> EvaluationMetricsReport:
    """Compute evaluation metrics from a timestamp-indexed feature alert matrix.

    A window is flagged if any feature flags it. Consecutive flagged windows
    exactly ``window_minutes`` apart belong to the same alert sequence.
    """
    if not isinstance(feature_flags, pd.DataFrame):
        raise TypeError("feature_flags must be a pandas DataFrame.")
    if not feature_flags.columns.is_unique:
        raise ValueError("feature_flags must have unique feature columns.")

    flags = feature_flags.fillna(False).astype(bool).copy()
    try:
        flags.index = pd.to_datetime(flags.index, utc=True, errors="raise")
    except (TypeError, ValueError) as error:
        raise TypeError("feature_flags index must contain valid timestamps.") from error
    flags = flags.sort_index()
    if flags.index.has_duplicates:
        raise ValueError("evaluation timestamps must be unique.")

    window_alert = flags.any(axis=1)
    flagged_times = flags.index[window_alert]
    interval = pd.Timedelta(minutes=window_minutes)

    if len(flagged_times):
        sequence_ids = (flagged_times.to_series(index=range(len(flagged_times))).diff().ne(interval).cumsum())
        sequences = pd.DataFrame({"timestamp": flagged_times, "sequence": sequence_ids.to_numpy()})
        sequence_summary = sequences.groupby("sequence").agg(start=("timestamp", "first"),last_window=("timestamp", "last"),windows=("timestamp", "size"))
        sequence_summary["end"] = sequence_summary["last_window"] + interval
        sequence_summary["duration_minutes"] = (sequence_summary["windows"] * window_minutes)
        sequence_summary = sequence_summary[["start", "end", "windows", "duration_minutes"]]
        total_duration = int(sequence_summary["duration_minutes"].sum())
        median_duration = float(sequence_summary["duration_minutes"].median())
    else:
        sequence_summary = pd.DataFrame(
            columns=["start", "end", "windows", "duration_minutes"]
        )
        total_duration = 0
        median_duration = 0.0

    sequence_metrics: dict[str, str | int | float] = {
        "evaluated_windows": len(flags),
        "flagged_windows": int(window_alert.sum()),
        "flagged_rate": float(window_alert.mean()) if len(flags) else 0.0,
        "alert_sequences": len(sequence_summary),
        "total_sequence_duration_minutes": total_duration,
        "median_sequence_duration_minutes": median_duration,
    }

    by_day = pd.DataFrame({"alert": window_alert.to_numpy()}, index=flags.index)
    by_day["date_utc"] = by_day.index.strftime("%Y-%m-%d")
    daily_concentration = by_day.groupby("date_utc").agg(
        evaluated_windows=("alert", "size"),
        flagged_windows=("alert", "sum"),
        flagged_rate=("alert", "mean"),
    )

    by_period = pd.DataFrame({"alert": window_alert.to_numpy()}, index=flags.index)
    by_period["utc_period"] = pd.cut(
        by_period.index.hour,
        bins=[0, 6, 12, 18, 24],
        labels=["00:00-06:00", "06:00-12:00", "12:00-18:00", "18:00-24:00"],
        right=False,
    )
    period_concentration = by_period.groupby("utc_period", observed=False).agg(
        evaluated_windows=("alert", "size"),
        flagged_windows=("alert", "sum"),
        flagged_rate=("alert", "mean"),
    )

    feature_counts = flags.sum().rename("flagged_windows").to_frame()
    feature_counts["flagged_rate"] = flags.mean()
    indicator_overlap = flags.astype("int64").T.dot(flags.astype("int64"))

    return EvaluationMetricsReport(
        sequence_metrics=sequence_metrics,
        sequences=sequence_summary,
        daily_concentration=daily_concentration,
        period_concentration=period_concentration,
        feature_counts=feature_counts,
        indicator_overlap=indicator_overlap,
    )

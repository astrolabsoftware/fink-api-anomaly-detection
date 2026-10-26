import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import dates as mdates


def plot_anomaly_timeline(experiment_results, timestamps, train_index, eval_index, period="eval"):
    """Plot anomaly detections over time for each feature subset."""
    if period not in {"train", "eval", "test"}:
        raise ValueError("period must be 'train', 'eval', or 'test'")

    split_index = train_index if period == "train" else eval_index
    result_position = 0 if period == "train" else 1
    selected_timestamps = pd.to_datetime(timestamps.iloc[split_index])
    if selected_timestamps.empty:
        raise ValueError(f"No timestamps available for the {period} period.")

    flags = {}
    for feature_subset, results in experiment_results.items():
        if len(results) <= result_position or "is_anomaly" not in results[result_position]:
            raise ValueError(f"Missing anomaly predictions for feature subset {feature_subset!r}.")
        predictions = results[result_position]["is_anomaly"]
        if predictions.isna().any():
            raise ValueError(f"Anomaly predictions contain missing values for {feature_subset!r}.")
        if len(predictions) != len(selected_timestamps):
            raise ValueError(f"Prediction count does not match timestamps for {feature_subset!r}.")
        flags[feature_subset] = predictions.to_numpy(dtype=bool)

    flag_matrix = pd.DataFrame(flags, index=selected_timestamps).sort_index()
    fig, ax = plt.subplots(figsize=(17, 6))

    for y, feature_subset in enumerate(flag_matrix.columns):
        mask = flag_matrix[feature_subset].to_numpy()
        ax.vlines(flag_matrix.index[mask], y - 0.30, y + 0.30, linewidth=1.2)
        count = int(mask.sum())
        rate = 100 * mask.mean() if len(mask) else 0.0
        ax.text(1.01, y, f"{count} ({rate:.2f}%)", transform=ax.get_yaxis_transform(), va="center", fontsize=9)

    ax.set_yticks(range(len(flag_matrix.columns)))
    ax.set_yticklabels(flag_matrix.columns)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=12))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m\n%H:%M", tz=flag_matrix.index.tz))

    start = flag_matrix.index.min().normalize()
    end = flag_matrix.index.max().normalize() + pd.Timedelta(days=1)
    for day in pd.date_range(start, end, freq="D", tz=flag_matrix.index.tz):
        ax.axvline(day, linewidth=0.8, alpha=0.25)

    ax.set_xlim(flag_matrix.index.min() - pd.Timedelta(minutes=10), flag_matrix.index.max() + pd.Timedelta(minutes=10))
    ax.set_title(f"Isolation Forest anomaly detections - {period.capitalize()} period")
    ax.set_xlabel("Timestamp (UTC)")
    ax.set_ylabel("Feature subset")
    ax.grid(axis="x", alpha=0.20)
    ax.set_axisbelow(True)
    ax.text(1.01, 1.02, "Anomalies (rate)", transform=ax.transAxes, ha="left", va="bottom", fontsize=9, fontweight="bold")
    fig.subplots_adjust(right=0.82)
    fig.tight_layout()
    plt.show()
    return flag_matrix


def plot_anomaly_overlap(flag_matrix):
    """Compare anomaly detections using pairwise Jaccard similarity."""
    if flag_matrix.empty or flag_matrix.shape[1] == 0:
        raise ValueError("flag_matrix must contain at least one model and one row.")
    if flag_matrix.isna().any().any():
        raise ValueError("flag_matrix must not contain missing anomaly flags.")

    models = flag_matrix.columns
    flags = flag_matrix.to_numpy(dtype=bool)
    intersections = flags.astype(np.int64).T @ flags.astype(np.int64)
    counts = flags.sum(axis=0)
    unions = counts[:, None] + counts[None, :] - intersections
    similarities = np.divide(intersections, unions, out=np.ones_like(unions, dtype=float), where=unions != 0)
    jaccard = pd.DataFrame(similarities, index=models, columns=models)

    fig, ax = plt.subplots(figsize=(7, 5))
    image = ax.imshow(similarities, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels(models, rotation=40, ha="right")
    ax.set_yticks(range(len(models)))
    ax.set_yticklabels(models)
    for i, j in np.ndindex(similarities.shape):
        ax.text(j, i, f"{similarities[i, j]:.2f}", ha="center", va="center")

    ax.set_title("Jaccard similarity")
    fig.colorbar(image, ax=ax, label="Jaccard similarity")
    fig.tight_layout()
    plt.show()
    return jaccard


def plot_anomaly_features(eval_results, feature_name, features_df, eval_index, features_to_plot=None):
    """Plot selected feature time series with the same anomalous windows highlighted in red."""
    features_to_plot = ["request_count"] if features_to_plot is None else list(features_to_plot)
    if not features_to_plot:
        raise ValueError("features_to_plot must contain at least one feature.")
    if "timestamp" not in features_df.columns:
        raise ValueError("features_df must contain a 'timestamp' column.")
    if "is_anomaly" not in eval_results.columns:
        raise ValueError("eval_results must contain an 'is_anomaly' column.")

    eval_df = features_df.loc[eval_index].copy()
    if eval_df.empty:
        raise ValueError("No rows found for eval_index.")

    missing_features = [feature for feature in features_to_plot if feature not in eval_df.columns]
    if missing_features:
        raise ValueError(f"Features not found: {missing_features}")

    eval_df["timestamp"] = pd.to_datetime(eval_df["timestamp"], utc=True)
    eval_df = eval_df.sort_values("timestamp")
    model_results = eval_results.reindex(eval_df.index)
    if model_results["is_anomaly"].isna().any():
        raise ValueError("Some evaluation rows have no anomaly prediction.")

    anomaly_mask = model_results["is_anomaly"].to_numpy(dtype=bool)
    fig, axes = plt.subplots(nrows=len(features_to_plot), ncols=1, figsize=(16, 4 * len(features_to_plot)), sharex=True, squeeze=False)
    axes = axes.ravel()
    x = eval_df["timestamp"]

    for ax, feature in zip(axes, features_to_plot):
        y = eval_df[feature].astype(float)
        ax.plot(x, y, color="steelblue", linewidth=1, label=feature)
        ax.plot(x, y.where(anomaly_mask), color="red", linewidth=2, label="Anomalous windows")
        ax.set_ylabel(feature)
        ax.grid(alpha=0.25)
        ax.legend(loc="upper right")

    n_anomalies = int(anomaly_mask.sum())
    anomaly_rate = anomaly_mask.mean() * 100
    axes[0].set_title(f"Isolation Forest - {feature_name}: {n_anomalies}/{len(anomaly_mask)} anomalies ({anomaly_rate:.2f}%)")
    axes[-1].set_xlabel("Timestamp (UTC)")
    axes[-1].xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=12))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d/%m %H:%M", tz=eval_df["timestamp"].dt.tz))
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    plt.show()
    return fig, axes

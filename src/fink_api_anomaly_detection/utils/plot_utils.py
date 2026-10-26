import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import dates as mdates


def plot_anomaly_timeline(experiment_results,timestamps, train_index, eval_index,period="eval",):
    """
    Plot anomaly detections over time for each feature subset.

    Assumes each result entry contains:
      results[0] = training results
      results[1] = evaluation results

    Each result DataFrame must contain an 'is_anomaly' column.
    """

    if period not in {"train", "eval", "test"}:
        raise ValueError("period must be 'train' or 'eval' or 'test'")

    split_index = train_index if period == "train" else eval_index
    result_position = 0 if period == "train" else 1

    # Build the prediction matrix 
    flag_matrix = pd.DataFrame(
        {
            feature_subset: results[result_position]["is_anomaly"].to_numpy()
            for feature_subset, results in experiment_results.items()
        },
        index=pd.to_datetime(timestamps.iloc[split_index]),
    )
    flag_matrix = flag_matrix.sort_index()

    fig, ax = plt.subplots(figsize=(17, 6))

    for y, feature_subset in enumerate(flag_matrix.columns):
        mask = flag_matrix[feature_subset].to_numpy()
        anomaly_times = flag_matrix.index[mask]

        ax.vlines(anomaly_times,y - 0.30, y + 0.30,linewidth=1.2,label=None,)

        count = int(mask.sum())
        rate = 100 * mask.mean() if len(mask) else 0.0

        ax.text(1.01,y,f"{count} ({rate:.2f}%)",transform=ax.get_yaxis_transform(),va="center",fontsize=9,)

    ax.set_yticks(range(len(flag_matrix.columns)))
    ax.set_yticklabels(flag_matrix.columns)

    locator = mdates.AutoDateLocator(minticks=5, maxticks=12)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(
        mdates.DateFormatter("%d/%m\n%H:%M", tz=flag_matrix.index.tz)
    )


    start = flag_matrix.index.min().normalize()
    end = flag_matrix.index.max().normalize() + pd.Timedelta(days=1)

    for day in pd.date_range(start, end, freq="D", tz="UTC"):
        ax.axvline(day, linewidth=0.8, alpha=0.25)

    ax.set_xlim(
        flag_matrix.index.min() - pd.Timedelta(minutes=10),
        flag_matrix.index.max() + pd.Timedelta(minutes=10),
    )

    ax.set_title( f"Isolation Forest anomaly detections results - {period.capitalize()} period")
    ax.set_xlabel("Timestamp (UTC)")
    ax.set_ylabel("Feature subset")

    ax.grid(axis="x", alpha=0.20)
    ax.set_axisbelow(True)

    ax.text(1.01, 1.02, "Anomalies (rate)", transform=ax.transAxes, ha="left", va="bottom", fontsize=9, fontweight="bold",)

    fig.subplots_adjust(right=0.82)
    plt.tight_layout()
    plt.show()

    return flag_matrix




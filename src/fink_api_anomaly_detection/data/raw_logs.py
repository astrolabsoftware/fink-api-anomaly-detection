""" Utilities for discovering, reading, and extracting raw log files.
For example, extracting a .gz file, listing available files, or reading a sample and potentially a class for parsing or encoding the logs.
"""

import gzip 
import shutil
from pathlib import Path
from typing import List, Iterable


def ls_log_files(data_dir: str | Path , category: str | None=None,) -> List[Path]:
    """
    Listing compressed log files available in the dataset.

    Args:
        data_dir: Root directory containing the log categories (e.g. access-logs, error-logs, geo-logs).
        category: Optional category to inspect. If provided, searches only in the corresponding subdirectory.

    Returns:
        A sorted list of paths files (*.gz).

    Raises:
        FileNotFoundError: If the dataset directory does not exist.
        NotADirectoryError: If data_dir is not a directory.
        ValueError: If the requested category directory does not exist.
    """

    root = Path(data_dir)

    if not root.exists(): raise FileNotFoundError(f"Dataset directory not found: {root}")

    if not root.is_dir(): raise NotADirectoryError(f"Expected a directory: {root}")

    if category is not None: 
        root = root / category

        if not root.is_dir(): raise ValueError(f"Unknown or missing log category: {root}")

    return sorted(root.rglob("*.gz"))

def read_gz_sample(gz_path: str | Path, n_lines: int = 20, encoding: str = "utf-8",) -> List[str]:
    """
    Read a limited number of lines from a compressed (.gz) log file.

    The file is read directly without extracting it to disk.

    Args:
        gz_path: Path to the compressed .gz file.
        n_lines: Maximum number of lines to read.
        encoding: Text encoding used to decode the file.

    Returns:
        A list of decoded n lines. 

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: if the file is not a .gz file.
    """
    path = Path(gz_path)

    if not path.is_file():
        raise FileNotFoundError(f"Log file not found: {path}")

    if path.suffix != ".gz":
        raise ValueError(f"Expected a .gz file: {path}")

    if n_lines < 0:
        raise ValueError("n_lines must be greater than or equal to zero")

    with gzip.open(path, mode="rt", encoding=encoding, errors="replace") as f:
        return [line.rstrip("\r\n") for _, line in zip(range(n_lines), f)]



def inspect_logs_quality(files_by_category: dict[str, Iterable[str | Path]], encoding: str = "utf-8",) -> list[dict]:
    """
    Inspect the basic quality of compressed log files.

    For each file, computes the total number of lines, empty lines,
    lines containing Unicode replacement characters, and line-length
    statistics.

    Files are read directly from their compressed .gz format without
    extracting them to disk.

    Args:
        files_by_category: Dictionary mapping log categories to their
            corresponding file paths.
        encoding: Text encoding used to decode the log files.

    Returns:
        A list of dictionaries containing quality metrics for each file.
    """
    quality_results = []

    for category, files in files_by_category.items():
        for file_path in files:
            file_path = Path(file_path)

            total_lines = 0
            empty_lines = 0
            total_line_length = 0
            min_line_length = None
            max_line_length = 0

            with gzip.open(file_path,mode="rt",encoding=encoding,errors="replace",) as log_file:
                for line in log_file:
                    content = line.rstrip("\r\n")
                    line_length = len(content)

                    total_lines += 1
                    total_line_length += line_length

                    if not content.strip():
                        empty_lines += 1


                    min_line_length = (
                        line_length
                        if min_line_length is None
                        else min(min_line_length, line_length)
                    )
                    max_line_length = max(max_line_length, line_length)

            quality_results.append(
                {
                    "category": category,
                    "filename": file_path.name,
                    "total_lines": total_lines,
                    "empty_lines": empty_lines,
                    "min_line_length": min_line_length or 0,
                    "max_line_length": max_line_length,
                    "mean_line_length": (
                        total_line_length / total_lines
                        if total_lines
                        else 0
                    ),
                }
            )

    return quality_results
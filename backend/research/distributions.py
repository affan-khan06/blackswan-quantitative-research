from __future__ import annotations

import numpy as np
from scipy import stats


def analyze_return_distribution(values: np.ndarray) -> dict:
    """
    Compute empirical distribution diagnostics and normality tests (Jarque-Bera)
    for return or terminal value arrays.
    """
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 8:
        return {
            "count": int(len(arr)),
            "mean": float(np.mean(arr)) if len(arr) else 0.0,
            "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
            "skewness": 0.0,
            "excess_kurtosis": 0.0,
            "jarque_bera_stat": None,
            "jarque_bera_pvalue": None,
            "normal_rejected_5pct": None,
        }

    jb_stat, jb_p = stats.jarque_bera(arr)
    return {
        "count": int(len(arr)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=1)),
        "median": float(np.median(arr)),
        "p01": float(np.percentile(arr, 1)),
        "p05": float(np.percentile(arr, 5)),
        "p25": float(np.percentile(arr, 25)),
        "p75": float(np.percentile(arr, 75)),
        "p95": float(np.percentile(arr, 95)),
        "p99": float(np.percentile(arr, 99)),
        "skewness": float(stats.skew(arr, bias=False)),
        "excess_kurtosis": float(stats.kurtosis(arr, fisher=True, bias=False)),
        "jarque_bera_stat": float(jb_stat),
        "jarque_bera_pvalue": float(jb_p),
        "normal_rejected_5pct": bool(jb_p < 0.05),
    }

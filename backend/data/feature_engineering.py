from __future__ import annotations

import numpy as np
import pandas as pd


def build_hmm_feature_matrix(
    market_returns: pd.Series,
    vol_window: int = 21,
) -> pd.DataFrame:
    """
    Construct causal, leakage-free regime feature matrix from daily market returns:
      - trend_vol_window: trailing rolling mean daily log return (annualized drift)
      - rolling_vol: trailing rolling volatility (annualized using sqrt(252))
      - short_vol: trailing 5-day realized volatility (annualized) for crisis onset detection
    All rolling calculations use strictly past/current observations [t-window+1, t].
    """
    r = market_returns.astype(float).dropna()
    rolling_mean = r.rolling(window=vol_window, min_periods=vol_window).mean() * 252.0
    rolling_vol = r.rolling(window=vol_window, min_periods=vol_window).std(ddof=1) * np.sqrt(252.0)
    short_vol = r.rolling(window=5, min_periods=5).std(ddof=1) * np.sqrt(252.0)
    features = pd.DataFrame(
        {
            "rolling_trend": rolling_mean,
            "rolling_vol": rolling_vol,
            "short_vol": short_vol,
        },
        index=r.index,
    ).dropna()
    return features

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

from backend.app.core.exceptions import NumericalStabilityError


@dataclass
class CovarianceDiagnostics:
    matrix: np.ndarray
    min_eigenvalue_raw: float
    max_eigenvalue_raw: float
    condition_number: float
    psd_adjusted: bool
    adjustment_frobenius_norm: float
    method: str

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "min_eigenvalue_raw": float(self.min_eigenvalue_raw),
            "max_eigenvalue_raw": float(self.max_eigenvalue_raw),
            "condition_number": float(self.condition_number),
            "psd_adjusted": bool(self.psd_adjusted),
            "adjustment_frobenius_norm": float(self.adjustment_frobenius_norm),
        }


def estimate_and_validate_covariance(
    returns: pd.DataFrame | np.ndarray,
    method: str = "sample",
    min_eig_floor: float = 1e-10,
) -> CovarianceDiagnostics:
    """
    Estimate daily covariance matrix and validate Positive Semi-Definiteness (PSD).
    Never silently alters a non-PSD matrix without reporting the exact eigenvalue
    clipping and Frobenius adjustment norm.
    """
    arr = returns.to_numpy(dtype=float) if isinstance(returns, pd.DataFrame) else np.asarray(returns, dtype=float)
    if arr.ndim != 2 or arr.shape[0] < 2:
        raise NumericalStabilityError("At least 2 return observations are required to estimate covariance.")
    if np.isnan(arr).any() or np.isinf(arr).any():
        raise NumericalStabilityError("Return matrix contains NaN or infinite values.")

    if method == "ledoit_wolf":
        lw = LedoitWolf(assume_centered=False).fit(arr)
        raw_cov = lw.covariance_
    else:
        raw_cov = np.cov(arr, rowvar=False, ddof=1)
        if np.ndim(raw_cov) == 0:
            raw_cov = np.array([[float(raw_cov)]])

    sym_cov = 0.5 * (raw_cov + raw_cov.T)
    eigvals, eigvecs = np.linalg.eigh(sym_cov)
    min_eig = float(np.min(eigvals))
    max_eig = float(np.max(eigvals))

    psd_adjusted = False
    adjusted_cov = sym_cov
    frob_norm = 0.0

    if min_eig < min_eig_floor:
        psd_adjusted = True
        clipped = np.maximum(eigvals, min_eig_floor)
        adjusted_cov = eigvecs @ np.diag(clipped) @ eigvecs.T
        adjusted_cov = 0.5 * (adjusted_cov + adjusted_cov.T)
        frob_norm = float(np.linalg.norm(adjusted_cov - sym_cov, ord="fro"))
        eigvals = clipped
        min_eig_eff = float(np.min(eigvals))
    else:
        min_eig_eff = min_eig

    cond = float(max_eig / max(min_eig_eff, 1e-15))
    return CovarianceDiagnostics(
        matrix=adjusted_cov,
        min_eigenvalue_raw=min_eig,
        max_eigenvalue_raw=max_eig,
        condition_number=cond,
        psd_adjusted=psd_adjusted,
        adjustment_frobenius_norm=frob_norm,
        method=method,
    )


def safe_cholesky(cov_matrix: np.ndarray) -> tuple[np.ndarray, bool, float]:
    """
    Compute lower-triangular Cholesky factor L such that Sigma = L @ L.T.
    Reports if jitter/eigenvalue clipping was needed.
    """
    sym = 0.5 * (cov_matrix + cov_matrix.T)
    try:
        L = np.linalg.cholesky(sym)
        return L, False, 0.0
    except np.linalg.LinAlgError:
        eigvals, eigvecs = np.linalg.eigh(sym)
        clipped = np.maximum(eigvals, 1e-10)
        repaired = 0.5 * (eigvecs @ np.diag(clipped) @ eigvecs.T + (eigvecs @ np.diag(clipped) @ eigvecs.T).T)
        frob = float(np.linalg.norm(repaired - sym, ord="fro"))
        try:
            L = np.linalg.cholesky(repaired)
            return L, True, frob
        except np.linalg.LinAlgError as exc:
            raise NumericalStabilityError(f"Cholesky decomposition failed even after PSD repair: {exc}")


def apply_crisis_correlation_stress(
    cov_matrix: np.ndarray,
    stress_blend: float = 0.50,
    target_crisis_corr: float = 0.85,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Transform a baseline covariance matrix into a stressed crisis covariance matrix
    by blending off-diagonal correlations toward `target_crisis_corr`:
        R_stress = (1 - blend) * R_base + blend * R_target
    Returns (stressed_cov, base_corr, stressed_corr).
    """
    stds = np.sqrt(np.maximum(np.diag(cov_matrix), 1e-12))
    inv_stds = np.diag(1.0 / stds)
    base_corr = inv_stds @ cov_matrix @ inv_stds
    base_corr = np.clip(0.5 * (base_corr + base_corr.T), -0.999, 0.999)
    np.fill_diagonal(base_corr, 1.0)

    n = base_corr.shape[0]
    target_mat = np.full((n, n), target_crisis_corr, dtype=float)
    np.fill_diagonal(target_mat, 1.0)

    # Blend correlations upward in magnitude/level toward crisis co-movement
    stressed_corr = (1.0 - stress_blend) * base_corr + stress_blend * np.maximum(base_corr, target_mat)
    np.fill_diagonal(stressed_corr, 1.0)

    # Ensure PSD correlation matrix
    eigvals, eigvecs = np.linalg.eigh(stressed_corr)
    if np.min(eigvals) < 1e-8:
        eigvals = np.maximum(eigvals, 1e-8)
        stressed_corr = eigvecs @ np.diag(eigvals) @ eigvecs.T
        d = np.sqrt(np.diag(stressed_corr))
        stressed_corr = stressed_corr / np.outer(d, d)
        np.fill_diagonal(stressed_corr, 1.0)

    D = np.diag(stds)
    stressed_cov = D @ stressed_corr @ D
    stressed_cov = 0.5 * (stressed_cov + stressed_cov.T)
    return stressed_cov, base_corr, stressed_corr

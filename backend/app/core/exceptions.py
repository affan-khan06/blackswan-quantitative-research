class BlackswanError(Exception):
    """Base domain exception for BLACKSWAN."""

    def __init__(self, message: str, status_code: int = 400, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class DataAcquisitionError(BlackswanError):
    """Raised when market data acquisition fails or yields insufficient coverage."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, status_code=502, details=details)


class DataValidationError(BlackswanError):
    """Raised when market data fails integrity or quality checks."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, status_code=422, details=details)


class InsufficientDataError(BlackswanError):
    """Raised when sample size is too small for econometric estimation."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, status_code=422, details=details)


class ModelConvergenceError(BlackswanError):
    """Raised when GARCH or HMM estimation fails to converge reliably."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, status_code=422, details=details)


class NumericalStabilityError(BlackswanError):
    """Raised when covariance or matrix decomposition cannot be stabilized safely."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, status_code=422, details=details)

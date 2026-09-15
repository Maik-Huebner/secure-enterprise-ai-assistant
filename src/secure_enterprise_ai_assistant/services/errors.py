"""Service-layer exceptions with safe, stable error messages."""


class ServiceError(Exception):
    """Base exception for expected business-service failures."""


class CaseNotFoundError(ServiceError):
    """Raised when a requested synthetic case does not exist."""


class CustomerNotFoundError(ServiceError):
    """Raised when a requested synthetic customer does not exist."""


class DatasetError(ServiceError):
    """Raised when the local synthetic dataset is missing or invalid."""


class ComplianceConfigurationError(ServiceError):
    """Raised when machine-readable compliance rules are invalid or unsafe."""

"""Project-specific exception hierarchy."""

from __future__ import annotations


class SRARError(RuntimeError):
    """Base class for project-specific runtime failures."""


class ConfigurationError(SRARError):
    """Raised when project configuration cannot be loaded or validated."""


class DataAccessError(SRARError):
    """Raised when a required data source cannot be accessed."""


class DataValidationError(SRARError):
    """Raised when input or processed data fail validation checks."""


class ReplicationBlockError(SRARError):
    """Raised when strict replication is blocked by unresolved evidence."""


class EstimationError(SRARError):
    """Raised when an econometric estimator cannot return valid results."""

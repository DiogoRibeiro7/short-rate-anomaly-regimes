"""Project-specific exception hierarchy."""

from __future__ import annotations


class SRARError(RuntimeError):
    """Base class for project-specific runtime failures."""


class ConfigurationError(SRARError):
    """Raised when project configuration cannot be loaded or validated."""


class DataAccessError(SRARError):
    """Raised when a required data source cannot be accessed."""


class FrozenVintageError(DataAccessError):
    """Raised when a download does not match the frozen vintage recorded in the archive.

    This is the abort that keeps a rebuild honest: the published results were
    produced from specific provider bytes, and a rebuild that silently accepted
    different bytes would report a different vintage under the same claims.
    """


class DataValidationError(SRARError):
    """Raised when input or processed data fail validation checks."""


class ReplicationBlockError(SRARError):
    """Raised when strict replication is blocked by unresolved evidence."""


class EstimationError(SRARError):
    """Raised when an econometric estimator cannot return valid results."""

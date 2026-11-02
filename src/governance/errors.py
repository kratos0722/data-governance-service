"""Domain errors."""

from __future__ import annotations


class GovernanceError(Exception):
    """Base class for governance domain errors."""


class NotFoundError(GovernanceError):
    pass


class DuplicateError(GovernanceError):
    pass


class InvalidStateError(GovernanceError):
    pass

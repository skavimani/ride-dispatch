"""Custom exceptions so callers can tell *which* input was wrong."""


class DispatchError(Exception):
    """Base class for every error raised by the ridedispatch package."""


class UnknownNodeError(DispatchError, KeyError):
    """An intersection id that is not in the road network."""


class UnknownDriverError(DispatchError, KeyError):
    """A driver id that is not registered."""


class DuplicateDriverError(DispatchError, ValueError):
    """A driver id that is already registered."""


class UnknownRequestError(DispatchError, KeyError):
    """A request id that is not waiting in the queue."""


class DuplicateRequestError(DispatchError, ValueError):
    """A request id that is already waiting in the queue."""

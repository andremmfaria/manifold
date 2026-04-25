class ManifoldError(Exception):
    """Base domain error."""


class AuthenticationError(ManifoldError):
    """Auth failure."""


class AuthorizationError(ManifoldError):
    """Permission failure."""


class ConflictError(ManifoldError):
    """Conflict error."""


class ValidationError(ManifoldError):
    """Validation error."""

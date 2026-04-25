from __future__ import annotations


class ManifoldError(Exception):
    """Base domain error."""


class AuthenticationError(ManifoldError):
    """Auth failure."""


class AuthorizationError(ManifoldError):
    """Permission failure."""


class NotFoundError(ManifoldError):
    def __init__(self, resource: str, id: str):
        super().__init__(f"{resource} {id!r} not found")
        self.resource = resource
        self.id = id


class ConflictError(ManifoldError):
    """Conflict error."""


class ValidationError(ManifoldError):
    """Validation error."""


class ProviderError(ManifoldError):
    """Base provider error."""

    def __init__(
        self,
        message: str = "provider error",
        *,
        error_code: str = "provider_error",
        detail: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.detail = detail or {"message": message}


class ProviderAuthError(ProviderError):
    """OAuth/credential failure for provider connection."""

    def __init__(
        self,
        message: str = "provider auth failed",
        *,
        detail: dict | None = None,
    ) -> None:
        super().__init__(message, error_code="provider_auth", detail=detail)


class ProviderRateLimitError(ProviderError):
    """HTTP 429 from provider."""

    def __init__(
        self,
        retry_after: int = 60,
        message: str | None = None,
        *,
        detail: dict | None = None,
    ) -> None:
        resolved_message = message or f"Rate limited; retry after {retry_after}s"
        resolved_detail = detail or {"message": resolved_message, "retry_after": retry_after}
        super().__init__(resolved_message, error_code="rate_limited", detail=resolved_detail)
        self.retry_after = retry_after


class ProviderUnavailableError(ProviderError):
    """Provider unavailable."""

    def __init__(
        self,
        message: str = "provider unavailable",
        *,
        detail: dict | None = None,
    ) -> None:
        super().__init__(message, error_code="provider_unavailable", detail=detail)


class ProviderDataError(ProviderError):
    """Provider returned invalid data."""

    def __init__(
        self,
        message: str = "provider data invalid",
        *,
        detail: dict | None = None,
    ) -> None:
        super().__init__(message, error_code="provider_data_error", detail=detail)


class SyncError(ManifoldError):
    """Base sync error."""

    def __init__(
        self,
        message: str = "sync failed",
        *,
        error_code: str = "sync_error",
        detail: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.detail = detail or {"message": message}


class SyncLockError(SyncError):
    """Another sync is already running for this connection."""

    def __init__(
        self,
        message: str = "sync already running",
        *,
        detail: dict | None = None,
    ) -> None:
        super().__init__(message, error_code="sync_lock", detail=detail)


class SyncTimeoutError(SyncError):
    """Sync timed out."""

    def __init__(
        self,
        message: str = "sync timed out",
        *,
        detail: dict | None = None,
    ) -> None:
        super().__init__(message, error_code="sync_timeout", detail=detail)


class AlarmEvaluationError(ManifoldError):
    """Alarm evaluation failed."""


class AlarmConditionError(AlarmEvaluationError):
    """Invalid or unparseable alarm condition."""


class NotifierError(ManifoldError):
    """Base notifier error."""


class NotifierConfigError(NotifierError):
    """Notifier config invalid."""


class NotifierDeliveryError(NotifierError):
    """Notifier delivery failed."""


class EncryptionError(ManifoldError):
    """Encryption error."""


class DEKNotFoundError(EncryptionError):
    """DEK missing."""


__all__ = [
    "AlarmConditionError",
    "AlarmEvaluationError",
    "AuthenticationError",
    "AuthorizationError",
    "ConflictError",
    "DEKNotFoundError",
    "EncryptionError",
    "ManifoldError",
    "NotFoundError",
    "NotifierConfigError",
    "NotifierDeliveryError",
    "NotifierError",
    "ProviderAuthError",
    "ProviderDataError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderUnavailableError",
    "SyncError",
    "SyncLockError",
    "SyncTimeoutError",
    "ValidationError",
]

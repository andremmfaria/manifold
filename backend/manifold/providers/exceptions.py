from __future__ import annotations


class SyncError(Exception):
    def __init__(self, message: str, *, error_code: str = "sync_error", detail: dict | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.detail = detail or {"message": message}


class ProviderAuthError(SyncError):
    def __init__(self, message: str = "provider auth failed", *, detail: dict | None = None):
        super().__init__(message, error_code="provider_auth", detail=detail)


class ProviderRateLimitError(SyncError):
    def __init__(self, message: str = "provider rate limited", *, detail: dict | None = None):
        super().__init__(message, error_code="rate_limited", detail=detail)

"""Typed data-layer errors.

These subclass the existing single ``AxHubError`` so the ``(category, code)``
contract that the conformance vectors and error tests match on keeps working,
while callers can still ``isinstance``-narrow on the specific failure (mirrors
node's ``LegacyCursorError`` / ``InvalidCursorError`` / ``ValidationError`` /
``TableNotFoundError`` / ``IntrospectFailedError`` / ``ScanLimitExceededError``
hierarchy).
"""
from __future__ import annotations

from .. import AxHubError


class ValidationError(AxHubError):
    def __init__(self, message: str, code: str = "validation", *, request_id: str | None = None, status: int = 0, retryable: bool = False):
        super().__init__("validation", code, message, status, retryable, request_id)


class LegacyCursorError(AxHubError):
    """Raised when an after/before keyset or v1:/v2: cursor token is supplied;
    the live AX Hub data API is offset-only (mirrors node LegacyCursorError)."""

    def __init__(self, message: str, *, request_id: str | None = None):
        super().__init__("validation", "legacy_cursor", message, 0, False, request_id)


class InvalidCursorError(AxHubError):
    def __init__(self, message: str, *, request_id: str | None = None):
        super().__init__("validation", "invalid_cursor", message, 0, False, request_id)


class TableNotFoundError(AxHubError):
    def __init__(self, message: str, *, request_id: str | None = None):
        super().__init__("not_found", "table_not_found", message, 404, False, request_id)


class IntrospectFailedError(AxHubError):
    def __init__(self, message: str, *, status: int = 0, retryable: bool = False, request_id: str | None = None):
        super().__init__("internal", "introspect_failed", message, status, retryable, request_id)


class ScanLimitExceededError(AxHubError):
    def __init__(self, message: str, *, request_id: str | None = None):
        super().__init__("internal", "scan_limit_exceeded", message, 0, False, request_id)


__all__ = [
    "ValidationError",
    "LegacyCursorError",
    "InvalidCursorError",
    "TableNotFoundError",
    "IntrospectFailedError",
    "ScanLimitExceededError",
]

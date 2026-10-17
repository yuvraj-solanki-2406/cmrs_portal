"""Domain errors and the single API error envelope.

Envelope: {"code": "...", "message": "...", "details": {...}, "request_id": "..."}
"""
import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .middleware import get_request_id

logger = logging.getLogger(__name__)


class DomainError(Exception):
    """Base class for business-rule violations raised by service functions."""

    status_code = 400
    code = "DOMAIN_ERROR"
    message = "The request could not be processed."

    def __init__(self, message: str | None = None, *, details: dict | None = None, code: str | None = None):
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details or {}
        if code:
            self.code = code


class ValidationFailed(DomainError):
    status_code = 400
    code = "VALIDATION_ERROR"


class NotAllowed(DomainError):
    status_code = 403
    code = "FORBIDDEN"
    message = "You do not have permission to perform this action."


class NotFound(DomainError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Not found."


class Conflict(DomainError):
    status_code = 409
    code = "CONFLICT"


class InvalidState(Conflict):
    code = "INVALID_STATE"


def _envelope(code: str, message: str, details: dict | None, status: int) -> Response:
    return Response(
        {"code": code, "message": message, "details": details or {}, "request_id": get_request_id()},
        status=status,
    )


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return _envelope(exc.code, exc.message, exc.details, exc.status_code)
    if isinstance(exc, Http404):
        return _envelope("NOT_FOUND", "Not found.", None, 404)
    if isinstance(exc, PermissionDenied):
        return _envelope("FORBIDDEN", "You do not have permission to perform this action.", None, 403)

    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled error", exc_info=exc)
        return _envelope("SERVER_ERROR", "An unexpected error occurred.", None, 500)

    if isinstance(exc, drf_exceptions.ValidationError):
        return _envelope("VALIDATION_ERROR", "Validation failed.", {"fields": response.data}, 400)
    if isinstance(exc, (drf_exceptions.NotAuthenticated, drf_exceptions.AuthenticationFailed)):
        return _envelope("UNAUTHENTICATED", "Authentication credentials were missing or invalid.", None, 401)
    if isinstance(exc, drf_exceptions.PermissionDenied):
        return _envelope("FORBIDDEN", "You do not have permission to perform this action.", None, 403)
    if isinstance(exc, drf_exceptions.NotFound):
        return _envelope("NOT_FOUND", "Not found.", None, 404)
    if isinstance(exc, drf_exceptions.Throttled):
        return _envelope("THROTTLED", "Too many requests. Try again later.", {"wait": exc.wait}, 429)
    detail = response.data.get("detail") if isinstance(response.data, dict) else None
    return _envelope(exc.__class__.__name__.upper(), str(detail or "Request failed."), None, response.status_code)

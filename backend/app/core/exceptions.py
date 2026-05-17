from typing import Any, Optional

from app.constants import ErrorMessages, HTTPStatus


class AppException(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR,
        details: Optional[dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.error_code = error_code or self.__class__.__name__
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "success": False,
            "error": self.message,
            "error_code": self.error_code,
        }
        if self.details:
            result["details"] = self.details
        return result


class ValidationError(AppException):
    def __init__(self, message: str = ErrorMessages.VALIDATION_ERROR, details: Optional[dict] = None):
        super().__init__(message, HTTPStatus.BAD_REQUEST, details, "VALIDATION_ERROR")


class NotFoundError(AppException):
    def __init__(self, message: str = "Ресурс не найден", details: Optional[dict] = None):
        super().__init__(message, HTTPStatus.NOT_FOUND, details, "NOT_FOUND")


class BadRequestError(AppException):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, HTTPStatus.BAD_REQUEST, details, "BAD_REQUEST")


class UnauthorizedError(AppException):
    def __init__(self, message: str = ErrorMessages.UNAUTHORIZED, details: Optional[dict] = None):
        super().__init__(message, HTTPStatus.UNAUTHORIZED, details, "UNAUTHORIZED")


class ForbiddenError(AppException):
    def __init__(self, message: str = ErrorMessages.FORBIDDEN, details: Optional[dict] = None):
        super().__init__(message, HTTPStatus.FORBIDDEN, details, "FORBIDDEN")


class ConflictError(AppException):
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message, HTTPStatus.BAD_REQUEST, details, "CONFLICT")

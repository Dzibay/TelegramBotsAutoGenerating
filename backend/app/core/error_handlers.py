from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.constants import ErrorMessages
from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger(__name__)


async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        content = exc.detail
    else:
        content = {
            "success": False,
            "error": str(exc.detail) if exc.detail else ErrorMessages.INTERNAL_ERROR,
            "error_code": f"HTTP_{exc.status_code}",
        }
    return JSONResponse(status_code=exc.status_code, content=content)


async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": ErrorMessages.VALIDATION_ERROR,
            "error_code": "VALIDATION_ERROR",
            "details": exc.errors(),
        },
    )


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": ErrorMessages.INTERNAL_ERROR,
            "error_code": "INTERNAL_ERROR",
        },
    )


def register_error_handlers(app) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

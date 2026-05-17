from typing import Any, Optional

from app.constants import HTTPStatus


def success_response(
    data: Optional[Any] = None,
    message: Optional[str] = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {"success": True}
    if message:
        response["message"] = message
    if data is not None:
        if isinstance(data, dict):
            response.update(data)
        else:
            response["data"] = data
    return response


def error_response(error: str, details: Any = None, status_code: int = HTTPStatus.BAD_REQUEST) -> dict:
    body: dict[str, Any] = {"success": False, "error": error}
    if details is not None:
        body["details"] = details
    return body

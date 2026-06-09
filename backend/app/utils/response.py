from typing import Any, Optional


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

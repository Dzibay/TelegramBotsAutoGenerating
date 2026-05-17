import json
import re
from typing import Any


def extract_json_array(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("JSON-массив не найден в ответе AI")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, list):
        raise ValueError("Ожидался JSON-массив")
    return [x for x in data if isinstance(x, dict)]


def extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("JSON-объект не найден в ответе AI")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("Ожидался JSON-объект")
    return data

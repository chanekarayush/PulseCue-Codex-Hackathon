"""Shared Lambda helpers for the codex_project backend."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,PUT,OPTIONS",
}


class DecimalJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)


def response(status_code: int, body: Any) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, cls=DecimalJSONEncoder, ensure_ascii=False),
    }


def options_response() -> dict[str, Any]:
    return response(200, {"ok": True})


def error_response(message: str = "Internal server error", status_code: int = 500) -> dict[str, Any]:
    return response(status_code, {"error": message})


def decimal_to_native(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {key: decimal_to_native(child) for key, child in value.items()}
    if isinstance(value, list):
        return [decimal_to_native(child) for child in value]
    return value


def floats_to_decimal(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: floats_to_decimal(child) for key, child in value.items()}
    if isinstance(value, list):
        return [floats_to_decimal(child) for child in value]
    return value


def scan_all(table: Any, **kwargs: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    scan_kwargs = dict(kwargs)
    while True:
        page = table.scan(**scan_kwargs)
        items.extend(page.get("Items", []))
        last_key = page.get("LastEvaluatedKey")
        if not last_key:
            return items
        scan_kwargs["ExclusiveStartKey"] = last_key


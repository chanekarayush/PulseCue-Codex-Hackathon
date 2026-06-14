"""Admin API for reviewing and correcting generated metadata."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

from common import decimal_to_native, error_response, floats_to_decimal, options_response, response, scan_all


logger = logging.getLogger()
logger.setLevel(logging.INFO)

READ_ONLY_FIELDS = {"video_id", "pk", "sk"}


def _table() -> Any:
    return boto3.resource("dynamodb").Table(os.environ["DYNAMODB_TABLE"])


def _video_id(event: dict[str, Any]) -> str | None:
    params = event.get("pathParameters") or {}
    return params.get("videoId")


def _route(event: dict[str, Any]) -> str:
    return event.get("resource") or event.get("path") or ""


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64

        body = base64.b64decode(body).decode("utf-8")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError("JSON body must be an object.")
    return parsed


def _update_video(video_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    updates = {key: value for key, value in payload.items() if key not in READ_ONLY_FIELDS}
    if not updates:
        raise ValueError("No mutable fields provided.")

    names = {f"#f{index}": key for index, key in enumerate(updates.keys())}
    values = {f":v{index}": floats_to_decimal(value) for index, value in enumerate(updates.values())}
    assignments = [f"{name} = :v{index}" for index, name in enumerate(names.keys())]

    result = _table().update_item(
        Key={"video_id": video_id},
        UpdateExpression="SET " + ", ".join(assignments),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ReturnValues="ALL_NEW",
    )
    return result.get("Attributes", {})


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    if event.get("httpMethod") == "OPTIONS":
        return options_response()

    try:
        method = event.get("httpMethod")
        route = _route(event)

        if method == "GET" and route == "/admin/videos":
            videos = scan_all(_table())
            return response(200, {"count": len(videos), "videos": decimal_to_native(videos)})

        if route == "/admin/videos/{videoId}":
            video_id = _video_id(event)
            if not video_id:
                return error_response("Missing videoId", 400)

            if method == "GET":
                item = _table().get_item(Key={"video_id": video_id}).get("Item")
                if not item:
                    return error_response("Video not found", 404)
                return response(200, decimal_to_native(item))

            if method == "PUT":
                updated = _update_video(video_id, _parse_body(event))
                return response(200, decimal_to_native(updated))

        return error_response("Route not found", 404)
    except Exception as exc:
        logger.exception("Admin API failed")
        return error_response(str(exc))


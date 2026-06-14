"""Library grid API Lambda for videos and books."""

from __future__ import annotations

import logging
import os
from typing import Any

import boto3

from common import decimal_to_native, error_response, options_response, response, scan_all


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _table(name: str) -> Any:
    return boto3.resource("dynamodb").Table(name)


def _path(event: dict[str, Any]) -> str:
    return event.get("resource") or event.get("path") or ""


def _video_id(event: dict[str, Any]) -> str | None:
    params = event.get("pathParameters") or {}
    return params.get("videoId")


def _video_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "video_id": item.get("video_id"),
        "title": item.get("title") or item.get("title_suggestion"),
        "summary": item.get("summary"),
        "topics": item.get("topics") or [],
        "type": item.get("type") or item.get("source_type") or "youtube_video",
    }


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    if event.get("httpMethod") == "OPTIONS":
        return options_response()

    try:
        video_table = _table(os.environ["DYNAMODB_TABLE"])
        books_table_name = os.environ.get("BOOKS_TABLE")
        route = _path(event)

        if route == "/videos/{videoId}":
            video_id = _video_id(event)
            if not video_id:
                return error_response("Missing videoId", 400)
            item = video_table.get_item(Key={"video_id": video_id}).get("Item")
            if not item:
                return error_response("Video not found", 404)
            return response(200, decimal_to_native(item))

        if route == "/videos":
            videos = scan_all(
                video_table,
                ProjectionExpression="video_id, title, title_suggestion, summary, topics, #type, source_type",
                ExpressionAttributeNames={"#type": "type"},
            )
            return response(200, {"count": len(videos), "videos": [_video_summary(item) for item in videos]})

        if route == "/books":
            if not books_table_name:
                return response(200, {"count": 0, "books": []})
            books_table = _table(books_table_name)
            books = scan_all(
                books_table,
                ProjectionExpression="book_id, title, author, summary, topics, mood, for_whom",
            )
            return response(200, {"count": len(books), "books": decimal_to_native(books)})

        return error_response("Route not found", 404)
    except Exception as exc:
        logger.exception("Library API failed")
        return error_response(str(exc))

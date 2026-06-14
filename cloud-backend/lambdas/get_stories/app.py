"""Randomized story feed Lambda."""

from __future__ import annotations

import logging
import os
import random
from decimal import Decimal
from typing import Any

import boto3
from pydantic import BaseModel, Field

from common import error_response, options_response, response, scan_all


logger = logging.getLogger()
logger.setLevel(logging.INFO)


class Story(BaseModel):
    story_id: str
    video_id: str
    title: str | None = None
    summary: str | None = None
    characters: list[str] = Field(default_factory=list)
    spiritual_lesson: str | None = None
    start_time_seconds: int | None = None
    end_time_seconds: int | None = None
    exact_start_text: str | None = None
    exact_end_text: str | None = None
    source_title: str | None = None


def _seconds(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return int(value)
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _video_title(item: dict[str, Any]) -> str | None:
    return item.get("title") or item.get("title_suggestion") or item.get("video_title")


def _flatten_story(video: dict[str, Any], story: dict[str, Any], index: int) -> Story:
    video_id = str(video.get("video_id") or video.get("id") or "unknown")
    return Story(
        story_id=f"{video_id}#story#{index:03d}",
        video_id=video_id,
        title=story.get("title"),
        summary=story.get("summary"),
        characters=list(story.get("characters") or []),
        spiritual_lesson=story.get("spiritual_lesson"),
        start_time_seconds=_seconds(story.get("start_time_seconds", story.get("start_time"))),
        end_time_seconds=_seconds(story.get("end_time_seconds", story.get("end_time"))),
        exact_start_text=story.get("exact_start_text"),
        exact_end_text=story.get("exact_end_text"),
        source_title=_video_title(video),
    )


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    if event.get("httpMethod") == "OPTIONS":
        return options_response()

    try:
        table_name = os.environ["DYNAMODB_TABLE"]
        table = boto3.resource("dynamodb").Table(table_name)
        videos = scan_all(table, ProjectionExpression="video_id, title, title_suggestion, stories")

        stories: list[dict[str, Any]] = []
        for video in videos:
            for index, story in enumerate(video.get("stories") or []):
                if isinstance(story, dict):
                    stories.append(_flatten_story(video, story, index).model_dump())

        random.shuffle(stories)
        return response(200, {"count": len(stories), "stories": stories})
    except Exception as exc:
        logger.exception("Failed to fetch stories")
        return error_response(str(exc))


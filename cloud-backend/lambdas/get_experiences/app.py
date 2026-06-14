"""Randomized motivation/fitness experience feed Lambda."""

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


class Experience(BaseModel):
    experience_id: str
    video_id: str
    title: str | None = None
    experience_type: str | None = None
    summary: str | None = None
    lesson: str | None = None
    start_time_seconds: int | None = None
    end_time_seconds: int | None = None
    exact_start_text: str | None = None
    exact_end_text: str | None = None
    source_title: str | None = None
    topics: list[str] = Field(default_factory=list)


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


def _flatten_experience(video: dict[str, Any], experience: dict[str, Any], index: int) -> Experience:
    video_id = str(video.get("video_id") or video.get("id") or "unknown")
    return Experience(
        experience_id=f"{video_id}#experience#{index:03d}",
        video_id=video_id,
        title=experience.get("title"),
        experience_type=experience.get("experience_type"),
        summary=experience.get("summary"),
        lesson=experience.get("lesson"),
        start_time_seconds=_seconds(experience.get("start_time_seconds", experience.get("start_time"))),
        end_time_seconds=_seconds(experience.get("end_time_seconds", experience.get("end_time"))),
        exact_start_text=experience.get("exact_start_text"),
        exact_end_text=experience.get("exact_end_text"),
        source_title=_video_title(video),
        topics=list(video.get("topics") or []),
    )


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    if event.get("httpMethod") == "OPTIONS":
        return options_response()

    try:
        table_name = os.environ["DYNAMODB_TABLE"]
        table = boto3.resource("dynamodb").Table(table_name)
        videos = scan_all(table, ProjectionExpression="video_id, title, title_suggestion, topics, experiences")

        experiences: list[dict[str, Any]] = []
        for video in videos:
            for index, experience in enumerate(video.get("experiences") or []):
                if isinstance(experience, dict):
                    experiences.append(_flatten_experience(video, experience, index).model_dump())

        random.shuffle(experiences)
        return response(200, {"count": len(experiences), "experiences": experiences})
    except Exception as exc:
        logger.exception("Failed to fetch experiences")
        return error_response(str(exc))


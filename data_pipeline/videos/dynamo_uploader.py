"""Upload lean video metadata records to DynamoDB."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from data_pipeline.common import get_logger, iter_json_files, load_json
from data_pipeline.dynamo import to_dynamo_value


LOGGER = get_logger(__name__)
VIDEO_DIR = Path(__file__).resolve().parent
DEFAULT_METADATA_DIR = VIDEO_DIR / "enriched_metadata"


def _seconds(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _queries(metadata: dict[str, Any]) -> list[str]:
    return _string_list(metadata.get("queries") or [])


def _clean_experiences(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in metadata.get("experiences") or []:
        if not isinstance(item, dict):
            continue
        cleaned.append(
            {
                "title": item.get("title"),
                "experience_type": item.get("experience_type"),
                "summary": item.get("summary"),
                "lesson": item.get("lesson"),
                "start_time_seconds": _seconds(item.get("start_time_seconds", item.get("start_time"))),
                "end_time_seconds": _seconds(item.get("end_time_seconds", item.get("end_time"))),
            }
        )
    return cleaned


def _clean_fitness_advice(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in metadata.get("fitness_advice") or []:
        if not isinstance(item, dict):
            continue
        cleaned.append(
            {
                "advice": item.get("advice"),
                "for_whom": _string_list(item.get("for_whom") or []),
                "category": item.get("category"),
                "why_it_matters": item.get("why_it_matters"),
                "how_to_apply": item.get("how_to_apply"),
                "start_time_seconds": _seconds(item.get("start_time_seconds", item.get("start_time"))),
                "end_time_seconds": _seconds(item.get("end_time_seconds", item.get("end_time"))),
            }
        )
    return cleaned


def _clean_takeaways(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    for item in metadata.get("motivational_takeaways") or []:
        if isinstance(item, dict):
            cleaned.append({"takeaway": item.get("takeaway"), "context": item.get("context")})
        elif str(item or "").strip():
            cleaned.append({"takeaway": str(item).strip(), "context": None})
    return cleaned


def _drop_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _drop_none(child) for key, child in value.items() if child is not None}
    if isinstance(value, list):
        return [_drop_none(child) for child in value]
    return value


def build_video_dynamo_item(metadata: dict[str, Any], *, video_id: str) -> dict[str, Any]:
    """Build the app-facing one-row-per-video DynamoDB schema."""

    return _drop_none({
        "video_id": video_id,
        "source_type": "youtube_video",
        "title": metadata.get("title") or metadata.get("title_suggestion"),
        "summary": metadata.get("summary"),
        "target_audience": _string_list(metadata.get("target_audience") or []),
        "difficulty_level": metadata.get("difficulty_level") or "unknown",
        "topics": _string_list(metadata.get("topics") or []),
        "queries": _queries(metadata),
        "experiences": _clean_experiences(metadata),
        "fitness_advice": _clean_fitness_advice(metadata),
        "motivational_takeaways": _clean_takeaways(metadata),
        "generated_at": metadata.get("generated_at"),
        "transcript_char_count": metadata.get("transcript_char_count"),
    })


def upload_metadata_file(
    metadata_path: str | Path,
    *,
    videos_table_name: str,
    segments_table_name: str | None = None,
) -> None:
    import boto3

    dynamodb = boto3.resource("dynamodb")
    videos_table = dynamodb.Table(videos_table_name)

    metadata = load_json(metadata_path)
    video_id = metadata.get("video_id") or Path(metadata_path).stem.replace("_meta", "")
    item = build_video_dynamo_item(metadata, video_id=video_id)
    videos_table.put_item(Item=to_dynamo_value(item))
    LOGGER.info("Uploaded video metadata for %s to %s", video_id, videos_table_name)

    if segments_table_name:
        LOGGER.warning(
            "DITTO_VIDEO_SEGMENTS_TABLE/--segments-table is ignored. "
            "The current schema stores one lean item per video_id in %s.",
            videos_table_name,
        )


def upload_directory(
    *,
    metadata_dir: str | Path = DEFAULT_METADATA_DIR,
    videos_table_name: str | None = None,
    segments_table_name: str | None = None,
) -> None:
    videos_table_name = videos_table_name or os.getenv("DITTO_VIDEOS_TABLE")
    segments_table_name = segments_table_name or os.getenv("DITTO_VIDEO_SEGMENTS_TABLE")
    if not videos_table_name:
        raise RuntimeError("Provide --videos-table or set DITTO_VIDEOS_TABLE.")

    for metadata_path in iter_json_files(metadata_dir):
        upload_metadata_file(
            metadata_path,
            videos_table_name=videos_table_name,
            segments_table_name=segments_table_name,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload video metadata to DynamoDB.")
    parser.add_argument("--metadata-dir", type=Path, default=DEFAULT_METADATA_DIR)
    parser.add_argument("--file", type=Path, help="Upload one metadata JSON file.")
    parser.add_argument("--videos-table", default=os.getenv("DITTO_VIDEOS_TABLE"))
    parser.add_argument("--segments-table", default=os.getenv("DITTO_VIDEO_SEGMENTS_TABLE"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.videos_table:
        raise SystemExit("Provide --videos-table or set DITTO_VIDEOS_TABLE.")

    if args.file:
        upload_metadata_file(
            args.file,
            videos_table_name=args.videos_table,
            segments_table_name=args.segments_table,
        )
    else:
        upload_directory(
            metadata_dir=args.metadata_dir,
            videos_table_name=args.videos_table,
            segments_table_name=args.segments_table,
        )


if __name__ == "__main__":
    main()

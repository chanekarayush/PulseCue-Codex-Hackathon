"""Upload enriched video metadata and segment records to DynamoDB."""

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


def _segment_records(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    video_id = metadata["video_id"]
    for segment_type, key in (
        ("experience", "experiences"),
        ("fitness_advice", "fitness_advice"),
        ("query_solved", "queries_solved"),
    ):
        for index, segment in enumerate(metadata.get(key) or []):
            if not isinstance(segment, dict):
                continue
            records.append(
                {
                    **segment,
                    "segment_id": f"{video_id}#{segment_type}#{index:03d}",
                    "video_id": video_id,
                    "segment_type": segment_type,
                    "source_type": "youtube_video",
                }
            )
    return records


def upload_metadata_file(
    metadata_path: str | Path,
    *,
    videos_table_name: str,
    segments_table_name: str | None = None,
) -> None:
    import boto3

    dynamodb = boto3.resource("dynamodb")
    videos_table = dynamodb.Table(videos_table_name)
    segments_table = dynamodb.Table(segments_table_name) if segments_table_name else None

    metadata = load_json(metadata_path)
    video_id = metadata.get("video_id") or Path(metadata_path).stem.replace("_meta", "")
    item = {
        **metadata,
        "video_id": video_id,
        "pk": f"VIDEO#{video_id}",
        "sk": "METADATA",
    }
    videos_table.put_item(Item=to_dynamo_value(item))
    LOGGER.info("Uploaded video metadata for %s to %s", video_id, videos_table_name)

    if segments_table:
        for record in _segment_records(item):
            record.setdefault("pk", f"VIDEO#{video_id}")
            record.setdefault("sk", f"SEGMENT#{record['segment_id']}")
            segments_table.put_item(Item=to_dynamo_value(record))
        LOGGER.info("Uploaded segment records for %s to %s", video_id, segments_table_name)


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

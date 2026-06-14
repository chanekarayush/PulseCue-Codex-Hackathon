"""Sync video metadata records from DynamoDB into local JSON files."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from data_pipeline.common import ensure_dir, get_logger, save_json_atomic
from data_pipeline.dynamo import from_dynamo_value


LOGGER = get_logger(__name__)
VIDEO_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = VIDEO_DIR / "enriched_metadata"


def _scan_table(table: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {}
    while True:
        response = table.scan(**kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return items
        kwargs["ExclusiveStartKey"] = last_key


def sync_videos_from_dynamo(
    *,
    table_name: str,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> list[Path]:
    import boto3

    output_dir = ensure_dir(output_dir)
    table = boto3.resource("dynamodb").Table(table_name)
    saved: list[Path] = []

    for item in _scan_table(table):
        parsed = from_dynamo_value(item)
        video_id = parsed.get("video_id")
        if not video_id:
            LOGGER.warning("Skipping Dynamo item without video_id: %s", parsed)
            continue
        output_path = output_dir / f"{video_id}_meta.json"
        save_json_atomic(output_path, parsed)
        saved.append(output_path)
        LOGGER.info("Synced %s", output_path)

    return saved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync video metadata from DynamoDB.")
    parser.add_argument("--table", default=os.getenv("DITTO_VIDEOS_TABLE"))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.table:
        raise SystemExit("Provide --table or set DITTO_VIDEOS_TABLE.")
    sync_videos_from_dynamo(table_name=args.table, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
